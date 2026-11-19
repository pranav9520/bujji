import tempfile
import os
"""Headless visual/interaction QA with isolated laptop data and fake native widget.
Run with Playwright and Chromium installed: python tests/browser_ui_refresh.py
"""
import sys,tempfile,threading,socket,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from bujji.main import create_app
from bujji.config import Settings
from playwright.sync_api import sync_playwright
import uvicorn
from datetime import datetime,timedelta,timezone
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);token='ui-refresh-test-only-'*3;app=create_app(Settings(token=token,data=root/'data',files=root/'files'),background=False)
 app.state.store.set_state('profile',{'name':'Alex'})
 store=app.state.store;store.remember('I prefer concise Telugu-English replies.');store.message('web','user','Can you help with my assignment?');store.message('web','assistant','Of course. Which topic are you working on?')
 store.execute('INSERT INTO reminders(title,due,recurrence,created) VALUES(?,?,?,?)',('Submit Java assignment',(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'none',datetime.now(timezone.utc).isoformat()))
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];server=uvicorn.Server(uvicorn.Config(app,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
 while not server.started:time.sleep(.05)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':1380,'height':900},timezone_id='Asia/Kolkata',reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.add_init_script('sessionStorage.setItem("bujji-token",'+repr(token)+');localStorage.setItem("bujji-session","web")')
  page.goto('http://127.0.0.1:'+str(port));page.get_by_text('I prefer concise Telugu-English replies.',exact=True).wait_for()
  assert page.locator('.quick-section,.system-strip').count()==0
  assert page.get_by_role('button',name='Settings',exact=True).count()==1
  assert page.get_by_role('button',name='Talk to Bujji',exact=True).count()==1
  assert page.get_by_role('button',name='Short talk',exact=True).count()==1
  assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth')
  page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-clean-desktop-home.png'),full_page=True)
  page.get_by_role('button',name='Focus mode',exact=True).click()
  page.get_by_role('button',name='Start focus',exact=True).wait_for()
  page.locator('.deep-setup input').first.fill('DBMS Revision')
  page.get_by_role('button',name='Start focus',exact=True).click()
  page.get_by_role('button',name='Pause',exact=True).wait_for()
  page.get_by_role('button',name='Pause',exact=True).click()
  page.get_by_role('button',name='Resume',exact=True).wait_for()
  page.get_by_role('textbox',name='New focus task').fill('Revise DBMS')
  page.locator('.deep-task-form button').click()
  page.get_by_role('button',name='Complete Revise DBMS').wait_for()
  page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-clean-desktop-focus.png'),full_page=True)
  page.get_by_role('button',name='Focus mode',exact=True).click()
  page.get_by_role('button',name='Type instead',exact=True).click();page.locator('.composer textarea').wait_for();page.get_by_text('Of course. Which topic are you working on?',exact=True).wait_for();page.get_by_role('heading',name='Conversation',exact=False).wait_for()
  assert page.locator('.chat-footnote').count()==0
  tools=page.locator('.chat-tool-options')
  if tools.count():assert not tools.evaluate('(e)=>e.open')
  page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-clean-desktop-chat.png'),full_page=True)
  page.set_viewport_size({'width':750,'height':650});assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth')
  page.set_viewport_size({'width':393,'height':873});assert page.get_by_role('button',name='Settings',exact=True).count()==1;assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth')
  page.get_by_role('button',name='Settings',exact=True).click()
  page.locator('.ai-routing summary').click()
  page.get_by_role('button',name='Use suggested routes',exact=True).click()
  page.get_by_role('button',name='Save AI routes',exact=True).click()
  page.get_by_text('Routes saved.',exact=False).wait_for()
  assert page.get_by_label('Study provider',exact=True).input_value()=='openai'
  assert page.get_by_label('Web research provider',exact=True).input_value()=='perplexity'
  assert 'notebooklm' not in page.locator('.ai-routing').inner_text().lower()
  page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-desktop-routing.png'),full_page=True)
  # Widget uses the real UI with an explicit fake native bridge; no Windows actions.
  widget=browser.new_page(viewport={'width':380,'height':500},reduced_motion='reduce');widget.on('pageerror',lambda e:errors.append(str(e)))
  widget.add_init_script('''window.bujjiDesktop={bootstrap:async()=>({origin:location.origin,token:"widget-test-only"}),onHidden:()=>()=>{},closeComputer:async()=>{},computer:async r=>r.operation==="info"?{routines:[],diagnostics:{ready:true}}:r.operation==="plan"?{plan_id:"test",summary:"Open Notepad",confirmation_required:!r.direct,actions:[{app:"Notepad",action:{op:"open_app"}}]}:r.operation==="execute"?{completed:true,plan_id:"test",results:[{detail:"Notepad opened (test only)"}]}:{windows:[],routines:[]}}''')
  widget.goto('http://127.0.0.1:'+str(port)+'/?computer=1');widget.get_by_text('Ready · say what you want to do',exact=True).wait_for();assert widget.locator('.widget-options').evaluate('(e)=>!e.open');assert widget.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth')
  widget.get_by_role('textbox',name='Computer command').fill('Open Notepad');widget.get_by_role('button',name='Run command',exact=True).click();widget.locator('.widget-results li').filter(has_text='Notepad opened (test only)').wait_for();assert widget.get_by_role('button',name='Yes, do it',exact=True).count()==0;widget.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-direct-widget.png'),full_page=True);assert widget.get_by_role('checkbox',name='Review commands before running',exact=True).count()==0
  assert not errors,errors
  browser.close()
 server.should_exit=True;thread.join(timeout=5)
print('PASS: refreshed desktop home/chat, 1380/750/393 width checks, no starter/routing sections or duplicate main controls, collapsed tools, compact widget and pending approval/cancel.')
