import tempfile
import os
"""Run manually with Playwright/Chromium installed; temporary local backend only."""
import sys,tempfile,threading,socket,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from bujji.main import create_app
from bujji.config import Settings
from playwright.sync_api import sync_playwright
import uvicorn,httpx
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);token='pairing-ui-test-only-'*3;app=create_app(Settings(token=token,data=root/'data',files=root/'files'),background=False)
 app.state.store.set_state('profile',{'name':'Alex'})
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 server=uvicorn.Server(uvicorn.Config(app,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
 while not server.started:time.sleep(.05)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':1280,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.add_init_script('sessionStorage.setItem("bujji-token",'+repr(token)+')');page.goto('http://127.0.0.1:'+str(port));page.get_by_role('button',name='Devices',exact=True).click()
  page.get_by_role('button',name='Generate phone pairing code',exact=True).click();page.wait_for_timeout(200)
  code=app.state.devices.pending
  assert code and page.get_by_text('One-use code (10 minutes):',exact=False).is_visible()
  # Exchange displayed code through the real backend, then test list and revoke UI.
  import re
  text=page.get_by_text('One-use code (10 minutes):',exact=False).inner_text();value=re.search(r'\b[a-f0-9]{16}\b',text).group()
  r=httpx.post('http://127.0.0.1:'+str(port)+'/api/devices/pair',json={'code':value,'name':'Test phone'});assert r.status_code==200
  page.get_by_role('button',name='Refresh connected devices',exact=True).click();page.get_by_text('Test phone',exact=True).wait_for()
  with page.expect_response(lambda r:'/access' in r.url and r.request.method=='PUT') as saved:
   page.get_by_role('checkbox',name='Phone control',exact=True).check()
  assert saved.value.status==200
  with page.expect_response(lambda r:'/access' in r.url and r.request.method=='PUT') as saved:
   page.get_by_role('checkbox',name='Browse/download files',exact=True).check()
  assert saved.value.status==200
  device=r.json()['id'];assert app.state.remote.permission(device)=={'control':True,'files':True}
  page.wait_for_function("!document.querySelector('.paired-device button').disabled")
  page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-remote-device-grants.png'))
  with page.expect_response(lambda r:'/access' in r.url and r.request.method=='PUT') as saved:
   page.get_by_role('checkbox',name='Phone control',exact=True).uncheck()
  assert saved.value.status==200
  assert not app.state.remote.permission(device)['control']
  page.get_by_role('button',name='Revoke',exact=True).click();page.wait_for_timeout(200)
  assert app.state.devices.devices()==[]
  assert 'bhavana' not in page.locator('.devices-panel').inner_text().lower()
  assert not errors,errors
  page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-v02-pairing.png'))
  browser.close()
 server.should_exit=True;thread.join(timeout=5)
print('PASS desktop pairing UI against real API: code, pair, refresh list, revoke; neutral voice labels; no page errors')
