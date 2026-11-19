'use strict';
const {app,BrowserWindow,Tray,Menu,Notification,nativeImage,ipcMain,dialog,shell} = require('electron');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const dotenv = require('dotenv');
const {randomBytes} = require('node:crypto');
const computerToken = randomBytes(32).toString('hex');
let computerWindow, computerAbort;
const fileGrantToken = randomBytes(32).toString('hex');
let choosingDocuments = false;
const policy = require('./policy.cjs');
const {notificationBatch} = require('./notifications.cjs');
const {MicrophoneGate} = require('./microphone.cjs');
const {SoundBridge} = require('./sound.cjs');
let soundBridge;

app.setName('Bujji');
app.setPath('userData',path.join(app.getPath('appData'),'BujjiCommunity'));
app.setAppUserModelId('org.bujji.desktop');
let window, tray, backend, origin='', token='', preferences={}, stateFile, quitting=false, stopped=false, pollTimer, polling=false;
let testAt=0;
const notices = new Set();
const iconPath = path.join(__dirname,'assets','icon.png');
function persist() {
  const temp = stateFile + '.tmp';
  fs.writeFileSync(temp,JSON.stringify(preferences,null,2),{mode:0o600});
  fs.renameSync(temp,stateFile);
}
function publicPreferences() {
  return {soundEnabled:preferences.soundEnabled,startAtLogin:preferences.startAtLogin,notificationsSupported:Notification.isSupported(),packaged:app.isPackaged};
}
async function playSound() {
  if (!preferences.soundEnabled) return {ok:false,reason:'muted'};
  if (!soundBridge) return {ok:false,reason:'backend-unavailable'};
  return soundBridge.request();
}
async function notify(toast) {
  let notificationRequested=false;
  try { if (Notification.isSupported()) {
    // The owned backend plays the bundled chime; do not rely on OS toast audio.
    const notice = new Notification({...toast,silent:true,icon:iconPath});
    notices.add(notice);
    notice.on('click',()=>{show();notices.delete(notice);});
    notice.on('close',()=>notices.delete(notice));
    notice.on('failed',()=>notices.delete(notice));
    notice.show();notificationRequested=true;
  }} catch { /* Toast failure must not suppress the independent chime. */ }
  const sound=toast.silent?{ok:false,reason:'muted'}:await playSound();
  return {notificationRequested,sound};
}
function show() { if (window && !window.isDestroyed()) {window.show();window.focus();} }
function menu() {
  tray.setContextMenu(Menu.buildFromTemplate([
    {label:'Open Bujji',click:show},
    {label:'Reminder sounds',type:'checkbox',checked:preferences.soundEnabled,click:item=>{preferences.soundEnabled=item.checked;persist();}},
    {label:'Test sound only',click:()=>playSound()},
    {label:'Test notification & sound',click:()=>notify({title:'Bujji sound test',body:'This is how your reminders will appear. Sound depends on Windows notification and volume settings.',silent:!preferences.soundEnabled})},
    {type:'separator'},
    {label:'Launch at sign-in',type:'checkbox',checked:preferences.startAtLogin,enabled:app.isPackaged && process.platform==='win32',click:item=>{app.setLoginItemSettings({openAtLogin:item.checked,args:['--hidden']});preferences.startAtLogin=item.checked;persist();}},
    {label:'Quit Bujji',click:()=>app.quit()},
  ]));
}
async function request(url) {
  return fetch(url,{headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(4000),redirect:'error'});
}
async function notifications() {
  if (polling || quitting) return;
  polling=true;
  try {
    const response=await request(origin+'/api/notifications');
    if (!response.ok) return;
    const rows=await response.json();
    if (!Array.isArray(rows)) return;
    const batch=notificationBatch(rows,preferences.lastSeenNotification,preferences.soundEnabled);
    // Persist first: a crash must not repeatedly play old reminder sounds.
    if (preferences.lastSeenNotification !== batch.cursor) {preferences.lastSeenNotification=batch.cursor;persist();}
    if (batch.toast) await notify(batch.toast);
  } catch { /* API polling is retried; never log tokens or private notification text. */ }
  finally {polling=false;}
}
async function rootDirectory() {
  if (!app.isPackaged) return path.resolve(__dirname,'..');
  const root=path.join(app.getPath('userData'),'workspace');
  fs.mkdirSync(root,{recursive:true,mode:0o700});
  const configPath=path.join(root,'.env');
  if (!fs.existsSync(configPath)) {
    const template=fs.readFileSync(path.join(process.resourcesPath,'config.example'),'utf8');
    const config=template.replace(/^BUJJI_TOKEN=.*$/m,'BUJJI_TOKEN='+randomBytes(48).toString('base64url'));
    fs.writeFileSync(configPath,config,{mode:0o600,flag:'wx'});
  }
  preferences.projectRoot=root;persist();
  return root;
}
async function startBackend(root) {
  const config=dotenv.parse(fs.readFileSync(path.join(root,'.env')));
  token=(config.BUJJI_TOKEN||'').trim();
  if (token.length<32) throw new Error('Your .env needs a BUJJI_TOKEN of at least 32 characters. Run the existing setup first.');
  const port=policy.desktopPort(config.BUJJI_DESKTOP_PORT);
  origin='http://127.0.0.1:'+port;
  const executable=app.isPackaged?path.join(process.resourcesPath,'backend','bujji-backend.exe'):path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
  if (!fs.existsSync(executable)) throw new Error('The Python backend is missing. Run setup for a source checkout, or rebuild the Windows installer.');
  const args=app.isPackaged?['--port',String(port)]:['-m','bujji.desktop_backend','--port',String(port)];
  const env={...process.env,...config,BUJJI_TOKEN:token,
    BUJJI_DATA_DIR:policy.localDirectory(root,config.BUJJI_DATA_DIR,'data'),
    BUJJI_KNOWN_FOLDERS:JSON.stringify(Object.fromEntries(['home','desktop','documents','downloads','pictures','videos','music'].map(key=>[key,app.getPath(key)]))),
    BUJJI_LOCAL_FILE_ROOTS:JSON.stringify([app.getPath('home'), ...(process.platform==='win32' ? Array.from({length:24},(_,i)=>String.fromCharCode(67+i)+':'+path.sep).filter(p=>fs.existsSync(p)) : [])]),
    BUJJI_COMPUTER_TOKEN:computerToken, BUJJI_DESKTOP_PID:String(process.pid),
    BUJJI_FILE_GRANT_TOKEN:fileGrantToken, BUJJI_DESKTOP_FOLDER:app.getPath('desktop'),
    BUJJI_FILE_ROOT:policy.localDirectory(root,config.BUJJI_FILE_ROOT,'data/inbox'),
    BUJJI_FRONTEND_DIR:app.isPackaged?path.join(process.resourcesPath,'frontend'):path.join(root,'frontend','dist'),
    BUJJI_DISABLE_TELEGRAM:'1',PYTHONUTF8:'1',PYTHONUNBUFFERED:'1'};
  if (!fs.existsSync(path.join(env.BUJJI_FRONTEND_DIR,'index.html'))) throw new Error('The interface is not built. Run npm.cmd --prefix frontend run build first.');
  let announced=false, exited=false, output='';
  backend=spawn(executable,args,{cwd:root,env,windowsHide:true,stdio:['pipe','pipe','pipe'],shell:false});
  soundBridge=new SoundBridge(line=>{if(backend.exitCode!==null || backend.stdin.destroyed)throw new Error('backend unavailable');backend.stdin.write(line);});
  backend.stdin.on('error',()=>soundBridge?.close());
  backend.on('error',()=>{exited=true;soundBridge?.close();});
  backend.stdout.on('data',chunk=>{
    output=(output+chunk.toString()).slice(-4096);
    const lines=output.split('\n');output=lines.pop()||'';
    if (lines.some(line=>policy.readyLine(line,port))) announced=true;
    for(const line of lines)soundBridge?.feed(line);
  });
  // Consume stderr without persisting private paths or arbitrary exceptions.
  backend.stderr.on('data',()=>{});
  backend.on('exit',()=>{
    exited=true;soundBridge?.close();
    if (!quitting && window) {tray?.setToolTip('Bujji · backend stopped');dialog.showErrorBox('Bujji backend stopped','Your backend stopped unexpectedly. Quit and reopen Bujji. Your saved data has not been deleted.');}
  });
  const deadline=Date.now()+30000;
  while (Date.now()<deadline) {
    if (exited) throw new Error('Backend could not start. Stop your old Bujji terminal with Ctrl+C and quit previous instances. Check .env and make sure the desktop port is free. No unrelated process was stopped.');
    if (announced) {
      try {const r=await request(origin+'/api/status');if (r.ok && (await r.json()).online) return;} catch {}
    }
    await new Promise(resolve=>setTimeout(resolve,200));
  }
  throw new Error('Backend did not become ready within 30 seconds. Stop your old Bujji backend and check its configuration.');
}
function secureWindow() {
  window=new BrowserWindow({width:1380,height:900,minWidth:750,minHeight:580,show:false,title:'Bujji',backgroundColor:'#100f20',icon:iconPath,webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,sandbox:true,nodeIntegration:false,webSecurity:true,allowRunningInsecureContent:false,webviewTag:false,devTools:!app.isPackaged,backgroundThrottling:true}});
  window.setMenuBarVisibility(false);
  window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  window.webContents.on('will-navigate',(event,url)=>{if (!policy.isLocalFrame(url,origin)) event.preventDefault();});
  window.webContents.on('will-attach-webview',event=>event.preventDefault());
  const session=window.webContents.session;
  const microphone=new MicrophoneGate();
  const owned = contents => [window,computerWindow].find(w=>w && !w.isDestroyed() && w.webContents===contents && w.isVisible());
  session.setPermissionCheckHandler((contents,permission,requestingOrigin,details)=>!!owned(contents) && policy.isLocalFrame(requestingOrigin,origin) && permission==='media' && details.mediaType==='audio' && microphone.granted);
  session.setPermissionRequestHandler(async(contents,permission,callback,details)=>{
    const allowed=()=>!!owned(contents) && policy.isLocalFrame(details.requestingUrl||contents.getURL(),origin) && permission==='media' && Array.isArray(details.mediaTypes) && details.mediaTypes.length>0 && details.mediaTypes.every(type=>type==='audio');
    if (!allowed()) return callback(false);
    try {
      const grant=await microphone.request(async()=>{
        const result=await dialog.showMessageBox(owned(contents),{type:'question',title:'Bujji microphone',message:'Allow microphone access for this app session?',detail:'Visible Bujji windows can record up to 20 seconds per turn, ending after three seconds of silence. Audio goes to your speech provider. Hiding a recording window stops capture. Camera and background capture are disabled.',buttons:['Allow microphone','Cancel'],defaultId:1,cancelId:1});
        return result.response===0;
      },allowed);
      callback(grant && allowed());
    } catch {callback(false);}
  });
  window.on('close',event=>{if (!quitting) {event.preventDefault();window.webContents.send('bujji:hidden');window.hide();}});
  window.on('minimize',()=>window.webContents.send('bujji:hidden'));
  window.once('ready-to-show',()=>{if (!process.argv.includes('--hidden')) show();});
  window.loadURL(origin);
}
async function stopComputer() {
  computerAbort?.abort();computerAbort=null;
  try { await fetch(origin+'/api/computer',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json','X-Bujji-Computer':computerToken},body:JSON.stringify({operation:'stop'}),signal:AbortSignal.timeout(2500)}); } catch {}
}
function openComputer() {
  if(process.platform!=='win32') throw new Error('Computer control is available in the Windows desktop app.');
  if(computerWindow && !computerWindow.isDestroyed()){computerWindow.show();computerWindow.focus();return {opened:true};}
  window?.webContents.send('bujji:hidden');
  computerWindow=new BrowserWindow({width:380,height:500,minWidth:330,minHeight:360,alwaysOnTop:true,show:false,title:'Bujji · Computer control',backgroundColor:'#100f20',webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,sandbox:true,nodeIntegration:false,webSecurity:true,allowRunningInsecureContent:false,webviewTag:false,devTools:!app.isPackaged,backgroundThrottling:true}});
  const widget=computerWindow;
  widget.setMenuBarVisibility(false);
  widget.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  widget.webContents.on('will-navigate',(event,url)=>{if(!policy.isLocalFrame(url,origin))event.preventDefault();});
  widget.webContents.on('will-attach-webview',event=>event.preventDefault());
  widget.on('close',()=>{widget.webContents.send('bujji:hidden');void stopComputer();});
  widget.on('minimize',()=>{widget.webContents.send('bujji:hidden');void stopComputer();});
  widget.on('closed',()=>{if(computerWindow===widget)computerWindow=null;});
  widget.once('ready-to-show',()=>widget.show());
  widget.loadURL(origin+'/?computer=1');
  return {opened:true};
}
function registerIPC() {
  const handle=(channel,fn)=>ipcMain.handle(channel,(event,...args)=>{if (!(policy.validIPC(event,window,origin,channel) || (channel==='bujji:bootstrap' && policy.validIPC(event,computerWindow,origin,channel)))) throw new Error('Untrusted desktop request');return fn(...args);});
  handle('bujji:open-settings-folder',async()=>{const result=await shell.openPath(await rootDirectory());if(result)throw new Error('Could not open configuration folder.');return {opened:true};});
  handle('bujji:choose-document-folder', async () => {
    if (choosingDocuments) throw new Error('A folder picker is already open.');
    choosingDocuments = true;
    try {
      const result = await dialog.showOpenDialog(window, {title:'Allow Bujji to inspect documents in this folder', buttonLabel:'Allow this folder', properties:['openDirectory']});
      if (result.canceled || !result.filePaths[0]) return null;
      const response = await fetch(origin+'/api/documents/grant', {
        method:'POST', headers:{'Content-Type':'application/json',Authorization:'Bearer '+token,'X-Bujji-Native':fileGrantToken},
        body:JSON.stringify({path:result.filePaths[0]}), signal:AbortSignal.timeout(10000)
      });
      if (!response.ok) throw new Error('Folder access could not be granted. Choose a regular folder, not a drive root or linked folder.');
      return response.json();
    } finally { choosingDocuments = false; }
  });
  ipcMain.handle('bujji:open-computer',event=>{
    if(!policy.validIPC(event,window,origin,'bujji:open-computer'))throw new Error('Untrusted widget opener');
    return openComputer();
  });
  ipcMain.handle('bujji:close-computer',event=>{
    if(!policy.validComputerIPC(event,computerWindow,origin,'bujji:close-computer'))throw new Error('Untrusted widget request');
    computerWindow.close();return {closed:true};
  });
  ipcMain.handle('bujji:computer',async(event,body)=>{
    if(!policy.validComputerIPC(event,computerWindow,origin,'bujji:computer'))throw new Error('Use the visible computer widget');
    if(!body || typeof body!=='object' || Array.isArray(body) || !['status','plan','execute','stop','save_routine','delete_routine','diagnostics','info'].includes(body.operation) || JSON.stringify(body).length>14000)throw new Error('Invalid computer request');
    if(body.operation==='stop'){await stopComputer();return {stopped:true,detail:'Stopped future steps. Completed actions are not undone.'};}
    if(computerAbort)throw new Error('A computer request is already running. Stop it or wait.');
    const controller=new AbortController();computerAbort=controller;
    const timer=setTimeout(()=>controller.abort(),120000);
    try {
      const response=await fetch(origin+'/api/computer',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json','X-Bujji-Computer':computerToken},body:JSON.stringify(body),signal:controller.signal,redirect:'error'});
      const result=await response.json();
      if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Computer request failed');
      return result;
    } finally {clearTimeout(timer);if(computerAbort===controller)computerAbort=null;}
  });
  handle('bujji:bootstrap',()=>({token,origin}));
  handle('bujji:preferences',()=>publicPreferences());
  handle('bujji:set-preferences',value=>{
    const next=policy.preferences(value);
    if ('startAtLogin' in next) {
      if (!app.isPackaged || process.platform!=='win32') throw new Error('Sign-in launch is available in the installed Windows app.');
      app.setLoginItemSettings({openAtLogin:next.startAtLogin,args:['--hidden']});
    }
    Object.assign(preferences,next);persist();menu();return publicPreferences();
  });
  handle('bujji:test-sound',()=>{if(Date.now()-testAt<5000)return {ok:false,reason:'rate-limited'};testAt=Date.now();return playSound();});
  handle('bujji:test-notification',()=>{
    if (Date.now()-testAt<5000) return {notificationRequested:false,sound:{ok:false,reason:'rate-limited'}};
    testAt=Date.now();return notify({title:'Bujji reminder sound test',body:'A reminder will appear here even when Bujji is in the tray. Check Windows sound and notification settings if silent.',silent:!preferences.soundEnabled});
  });
}
async function stopBackend() {
  clearInterval(pollTimer);
  await stopComputer();
  computerWindow?.destroy();
  soundBridge?.close();
  if (!backend || backend.exitCode!==null || backend.signalCode!==null) return;
  await new Promise(resolve=>{
    const killTimer=setTimeout(()=>{backend.kill();resolve();},8000);
    backend.once('exit',()=>{clearTimeout(killTimer);resolve();});
    backend.stdin.on('error',()=>{});
    backend.stdin.end('quit\n');
  });
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance',show);
  app.on('window-all-closed',()=>{});
  app.on('activate',show);
  app.on('before-quit',event=>{
    if (stopped) return;
    event.preventDefault();
    if (quitting) return;
    quitting=true;
    stopBackend().finally(()=>{stopped=true;tray?.destroy();app.quit();});
  });
  app.whenReady().then(async()=>{
    try {
      stateFile=path.join(app.getPath('userData'),'desktop-settings.json');
      let saved={};
      try {saved=JSON.parse(fs.readFileSync(stateFile,'utf8'));} catch {}
      preferences={projectRoot:typeof saved.projectRoot==='string'?saved.projectRoot:undefined,soundEnabled:saved.soundEnabled!==false,startAtLogin:saved.startAtLogin===true,lastSeenNotification:Number.isSafeInteger(saved.lastSeenNotification)?saved.lastSeenNotification:null};
      if (app.isPackaged && process.platform==='win32') preferences.startAtLogin=app.getLoginItemSettings({args:['--hidden']}).openAtLogin;
      const root=await rootDirectory();
      await startBackend(root);
      tray=new Tray(nativeImage.createFromPath(iconPath));tray.setToolTip('Bujji · running privately on your laptop');tray.on('double-click',show);menu();
      registerIPC();secureWindow();
      await notifications();pollTimer=setInterval(notifications,5000);
    } catch(error) {dialog.showErrorBox('Bujji could not start',error instanceof Error?error.message:'Check your local setup.');app.quit();}
  });
}
