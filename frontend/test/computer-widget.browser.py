import tempfile
import os
"""Optional browser smoke test, with an explicitly fake Electron/native bridge.
Run after npm --prefix frontend run build, with playwright and Chromium installed.
This does NOT validate actual Windows input or Electron packaging.
"""
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading
from playwright.sync_api import sync_playwright

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

root=Path(__file__).resolve().parents[1]/'dist'
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(root)))
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'),headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':420,'height':760});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script('''
        window.__calls=[];window.__held=null;
        window.bujjiDesktop={
          bootstrap:async()=>({token:'test-only',origin:location.origin}),
          onHidden:()=>()=>{},closeComputer:async()=>({closed:true}),
          computer:async body=>{
            window.__calls.push(body);
            if(body.operation==='diagnostics')return {code:'invalid_json',operation:'snapshot'};
            if(body.operation==='status'&&window.__failScan)throw new Error("Error invoking remote method 'bujji:computer': Error: The Windows helper returned unreadable data (invalid_json).");
            if(body.operation==='status')return {windows:[{id:'10',exe:'notepad.exe',title:'Notes'}],target:'10',routines:[]};
            if(body.operation==='stop')return {stopped:true};
            if(body.operation==='plan') {
              if(body.message==='slow')return await new Promise(resolve=>window.__held=resolve);
              if(body.message==='what is on my screen')return {summary:'Read selected app text first.',actions:[]};
              return {plan_id:'p1',summary:'Requested control',confirmation_required:body.message==='close window',actions:[{action:{op:'window',command:body.message==='close window'?'close':'left'},target:'Notes',app:'notepad.exe'}]};
            }
            if(body.operation==='execute')return {completed:true,plan_id:'p1',results:[{detail:'Observed mocked window result.'}]};
            return {};
          }
        };
        ''')
        page.goto(f'http://127.0.0.1:{server.server_port}/?computer=1')
        page.get_by_text('Ready · say what you want to do',exact=True).wait_for()
        assert page.evaluate("window.__calls.filter(x=>x.operation==='status').length")==0
        assert page.locator('select').input_value()==''
        page.evaluate('window.__failScan=true')
        page.get_by_role('button',name='Refresh open apps',exact=True).click()
        page.get_by_role('alert').wait_for()
        assert 'remote method' not in page.get_by_role('alert').inner_text()
        assert page.get_by_role('button',name='Listen',exact=True).is_enabled()
        page.evaluate('window.__failScan=false')
        text=page.get_by_role('textbox',name='Computer command')
        text.fill('move notepad left');page.get_by_role('button',name='Run command',exact=True).click()
        page.get_by_role('listitem').filter(has_text='Observed mocked window result.').wait_for()
        assert len(page.evaluate("window.__calls.filter(x=>x.operation==='execute')"))==1
        text.fill('close window');page.get_by_role('button',name='Run command',exact=True).click()
        page.get_by_role('button',name='Approve',exact=True).wait_for()
        assert len(page.evaluate("window.__calls.filter(x=>x.operation==='execute')"))==1
        page.screenshot(path=str(Path(tempfile.gettempdir())/'bujji-computer-widget.png'),full_page=True)
        page.get_by_role('button',name='Approve',exact=True).click()
        page.get_by_role('listitem').filter(has_text='Observed mocked window result.').wait_for()
        assert page.evaluate("window.__calls.filter(x=>x.operation==='execute').at(-1).confirmed") is True
        text.fill('slow');page.get_by_role('button',name='Run command',exact=True).click()
        page.wait_for_function('window.__held!==null')
        page.get_by_role('button',name='Stop / pause',exact=True).click()
        page.evaluate("window.__held({plan_id:'late',summary:'stale',confirmation_required:false,actions:[{action:{op:'open_app',app:'anything'}}]})")
        page.wait_for_timeout(100)
        assert len(page.evaluate("window.__calls.filter(x=>x.operation==='execute')"))==2
        assert page.get_by_role('button',name='Approve',exact=True).count()==0
        before=page.evaluate("window.__calls.filter(x=>x.operation==='plan').length")
        text.fill('stop');page.get_by_role('button',name='Run command',exact=True).click()
        page.get_by_text('Stopped / cancelled',exact=True).wait_for()
        assert page.evaluate("window.__calls.filter(x=>x.operation==='plan').length")==before
        assert not errors,errors
        browser.close()
        print('Browser smoke passed: rendering, automatic low-risk dispatch, approval gate, Stop and late-plan rejection. Native bridge was mocked.')
finally:server.shutdown()
