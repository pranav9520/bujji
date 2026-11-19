import tempfile
import os
"""Browser-only UI checks with an explicit fake native bridge; not Android device tests.
Run: python -m pip install playwright; python android/tests/ui_smoke.py
Requires Chromium installed or PLAYWRIGHT_CHROMIUM_EXECUTABLE set.
"""
from pathlib import Path
import json, os, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright
assets=Path(__file__).resolve().parents[1]/'app/src/main/assets'
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(assets),**kwargs)
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
mock=r'''(() => {
 const state={version:'1.0.0',settings:{name:'Alex',provider:'gemini',model:'test-model',hasKey:true,speak:false,focusMode:false,budgetMinutes:480,nudgeInterval:60,quietStart:22,quietEnd:7},messages:[],memories:[],reminders:[],events:[],focus:{},permissions:{notifications:false,precise:false,usage:false}};
 state.deepFocus={active:{},tasks:[],stats:{focused_ms:0,completed:0,completion:null},defaults:{work_minutes:45,break_minutes:10,rounds:3,quiet:false,auto_break:true},choice:{}};
 state.ai={keys:{gemini:true},models:{gemini:'test-model'},routes:{daily:'gemini',study:'openai',research:'perplexity',coding:'anthropic',writing:'anthropic',analysis:'openai'},speechProvider:'gemini'};
 window.mockState=state;window.calls=[];
 window.BujjiAndroid={call(raw){const c=JSON.parse(raw);calls.push(c);let result={};const p=c.payload;
 switch(c.action){
 case 'state':result=structuredClone(state);break;
 case 'settings':if(p.routes)state.ai.routes=p.routes;if(p.provider){state.ai.models[p.provider]=p.model;if(p.apiKey)state.ai.keys[p.provider]=true;}if(p.speechProvider)state.ai.speechProvider=p.speechProvider;Object.assign(state.settings,p);delete state.settings.apiKey;result=structuredClone(state);break;
 case 'chat':if(p.mode==='short'){result={reply:p.text==='Explain DBMS'?'A DBMS stores and organizes data so you can find and update it.':'A little company, right here.'};}else if(p.text.includes('assignment.txt')){state.messages.push({id:'file-user',role:'user',body:p.text,created:Date.now()},{id:'file-reply',role:'assistant',source:'laptop',body:'Found assignment.txt.',files:[{name:'assignment.txt',path:'C:\\\\Users\\\\Test\\\\assignment.txt',bytes:123,kind:'file'}],created:Date.now()});result={reply:'Found assignment.txt.'};}else{state.messages.push({role:'user',body:p.text,created:Date.now()},{role:'assistant',body:'<img src=x onerror="window.bad=true"> Hello!',created:Date.now()});result={reply:state.messages.at(-1).body};}break;
 case 'remoteStatus':result={online:true,protocol:2,permissions:{control:true,files:true},roots:['C:\\Users\\Test'],files_enabled:true};break;
 case 'remoteControl':result=p.operation==='status'?{windows:[{id:'window-1',title:'Notepad',exe:'notepad.exe'}]}:{completed:true,summary:'Finished remote command',results:[{detail:'Opened app (mock only)'}]};break;
 case 'remoteStop':result={stopped:true};break;
 case 'remoteFiles':result=p.operation==='read'?{text:'Assignment notes',path:p.path}:p.operation==='search'?{results:[{path:'C:\\Users\\Test\\assignment.txt',kind:'file',name:'assignment.txt'}]}:{path:p.path,entries:[{path:'C:\\Users\\Test\\assignment.txt',name:'assignment.txt',kind:'file',bytes:123}],next_offset:null};break;
 case 'remoteDownload':result={message:'File saved on this phone.'};break;
 case 'memoryAdd':state.memories.unshift({id:'memory-1',body:p.text,updated:Date.now()});result=structuredClone(state);break;
 case 'memoryRemove':state.memories=[];result=structuredClone(state);break;
 case 'reminderAdd':state.reminders.push({id:'reminder-1',title:p.title,due:p.at,status:'pending',kind:'reminder',repeat_mode:p.repeat});result=structuredClone(state);break;
 case 'reminderComplete':state.reminders[0].status='done';result=structuredClone(state);break;
 case 'workFocus':{const d=state.deepFocus,a=d.active;switch(p.action){
 case 'start':d.active={id:'focus-test',title:p.title,work_ms:p.work_minutes*60000,break_ms:p.break_minutes*60000,rounds:p.rounds,round:1,phase:'work',status:'running',remaining:p.work_minutes*60000,deadline:Date.now()+p.work_minutes*60000,quiet:p.quiet,auto_break:p.auto_break};break;
 case 'pause':a.remaining=a.deadline-Date.now();a.status='paused';break;
 case 'resume':a.deadline=Date.now()+a.remaining;a.status='running';break;
 case 'end':a.status='finished';break;
 case 'task_add':d.tasks.push({id:'task-1',title:p.title,done:0});break;
 case 'task_toggle':d.tasks[0].done=p.done?1:0;break;
 }result=structuredClone(state);break;}
 case 'focusStart':state.focus={title:p.title,start:Date.now(),end:Date.now()+p.minutes*60000};result={message:'Focus started'};break;
 case 'focusStop':state.focus={};result=structuredClone(state);break;
 case 'usage':result={permission:true,minutes:321,apps:[{name:'Browser',minutes:120}]};break;
 case 'pairLaptop':state.pairing={paired:true,url:p.url,lastSync:0,conflicts:[]};state.laptopPaired=true;result={message:'Paired'};break;
 case 'syncLaptop':state.memories.unshift({id:'laptop-memory',body:'Shared project context',updated:Date.now()});state.pairing.lastSync=Date.now();result={message:'Memories and reminders synced.'};break;
 case 'disconnectLaptop':state.pairing={paired:false};result=structuredClone(state);break;
 case 'record':setTimeout(()=>Bujji.event('recording',{active:true}),10);break;
 }
 setTimeout(()=>Bujji.response({id:c.id,result}),5);
 }};
 addEventListener('DOMContentLoaded',()=>setTimeout(()=>Bujji.event('ready',{}),20));
})();'''
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'),args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':393,'height':873},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script(mock);page.goto(f'http://127.0.0.1:{server.server_port}/index.html')
    page.get_by_role('heading',name='Good',exact=False).wait_for()
    assert page.locator('.orb').count()==1
    assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth')
    page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-android-home.png'),full_page=True)
    page.get_by_role('button',name='Type instead').click()
    page.locator('#chat-input').fill('Hello from phone')
    page.get_by_role('button',name='Send',exact=True).click()
    page.locator('.message.assistant').wait_for()
    assert page.locator('#messages img').count()==0
    assert page.evaluate('window.bad') is None
    page.get_by_role('button',name='Memory',exact=True).click()
    page.get_by_role('button',name='Add memory').click()
    page.get_by_role('textbox',name='Memory',exact=True).fill('I prefer concise replies.')
    page.get_by_role('button',name='Save memory').click()
    page.get_by_text('I prefer concise replies.',exact=True).wait_for()
    page.get_by_role('button',name='Reminders',exact=True).click()
    page.get_by_role('button',name='Add reminder',exact=True).click()
    page.locator('#reminder-form [name=title]').fill('Dummy test task')
    page.get_by_role('button',name='Save reminder',exact=True).click()
    page.get_by_text('Dummy test task',exact=True).wait_for()
    page.once('dialog',lambda d:d.accept())
    page.get_by_role('button',name='Complete Dummy test task',exact=True).click()
    page.get_by_role('button',name='Completed',exact=True).wait_for()
    page.get_by_role('button',name='Home',exact=True).click()
    page.get_by_role('button',name='Focus',exact=True).click()
    page.locator('#work-start-form').get_by_role('button',name='Start focus',exact=True).click()
    page.get_by_role('button',name='Pause',exact=True).wait_for()
    page.get_by_role('button',name='Pause',exact=True).click()
    page.get_by_role('button',name='Resume',exact=True).wait_for()
    page.get_by_role('textbox',name='New focus task',exact=True).fill('Revise DBMS')
    page.locator('#work-task-form button').click()
    page.get_by_role('button',name='Complete Revise DBMS',exact=True).click()
    page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-android-focus.png'),full_page=True)
    page.get_by_role('button',name='Settings',exact=True).click()
    page.get_by_role('button',name='Screen time',exact=True).click()
    page.get_by_text('Browser',exact=True).wait_for()
    page.get_by_role('button',name='Home',exact=True).click()
    page.get_by_role('button',name='Short talk',exact=False).click()
    before=page.evaluate('mockState.messages.length')
    page.evaluate("Bujji.event('transcript',{text:'Just chatting',mode:'short',confirm:false})")
    page.locator('#short-messages .assistant').filter(has_text='A little company, right here.').wait_for()
    assert page.evaluate('mockState.messages.length')==before
    page.get_by_role('button',name='End short talk',exact=True).click()
    assert page.locator('#short-messages').inner_text()==''
    page.evaluate("Bujji.event('transcript',{text:'Review me before sending',mode:'normal',confirm:true})")
    page.get_by_role('heading',name='Did I hear that right?').wait_for()
    assert page.evaluate('mockState.messages.length')==before
    page.get_by_role('button',name='Send this message',exact=True).click()
    page.wait_for_function('mockState.messages.length>2')
    page.get_by_role('button',name='Settings',exact=True).click()
    page.locator('#settings-form [name=provider]').select_option('anthropic')
    assert page.locator('#settings-form [name=model]').input_value()==''
    page.locator('#settings-form [name=provider]').select_option('gemini')
    assert page.locator('#settings-form [name=model]').input_value()=='test-model'
    page.locator('.settings-details summary').filter(has_text='AI task routing').click()
    page.locator('[name=route_study]').select_option('anthropic')
    page.locator('#settings-form [name=apiKey]').fill('private-dummy-key')
    page.get_by_role('button',name='Save settings',exact=True).click()
    page.wait_for_timeout(100)
    assert page.locator('[name=apiKey]').count()==0
    assert page.evaluate('mockState.ai.routes.study')=='anthropic'
    page.get_by_role('button',name='Settings',exact=True).click()
    assert 'notebooklm' not in page.locator('#sheet').inner_text().lower()
    assert 'bhavana' not in page.locator('#sheet').inner_text().lower()
    page.locator('#pairing-form [name=url]').fill('https://laptop.tailnet.ts.net')
    page.locator('#pairing-form [name=code]').fill('0123456789abcdef')
    page.locator('#pairing-form [name=confirmed]').check()
    page.get_by_role('button',name='Pair my laptop',exact=True).click()
    page.get_by_role('button',name='Sync now',exact=True).wait_for()
    page.get_by_role('button',name='Sync now',exact=True).click()
    page.wait_for_timeout(100)
    page.get_by_role('button',name='Memory',exact=True).click()
    page.get_by_text('Shared project context',exact=True).wait_for()
    page.get_by_role('button',name='Home',exact=True).click()
    page.get_by_role('button',name='Chat',exact=True).click()
    page.locator('#chat-input').fill('find assignment.txt')
    page.get_by_role('button',name='Send',exact=True).click()
    page.locator('.chat-file strong').filter(has_text='assignment.txt').wait_for()
    assert page.locator('.chat-file').evaluate("e=>e.getBoundingClientRect().bottom<=document.querySelector('.chat-composer').getBoundingClientRect().top")
    page.locator('.chat-file button').click()
    page.get_by_text('File saved on this phone.',exact=True).wait_for()
    page.get_by_role('button',name='Laptop files',exact=True).click()
    page.locator('[data-laptop-root="0"]').click()
    page.get_by_role('button',name='assignment.txt',exact=False).first.click()
    page.get_by_text('Assignment notes',exact=True).wait_for()
    page.get_by_role('button',name='Save to phone',exact=True).click()
    page.get_by_text('File saved on this phone.',exact=True).wait_for()
    page.locator('#sheet-close').click()
    page.evaluate("document.querySelector('#toast').hidden=true")
    page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-android-chat-files.png'),full_page=True)
    page.get_by_role('button',name='Home',exact=True).click()
    page.get_by_role('button',name='Short talk',exact=False).click()
    page.evaluate("Bujji.event('transcript',{text:'Explain DBMS',mode:'short',confirm:false})")
    page.locator('#short-messages .assistant').filter(has_text='A DBMS stores and organizes data so you can find and update it.').wait_for()
    page.wait_for_function("calls.some(c=>c.action==='speak'&&c.payload.text.startsWith('A DBMS'))")
    page.get_by_role('button',name='End short talk',exact=True).click()
    page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-android-home-paired.png'),full_page=True)
    page.get_by_role('button',name='Control laptop',exact=False).click()
    page.get_by_role('button',name='Run',exact=True).wait_for()
    assert page.get_by_role('heading',name='Laptop files',exact=True).count()==0
    page.get_by_label('Laptop command',exact=True).fill('Open Notepad')
    page.get_by_role('button',name='Run',exact=True).click()
    page.get_by_text('Opened app (mock only)',exact=False).wait_for()
    page.locator('summary').filter(has_text='Screen options').click()
    page.get_by_role('button',name='Refresh open windows',exact=True).click()
    page.get_by_label('Target window',exact=True).select_option('window-1')
    page.evaluate("mockState.settings.focusMode=false;Bujji.event('transcript',{text:'Open YouTube',mode:'remote',confirm:true})")
    page.wait_for_function("calls.filter(c=>c.action==='remoteControl'&&c.payload.operation==='command').length===2")
    page.get_by_role('checkbox',name='Keep listening',exact=True).check()
    page.evaluate("Bujji.event('transcript',{text:'Open GitHub',mode:'remote',confirm:false})")
    page.wait_for_function("calls.some(c=>c.action==='record'&&c.payload.mode==='remote')")
    page.evaluate("Bujji.event('paused',{})")
    before_pause=page.evaluate("calls.filter(c=>c.action==='record'&&c.payload.mode==='remote').length")
    page.wait_for_timeout(900)
    assert page.evaluate("calls.filter(c=>c.action==='record'&&c.payload.mode==='remote').length")==before_pause
    page.get_by_role('button',name='Stop',exact=True).click()
    page.get_by_text('Stopped future steps.',exact=False).wait_for()
    assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth')
    page.evaluate("document.querySelector('#toast').hidden=true")
    page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-android-laptop.png'),full_page=True)
    assert not errors,errors
    assert not page.locator('body').evaluate('(e)=>/[\u0c00-\u0c7f]/.test(e.innerText)')
    print('PASS: home, responsive layout, chat escaping, memory, reminders, focus, usage, short-talk isolation, focus review, secret input clearing; no JS errors')
    browser.close()
server.shutdown()
