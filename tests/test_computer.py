import asyncio
import copy
import json
import time
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from bujji.computer import Computer
from bujji.computer_protocol import Action, ComputerRequest, ControlError, requires_confirmation
from bujji.config import Settings
from bujji.main import create_app
from bujji.store import Store
from bujji import providers

SNAP={'apps':[{'id':'app1','name':'Notepad'}],'windows':[{'id':'10','pid':12,'exe':'notepad.exe','title':'Notes'},{'id':'20','pid':13,'exe':'chrome.exe','title':'Browser'}],'target':'20','controls':[]}

@pytest.fixture
def controller(tmp_path,monkeypatch):
    value=Computer(Store(tmp_path/'db.sqlite3'));calls=[]
    async def native(body):
        calls.append(body)
        return copy.deepcopy(SNAP) if body['op']=='snapshot' else {'apps':copy.deepcopy(SNAP['apps'])} if body['op']=='catalog' else {'detail':'Observed test result'}
    monkeypatch.setattr(value,'native',native)
    return value,calls

def req(**kwargs):return ComputerRequest(**kwargs)

def test_native_secret_is_required_even_with_pairing_token(tmp_path,monkeypatch):
    monkeypatch.setenv('BUJJI_COMPUTER_TOKEN','native-secret')
    app=create_app(Settings(token='x'*40,data=tmp_path/'data',files=tmp_path/'inbox'),background=False)
    with TestClient(app,headers={'Authorization':'Bearer '+'x'*40}) as client:
        assert client.post('/api/computer',json={'operation':'stop'}).status_code==403
        assert client.post('/api/computer',json={'operation':'stop'},headers={'X-Bujji-Computer':'wrong'}).status_code==403
        assert client.post('/api/computer',json={'operation':'stop'},headers={'X-Bujji-Computer':'native-secret'}).json()['stopped']
        assert client.post('/api/computer',json={'operation':'stop'},headers={'Authorization':'','X-Bujji-Computer':'native-secret'}).status_code==401

def test_actions_cannot_supply_shell_paths_arbitrary_hotkeys_or_credentials():
    for body in [dict(op='shell',text='cmd /c anything'),dict(op='open_app',app='app1',path='cmd.exe'),dict(op='browser',window='20',command='ctrl+enter'),dict(op='open_url',url='file:///C:/Windows/cmd.exe'),dict(op='open_url',url='javascript:alert(1)'),dict(op='open_url',url='https://user:pass@example.com'),dict(op='type_text',window='10',control='field',text='abc\x00')]:
        with pytest.raises((ValidationError,ValueError)):Action.model_validate(body)
    assert requires_confirmation(Action(op='type_text',window='10',control='field',text='hello'))
    assert requires_confirmation(Action(op='window',window='10',command='close'))
    assert requires_confirmation(Action(op='browser',window='20',command='close_tab'))
    assert not requires_confirmation(Action(op='open_url',url='https://example.com'))

def test_simple_commands_skip_ai_and_plan_execute_once(controller,monkeypatch):
    computer,calls=controller
    async def forbidden(*args,**kwargs):pytest.fail('Fast commands must not use AI')
    monkeypatch.setattr(providers,'reply',forbidden)
    async def check():
        plan=await computer.request(req(operation='plan',message='Open Notepad'))
        assert plan['actions'][0]['app']=='Notepad' and not plan['confirmation_required']
        assert not any(c['op']=='act' for c in calls)
        result=await computer.request(req(operation='execute',plan_id=plan['plan_id']))
        assert result['completed']
        with pytest.raises(ControlError):await computer.request(req(operation='execute',plan_id=plan['plan_id']))
        assert len([c for c in calls if c['op']=='act'])==1
        fast=await computer.request(req(operation='plan',message='put Chrome on the left'))
        assert fast['actions'][0]['action']['command']=='left'
    asyncio.run(check())

def test_close_needs_confirmation_and_expiry_blocks_execution(controller):
    computer,calls=controller
    async def check():
        plan=await computer.request(req(operation='plan',message='close tab'))
        with pytest.raises(ControlError,match='Approve'):await computer.request(req(operation='execute',plan_id=plan['plan_id']))
        assert not any(c['op']=='act' for c in calls)
        computer.pending[plan['plan_id']]['expires']=time.monotonic()-1
        with pytest.raises(ControlError,match='expired'):await computer.request(req(operation='execute',plan_id=plan['plan_id'],confirmed=True))
    asyncio.run(check())

def test_invented_targets_and_invalid_json_never_run(controller,monkeypatch):
    computer,calls=controller
    async def check():
        for response in ['not json',json.dumps({'summary':'bad','actions':[{'op':'window','window':'invented','command':'close'}]})]:
            async def model(*args,**kwargs):return {'text':response}
            monkeypatch.setattr(providers,'reply',model)
            with pytest.raises(ControlError):await computer.request(req(operation='plan',message='do something complicated'))
        assert not any(c['op']=='act' for c in calls)
    asyncio.run(check())

def test_screen_text_is_opt_in_and_stays_out_of_saved_history(controller,monkeypatch):
    computer,calls=controller;seen=[]
    async def model(messages,memories,**kwargs):
        seen.append((messages,kwargs));return {'text':json.dumps({'summary':'Please enable reading the target app first.','actions':[]})}
    monkeypatch.setattr(providers,'reply',model)
    asyncio.run(computer.request(req(operation='plan',message='What is on my screen?')))
    assert next(call for call in calls if call['op']=='snapshot')['read'] is False
    assert computer.store.messages('web')==[]
    assert 'untrusted data' in seen[0][1]['system_override']

def test_stop_invalidates_inflight_model_reply(controller,monkeypatch):
    computer,calls=controller
    async def check():
        entered=asyncio.Event();release=asyncio.Event()
        async def model(*args,**kwargs):entered.set();await release.wait();return {'text':json.dumps({'summary':'open','actions':[{'op':'open_app','app':'app1'}]})}
        monkeypatch.setattr(providers,'reply',model)
        task=asyncio.create_task(computer.request(req(operation='plan',message='Please do this task')))
        await entered.wait();computer.stop();release.set()
        with pytest.raises(ControlError,match='stopped'):await task
        assert not computer.pending and not computer.busy and not any(c['op']=='act' for c in calls)
    asyncio.run(check())

def test_partial_failure_reports_completed_steps_and_stops(controller,monkeypatch):
    computer,calls=controller
    async def model(*args,**kwargs):return {'text':json.dumps({'summary':'three','actions':[{'op':'open_app','app':'app1'}]*3})}
    monkeypatch.setattr(providers,'reply',model)
    count=0
    async def native(body):
        nonlocal count
        if body['op']=='snapshot':return copy.deepcopy(SNAP)
        if body['op']=='catalog':return {'apps':copy.deepcopy(SNAP['apps'])}
        count+=1
        if count==2:raise ControlError('Target changed')
        return {'detail':'First app opened'}
    monkeypatch.setattr(computer,'native',native)
    async def check():
        plan=await computer.request(req(operation='plan',message='three apps please'))
        result=await computer.request(req(operation='execute',plan_id=plan['plan_id']))
        assert not result['completed'] and len(result['results'])==2 and count==2
        assert result['results'][0]['detail']=='First app opened' and computer.last is None
    asyncio.run(check())

def test_routines_persist_and_rebind_current_window_ids(controller,tmp_path):
    computer,calls=controller
    async def check():
        plan=await computer.request(req(operation='plan',message='put Chrome on the left'))
        await computer.request(req(operation='execute',plan_id=plan['plan_id']))
        with pytest.raises(ControlError):await computer.request(req(operation='save_routine',plan_id=plan['plan_id'],name='study'))
        await computer.request(req(operation='save_routine',plan_id=plan['plan_id'],name='study',confirmed=True))
        restored=Computer(Store(computer.store.path))
        async def new_snapshot(body):
            snapshot=copy.deepcopy(SNAP)
            snapshot['windows'][1]['id']='30';snapshot['target']='30'
            return snapshot
        restored.native=new_snapshot
        current=await restored.request(req(operation='plan',message='run study'))
        assert current['actions'][0]['action']['window']=='30'
        assert restored.store.messages('web')==[]
    asyncio.run(check())

def test_native_rejects_changed_or_terminal_targets_and_wrong_foreground():
    from bujji.computer_native import Windows
    native=Windows.__new__(Windows)
    native.describe=lambda hwnd:{'id':'10','pid':99,'exe':'notepad.exe'}
    with pytest.raises(ControlError,match='changed'):native.check({'id':'10','pid':12,'exe':'notepad.exe'})
    native.describe=lambda hwnd:{'id':'10','pid':12,'exe':'powershell.exe'}
    with pytest.raises(ControlError,match='excluded'):native.check({'id':'10','pid':12,'exe':'powershell.exe'})
    native.describe=lambda hwnd:{'id':'10','pid':12,'exe':'notepad.exe'}
    class User:
        def IsIconic(self,hwnd):return False
        def SetForegroundWindow(self,hwnd):pass
        def GetForegroundWindow(self):return 20
    native.u=User()
    class Fn:
        def __init__(self,value):self.value=value
        def __call__(self,*args):return self.value
    class Kernel:GetCurrentThreadId=Fn(1)
    class Types:DWORD=int;BOOL=bool
    native.W=Types;native.k=Kernel()
    native.u.GetWindowThreadProcessId=Fn(1);native.u.AttachThreadInput=Fn(True)
    with pytest.raises(ControlError,match='focus'):native.focus({'id':'10','pid':12,'exe':'notepad.exe'})

def test_control_identity_and_sensitive_buttons_are_rechecked():
    from bujji.computer_native import Windows
    native=Windows.__new__(Windows)
    saved={'rid':[1,2],'name':'Send','kind':'ButtonControl'}
    native.controls=lambda bound:[saved]
    with pytest.raises(ControlError,match='not supported'):native.current_control({},saved)
    native.controls=lambda bound:[{**saved,'rid':[1,3]}]
    with pytest.raises(ControlError,match='changed'):native.current_control({},saved)

def test_native_process_cancellation_kills_worker_and_drops_keys(controller,monkeypatch):
    computer,_=controller;computer.native=Computer.native.__get__(computer,Computer)
    monkeypatch.setenv('GEMINI_API_KEY','do-not-forward');seen={}
    async def check():
        entered=asyncio.Event()
        class Process:
            returncode=None;killed=False
            async def communicate(self,body):entered.set();await asyncio.sleep(30)
            def kill(self):self.killed=True;self.returncode=-9
            async def wait(self):return self.returncode
        process=Process()
        async def spawn(*args,**kwargs):seen.update(kwargs);return process
        monkeypatch.setattr(asyncio,'create_subprocess_exec',spawn)
        task=asyncio.create_task(computer.native({'op':'snapshot'}));await entered.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert process.killed and computer.process is None
        assert 'GEMINI_API_KEY' not in seen['env'] and 'shell' not in seen
    asyncio.run(check())

def test_close_reload_guard_rejects_changed_document_title():
    from bujji.computer_native import Windows
    native=Windows.__new__(Windows)
    native.describe=lambda hwnd:{'id':'10','pid':12,'exe':'notepad.exe','title':'Different unsaved document'}
    saved={'id':'10','pid':12,'exe':'notepad.exe','title':'Approved document'}
    assert native.check(saved)==10
    with pytest.raises(ControlError,match='changed since approval'):native.check(saved,strict_title=True)

def test_open_website_and_widget_info_do_not_scan_windows_or_apps(controller):
    computer,calls=controller
    async def check():
        assert (await computer.request(req(operation='info')))['routines']==[]
        plan=await computer.request(req(operation='plan',message='Open YouTube'))
        assert plan['actions'][0]['action']['url']=='https://www.youtube.com' and not calls
        result=await computer.request(req(operation='execute',plan_id=plan['plan_id']))
        assert result['completed'] and [x['op'] for x in calls]==['act']
    asyncio.run(check())

def test_open_app_needs_catalog_but_no_window_choice_or_scan(controller):
    computer,calls=controller
    async def check():
        plan=await computer.request(req(operation='plan',message='open notepad'))
        assert plan['actions'][0]['app']=='Notepad'
        assert [x['op'] for x in calls]==['catalog']
    asyncio.run(check())

def test_browser_command_auto_selects_only_browser_but_respects_override(controller):
    computer,_=controller
    snapshot=copy.deepcopy(SNAP);snapshot['target']='10'
    assert computer.fast('new tab',snapshot).actions[0].window=='20'
    snapshot['manual_target']=True
    assert computer.fast('new tab',snapshot) is None

def test_auto_target_prefers_named_app_and_manual_override():
    from bujji.computer_targets import choose
    windows=copy.deepcopy(SNAP['windows'])
    assert choose(windows,'20',message='Type a greeting in Notepad')['id']=='10'
    assert choose(windows,'20',manual='20',message='notepad')['id']=='20'
    assert choose(windows,'20',manual='closed-window') is None
    assert choose(windows,'20',message='what is on my screen')['id']=='20'

def test_native_snapshot_does_not_scan_installed_apps_when_disabled(monkeypatch):
    from bujji import computer_native
    native=computer_native.Windows.__new__(computer_native.Windows)
    native.windows=lambda:[]
    native.u=type('User',(),{'GetForegroundWindow':lambda self:0})()
    monkeypatch.setattr(computer_native,'app_catalog',lambda:pytest.fail('Startup windows refresh must not walk the Start menu'))
    assert native.snapshot('',False,catalog=False)['apps']==[]

def test_helper_framing_accepts_startup_noise_and_keeps_diagnostics_private():
    from bujji.computer_wire import encode,decode,last_diagnostic,WireError
    result={'windows':[{'title':'A Unicode window \u0c2a'}]}
    raw=b'library startup notice without a newline'+encode(result)
    assert decode(raw)==result
    assert decode(b'{"legacy":true}')=={'legacy':True}
    with pytest.raises(WireError,match='invalid_json'):decode(b'not a JSON response')
    with pytest.raises(WireError,match='invalid_result'):decode(b'[]')
    safe=last_diagnostic(b'private path and key\nBUJJI_COMPUTER_DIAG:{"phase":"catalog","error_type":"PermissionError","private":"never return"}\n')
    assert safe=={'phase':'catalog','error_type':'PermissionError'}

def test_native_reports_protocol_error_separately_from_timeout(controller,monkeypatch):
    computer,_=controller;computer.native=Computer.native.__get__(computer,Computer)
    class Process:
        returncode=0
        async def communicate(self,body):return b'bad startup response',b'private diagnostic noise'
    async def spawn(*args,**kwargs):return Process()
    monkeypatch.setattr(asyncio,'create_subprocess_exec',spawn)
    with pytest.raises(ControlError,match='unreadable data'):asyncio.run(computer.native({'op':'snapshot'}))
    assert computer.worker_health['code']=='invalid_json' and 'private' not in json.dumps(computer.worker_health)
    class TimeoutProcess:
        returncode=None;killed=False
        async def communicate(self,body):raise TimeoutError()
        def kill(self):self.killed=True;self.returncode=-9
        async def wait(self):return self.returncode
    process=TimeoutProcess()
    async def timeout_spawn(*args,**kwargs):return process
    monkeypatch.setattr(asyncio,'create_subprocess_exec',timeout_spawn)
    with pytest.raises(ControlError,match='time limit'):asyncio.run(computer.native({'op':'snapshot'}))
    assert computer.worker_health['code']=='timeout' and process.killed

def test_source_helper_emits_valid_frame_even_for_unsupported_platform():
    import subprocess,sys
    from bujji.computer_wire import decode
    if sys.platform=='win32':pytest.skip('Real Windows actions are tested manually on the device')
    process=subprocess.run([sys.executable,'-m','bujji.computer_native'],input=b'{"op":"snapshot"}',capture_output=True,timeout=15)
    assert process.returncode==0 and 'Windows desktop' in decode(process.stdout)['error']

def test_catalog_scan_is_bounded_and_does_not_follow_directory_links(tmp_path,monkeypatch):
    from bujji.computer_native import app_catalog
    root=tmp_path/'profile';programs=root/'Microsoft/Windows/Start Menu/Programs';programs.mkdir(parents=True)
    for number in range(210):(programs/f'Example App {number}.lnk').touch()
    (programs/'recursive-link').symlink_to(programs,target_is_directory=True)
    monkeypatch.setenv('APPDATA',str(root));monkeypatch.setenv('PROGRAMDATA',str(tmp_path/'empty'));monkeypatch.setenv('SYSTEMROOT',str(tmp_path/'empty-windows'))
    apps=app_catalog()
    assert len(apps)==180 and all('recursive-link' not in x['path'] for x in apps)

def test_direct_control_runs_allowed_close_without_per_action_approval(controller):
    computer,calls=controller
    async def check():
        plan=await computer.request(req(operation='plan',message='close tab',direct=True))
        assert plan['confirmation_required'] is False
        result=await computer.request(req(operation='execute',plan_id=plan['plan_id'],confirmed=False))
        assert result['completed']
        assert any(c['op']=='act' for c in calls)
        with pytest.raises(ControlError):await computer.request(req(operation='execute',plan_id=plan['plan_id']))
    asyncio.run(check())
