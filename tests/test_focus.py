import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from bujji.config import Settings
from bujji.main import create_app
from bujji import focus, providers


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(providers,'available',lambda:{'gemini':True,'groq':True,'ollama':False})
    for role,_ in focus.ROLES:
        monkeypatch.delenv(f'BUJJI_FOCUS_{role.upper()}_PROVIDER',raising=False)
    monkeypatch.setenv('BUJJI_DAILY_PROVIDER','gemini')
    app=create_app(Settings(token='focus-test-token-'*3,data=tmp_path/'data',files=tmp_path/'inbox'),background=False)
    return app


def test_focus_four_stages_and_atomic_conversation(setup,monkeypatch):
    calls=[]
    async def fake(messages,memories,task,provider,focused):
        calls.append((messages[-1]['content'],provider,focused))
        return {'text':f'artifact {len(calls)}','provider':provider,'model':'test-model'}
    monkeypatch.setattr(providers,'reply',fake)
    with TestClient(setup,headers={'Authorization':'Bearer '+'focus-test-token-'*3}) as client:
        response=client.post('/api/focus',json={'message':'Build a study plan','session':'focus-test'})
        events=[json.loads(line) for line in response.text.splitlines()]
        assert [e['role'] for e in events if e['type']=='stage' and e['status']=='complete']==['plan','build','review','revise']
        assert len(calls)==4 and all(c[1:] == ('gemini',True) for c in calls)
        assert 'artifact 2' in calls[2][0]
        assert 'artifact 3' in calls[3][0]
        assert events[-1]['type']=='result' and 'Not executed' in events[-1]['text']
        history=client.get('/api/messages?session=focus-test').json()
        assert len(history)==2 and history[-1]['content']==events[-1]['text']


def test_failed_stage_stops_and_does_not_save_false_success(setup,monkeypatch):
    calls=[]
    async def fake(*args):
        calls.append(1)
        if len(calls)==2:
            raise providers.ProviderError('Provider quota reached.')
        return {'text':'plan','model':'test','provider':'gemini'}
    monkeypatch.setattr(providers,'reply',fake)
    with TestClient(setup,headers={'Authorization':'Bearer '+'focus-test-token-'*3}) as client:
        response=client.post('/api/focus',json={'message':'test','session':'fail'})
        events=[json.loads(line) for line in response.text.splitlines()]
        assert len(calls)==2 and events[-1]['type']=='error'
        assert events[-2]['role']=='build' and events[-2]['status']=='failed'
        assert events[-2]['error']=='Provider quota reached.'
        assert client.get('/api/messages?session=fail').json()==[]
        # The failed run released its session lock.
        assert client.post('/api/focus',json={'message':'retry','session':'fail'}).status_code==200


def test_focus_preflight_auth_and_validation(setup,monkeypatch):
    monkeypatch.setenv('BUJJI_FOCUS_REVIEW_PROVIDER','ollama')
    with TestClient(setup) as client:
        assert client.post('/api/focus',json={'message':'test'}).status_code==401
        client.headers['Authorization']='Bearer '+'focus-test-token-'*3
        assert client.post('/api/focus',json={'message':'test'}).status_code==503
        assert client.post('/api/focus',json={'message':' '}).status_code==422
        assert client.post('/api/focus',json={'message':'test','provider':'unknown'}).status_code==422


def test_role_routes_and_manual_override(setup,monkeypatch):
    monkeypatch.setenv('BUJJI_FOCUS_BUILD_PROVIDER','groq')
    assert focus.routes('daily','auto')['build']=='groq'
    assert set(focus.routes('daily','gemini').values())=={'gemini'}


def test_cancellation_during_call_stops_later_roles(setup,monkeypatch):
    calls=[]
    cancelled=[]
    async def fake(*args):
        calls.append(1)
        try:
            await asyncio.sleep(30)
        finally:
            cancelled.append(True)
    monkeypatch.setattr(providers,'reply',fake)
    async def scenario():
        stream=focus.run('task',[],[])
        assert (await anext(stream))['role']=='plan'
        pending=asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        await stream.aclose()
    asyncio.run(scenario())
    assert len(calls)==1 and cancelled==[True]


def test_context_is_bounded_and_artifacts_are_untrusted(setup,monkeypatch):
    prompts=[]
    async def fake(messages,*args):
        prompts.append(messages)
        return {'text':'x'*20000,'model':'test','provider':'gemini'}
    monkeypatch.setattr(providers,'reply',fake)
    async def scenario():
        return [event async for event in focus.run('task',[{'role':'user','content':'old'}]*20,[])]
    events=asyncio.run(scenario())
    assert len(prompts[-1])==7
    assert len(prompts[-1][-1]['content'])<20000
    assert 'untrusted' in prompts[-1][-1]['content']
    assert len(events[-1]['text'])==12000


def test_deadline_stops_workflow_without_result(setup,monkeypatch):
    monkeypatch.setattr(focus,'DEADLINE_SECONDS',0.01)
    async def fake(*args):
        await asyncio.sleep(30)
    monkeypatch.setattr(providers,'reply',fake)
    async def scenario():
        with pytest.raises(providers.ProviderError,match='deadline'):
            async for _ in focus.run('task',[],[]):
                pass
    asyncio.run(scenario())


def test_http_disconnect_cancels_provider_and_releases_session(setup,monkeypatch):
    import socket
    import threading
    import time
    import httpx
    import uvicorn
    entered=threading.Event()
    cancelled=threading.Event()
    calls=[]
    async def slow(*args):
        calls.append(1)
        entered.set()
        try:
            await asyncio.sleep(30)
        finally:
            cancelled.set()
    monkeypatch.setattr(providers,'reply',slow)
    sock=socket.socket()
    sock.bind(('127.0.0.1',0))
    port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(setup,log_level='critical',lifespan='off'))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True)
    thread.start()
    try:
        deadline=time.monotonic()+5
        while not server.started and time.monotonic()<deadline:
            time.sleep(0.01)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers={'Authorization':'Bearer '+'focus-test-token-'*3},trust_env=False,timeout=5) as client:
            with client.stream('POST','/api/focus',json={'message':'task','session':'disconnect'}) as response:
                assert response.status_code==200
                assert json.loads(next(response.iter_lines()))['role']=='plan'
                assert entered.wait(1)
            assert cancelled.wait(2)
            async def fast(*args):
                return {'text':'done','model':'test','provider':'gemini'}
            monkeypatch.setattr(providers,'reply',fast)
            retried=client.post('/api/focus',json={'message':'retry','session':'disconnect'})
            assert retried.status_code==200
        assert len(calls)==1
    finally:
        server.should_exit=True
        thread.join(timeout=5)
        sock.close()
