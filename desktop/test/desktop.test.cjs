'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {notificationBatch}=require('../notifications.cjs');
const {preferences,validIPC,isLocalFrame,desktopPort}=require('../policy.cjs');
const note=(id,content='Reminder: Test',read=0)=>({id,content,read});
test('initial poll baselines existing notifications; later poll announces only new IDs',()=>{
 assert.deepEqual(notificationBatch([note(1),note(2)],null,true),{cursor:2,toast:null});
 const fresh=notificationBatch([note(3),note(2),note(1)],2,true);
 assert.equal(fresh.cursor,3);assert.equal(fresh.toast.silent,false);
 assert.equal(notificationBatch([note(3)],3,true).toast,null);
});
test('mute, missed reminders, read state and grouped alerts are respected',()=>{
 assert.equal(notificationBatch([note(2)],1,false).toast.silent,true);
 assert.equal(notificationBatch([note(2,'Missed while offline: Test')],1,true).toast.silent,true);
 assert.equal(notificationBatch([note(2,'Reminder: Test',1)],1,true).toast,null);
 const grouped=notificationBatch([note(4),note(3)],2,true);
 assert.match(grouped.toast.title,/2 reminders/);
 assert.equal(grouped.cursor,4);
});
test('database reset and malformed data do not replay reminders',()=>{
 assert.equal(notificationBatch([note(1)],100,true).toast,null);
 assert.deepEqual(notificationBatch([{id:'3',content:'invalid'}],null,true),{cursor:0,toast:null});
});
test('desktop preferences cannot set tokens, commands, paths, or nonboolean values',()=>{
 assert.deepEqual(preferences({soundEnabled:false}),{soundEnabled:false});
 for(const value of [{token:'secret'},{command:'cmd.exe'},{soundEnabled:'yes'},null,[]]) assert.throws(()=>preferences(value));
});
test('IPC validates exact window, main frame, origin and allowlisted channel',()=>{
 const frame={url:'http://127.0.0.1:8765/'};
 const contents={mainFrame:frame};const window={isDestroyed:()=>false,webContents:contents};
 const event={sender:contents,senderFrame:frame};
 assert.equal(validIPC(event,window,'http://127.0.0.1:8765','bujji:bootstrap'),true);
 assert.equal(validIPC(event,window,'http://127.0.0.1:8765','bujji:choose-document-folder'),true);
 assert.equal(validIPC({...event,senderFrame:{url:frame.url}},window,'http://127.0.0.1:8765','bujji:choose-document-folder'),false);
 assert.equal(validIPC(event,window,'http://127.0.0.1:8765','arbitrary:exec'),false);
 assert.equal(validIPC({...event,senderFrame:{url:frame.url}},window,'http://127.0.0.1:8765','bujji:bootstrap'),false);
 frame.url='https://evil.example/';
 assert.equal(validIPC(event,window,'http://127.0.0.1:8765','bujji:bootstrap'),false);
 assert.equal(isLocalFrame('http://127.0.0.1.evil.example:8765','http://127.0.0.1:8765'),false);
});
test('port validation refuses invalid configuration',()=>{
 assert.equal(desktopPort(undefined),8765);assert.equal(desktopPort('8766'),8766);
 for(const value of ['abc','80','65536','8765.5','']) assert.throws(()=>desktopPort(value));
});
test('readiness accepts Python JSON spacing and rejects wrong ports or arbitrary lines',()=>{
 const {readyLine}=require('../policy.cjs');
 assert.equal(readyLine('BUJJI_READY:{"port": 8765}',8765),true);
 assert.equal(readyLine('BUJJI_READY:{"port":8766}',8765),false);
 assert.equal(readyLine('BUJJI_READY:not json',8765),false);
 assert.equal(readyLine('some log line',8765),false);
});
test('microphone grant is reused in session and concurrent requests share one prompt',async()=>{
 const {MicrophoneGate}=require('../microphone.cjs');const gate=new MicrophoneGate();let asks=0;
 const prompt=async()=>{asks++;return true};
 const values=await Promise.all([gate.request(prompt,()=>true),gate.request(prompt,()=>true)]);
 assert.deepEqual(values,[true,true]);assert.equal(asks,1);
 assert.equal(await gate.request(prompt,()=>true),true);assert.equal(asks,1);
 assert.equal(await gate.request(prompt,()=>false),false);
});
test('denied or hidden microphone prompt does not silently grant access',async()=>{
 const {MicrophoneGate}=require('../microphone.cjs');const gate=new MicrophoneGate();
 assert.equal(await gate.request(async()=>false,()=>true),false);assert.equal(gate.granted,false);
 let visible=true;
 assert.equal(await gate.request(async()=>{visible=false;return true},()=>visible),false);
 assert.equal(gate.granted,false);
});
test('sound bridge waits for a matching backend acknowledgement',async()=>{
 const {SoundBridge}=require('../sound.cjs');let command;
 const bridge=new SoundBridge(line=>{command=JSON.parse(line)},100);
 const result=bridge.request();
 assert.equal(command.command,'chime');
 bridge.feed('BUJJI_SOUND:'+JSON.stringify({id:'wrong',ok:true,reason:'started'}));
 bridge.feed('BUJJI_SOUND:'+JSON.stringify({id:command.id,ok:true,reason:'started'}));
 assert.deepEqual(await result,{ok:true,reason:'started'});assert.equal(bridge.pending.size,0);
});
test('sound timeouts and closed backends are reported instead of claiming sound played',async()=>{
 const {SoundBridge}=require('../sound.cjs');
 const timeout=new SoundBridge(()=>{},5);
 assert.deepEqual(await timeout.request(),{ok:false,reason:'timeout'});
 const closed=new SoundBridge(()=>{},100);const result=closed.request();closed.close();
 assert.deepEqual(await result,{ok:false,reason:'backend-unavailable'});
});
test('computer IPC is restricted to the exact visible widget main frame',()=>{
 const {validComputerIPC}=require('../policy.cjs');
 const frame={url:'http://127.0.0.1:8765/?computer=1'},contents={mainFrame:frame};let visible=true;
 const widget={isDestroyed:()=>false,isVisible:()=>visible,webContents:contents};
 const event={sender:contents,senderFrame:frame};
 assert.equal(validComputerIPC(event,widget,'http://127.0.0.1:8765','bujji:computer'),true);
 assert.equal(validComputerIPC({...event,sender:{}},widget,'http://127.0.0.1:8765','bujji:computer'),false);
 assert.equal(validComputerIPC({...event,senderFrame:{url:frame.url}},widget,'http://127.0.0.1:8765','bujji:computer'),false);
 assert.equal(validComputerIPC(event,widget,'http://127.0.0.1:8765','bujji:set-preferences'),false);
 visible=false;assert.equal(validComputerIPC(event,widget,'http://127.0.0.1:8765','bujji:computer'),false);
});

test('Focus quiet preserves the cursor but only emits focus/break alerts',()=>{
 const {notificationBatch}=require('../notifications.cjs');
 assert.deepEqual(notificationBatch([{id:4,content:'Reminder: task',read:0,quiet:true}],3,true),{cursor:4,toast:null});
 const batch=notificationBatch([{id:5,content:'Focus: done',read:0,quiet:false},{id:4,content:'Reminder: task',read:0,quiet:true}],3,true);
 assert.equal(batch.cursor,5);assert.equal(batch.toast.body,'Focus: done');assert.equal(batch.toast.silent,false);
});
