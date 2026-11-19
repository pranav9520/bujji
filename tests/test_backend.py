from datetime import datetime, timedelta, timezone
from pathlib import Path
import asyncio
import time
import httpx
import pytest
from fastapi.testclient import TestClient
from bujji.config import Settings
from bujji.main import create_app
from bujji.reminders import tick
from bujji import providers
from bujji.telegram import handle, authorized

TOKEN = 'test-pairing-token-' * 3


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name in ('GEMINI_API_KEY','GROQ_API_KEY','GEMINI_MODEL','GROQ_MODEL','OLLAMA_MODEL','TELEGRAM_BOT_TOKEN'):
        monkeypatch.delenv(name, raising=False)
    return create_app(Settings(token=TOKEN, data=tmp_path/'data', files=tmp_path/'inbox'), background=False)


@pytest.fixture
def client(app):
    with TestClient(app, headers={'Authorization': 'Bearer '+TOKEN}) as client:
        yield client


def test_auth_required_for_every_api(app):
    with TestClient(app) as client:
        for method, route in [('GET','/api/status'),('GET','/api/messages'),('GET','/api/memories'),('GET','/api/reminders'),('GET','/api/files?q=a'),('GET','/api/notifications'),('POST','/api/chat'),('POST','/api/files/request'),('POST','/api/files/a/confirm')]:
            assert client.request(method, route, json={'message':'hello','path':'a','confirmed':True}).status_code == 401


def test_startup_rejects_weak_token(tmp_path):
    with pytest.raises(RuntimeError):
        create_app(Settings(token='weak',data=tmp_path,files=tmp_path))


def test_memory_crud_dedup_and_persistence(client, app):
    memory = client.post('/api/memories',json={'content':'Prefer Telugu-English'}).json()
    assert client.post('/api/memories',json={'content':'prefer telugu-english'}).json()['id'] == memory['id']
    assert client.put(f"/api/memories/{memory['id']}",json={'content':'Prefer concise Telugu-English'}).status_code == 200
    rebuilt = create_app(Settings(token=TOKEN,data=Path(app.state.store.path).parent,files=Path(app.state.store.path).parent/'inbox'),background=False)
    with TestClient(rebuilt,headers={'Authorization':'Bearer '+TOKEN}) as other:
        assert other.get('/api/memories?q=concise').json()[0]['content']=='Prefer concise Telugu-English'
    assert client.delete(f"/api/memories/{memory['id']}").status_code==200
    assert client.get('/api/memories').json()==[]
    assert client.post('/api/memories',json={'content':'  '}).status_code==422


def test_no_fake_ai_success(client):
    r=client.post('/api/chat',json={'message':'hello'})
    assert r.status_code==503
    assert 'not configured' in r.json()['detail']
    assert client.get('/api/messages').json()==[]


def test_chat_routing_and_history(client, monkeypatch):
    observed={}
    async def fake(messages, memories, task, requested, focus):
        observed.update(task=task,provider=requested,focus=focus)
        return {'text':'Cheppu, let’s work through it.','provider':'groq','model':'test'}
    monkeypatch.setattr(providers,'reply',fake)
    r=client.post('/api/chat',json={'message':'Explain this code','task':'coding','provider':'groq','focus':True})
    assert r.status_code==200
    assert observed=={'task':'coding','provider':'groq','focus':True}
    assert [m['role'] for m in client.get('/api/messages').json()]==['user','assistant']
    assert client.get('/api/messages?session=other').json()==[]
    assert client.post('/api/chat',json={'message':'hey','task':'shell'}).status_code==422


def test_reminders_timezone_recovery_and_no_duplicate_delivery(client, app):
    future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    body={'title':'Java assignment','due':future,'recurrence':'none'}
    row=client.post('/api/reminders',json=body).json()
    assert client.post('/api/reminders',json=body).json()['id']==row['id']
    moment=datetime.fromisoformat(future)+timedelta(hours=2)
    tick(app.state.store,'Asia/Kolkata',moment)
    tick(app.state.store,'Asia/Kolkata',moment)
    n=client.get('/api/notifications').json()
    assert len(n)==1 and n[0]['content'].startswith('Missed while offline:')
    assert client.get('/api/reminders').json()[0]['status']=='delivered'
    assert client.post(f"/api/notifications/{n[0]['id']}/read").status_code==200
    assert client.get('/api/notifications').json()[0]['read']==1
    naive=client.post('/api/reminders',json={'title':'IST','due':'2099-01-01T19:00','recurrence':'weekly'}).json()
    assert naive['due'].endswith('13:30:00+00:00')
    assert client.post('/api/reminders',json={'title':'Past','due':'2000-01-01'}).status_code==422


def test_recurring_missed_occurrences_coalesce_and_cancel(client, app):
    future=datetime.now(timezone.utc)+timedelta(days=1)
    row=client.post('/api/reminders',json={'title':'Study','due':future.isoformat(),'recurrence':'daily'}).json()
    instant=future+timedelta(days=5,hours=1)
    tick(app.state.store,'Asia/Kolkata',instant)
    r=client.get('/api/reminders').json()[0]
    assert datetime.fromisoformat(r['due'])>instant
    assert len(client.get('/api/notifications').json())==1
    client.delete('/api/reminders/'+str(row['id']))
    tick(app.state.store,'Asia/Kolkata',instant+timedelta(days=20))
    assert len(client.get('/api/notifications').json())==1


def test_file_scoping_confirmation_and_replay(client, app):
    root=Path(app.state.store.path).parent.parent/'inbox'
    (root/'notes.txt').write_text('approved notes')
    assert client.get('/api/files?q=notes').json()[0]['path']=='notes.txt'
    assert client.get('/api/files?q=').status_code==422
    for path in ('../data/bujji.sqlite3','/etc/passwd','.env'):
        assert client.post('/api/files/request',json={'path':path}).status_code in (403,404)
    action=client.post('/api/files/request',json={'path':'notes.txt'}).json()['action_id']
    assert client.post('/api/files/'+action+'/confirm',json={'confirmed':True}).text=='approved notes'
    assert client.post('/api/files/'+action+'/confirm',json={'confirmed':True}).status_code==409


def test_file_symlink_expiry_reject_and_size(client, app, tmp_path):
    root=tmp_path/'inbox'
    (root/'ok.txt').write_text('ok')
    action=client.post('/api/files/request',json={'path':'ok.txt'}).json()['action_id']
    app.state.store.execute('UPDATE approvals SET expires=? WHERE id=?',(time.time()-1,action))
    assert client.post('/api/files/'+action+'/confirm',json={'confirmed':True}).status_code==409
    action=client.post('/api/files/request',json={'path':'ok.txt'}).json()['action_id']
    client.post('/api/files/'+action+'/confirm',json={'confirmed':False})
    assert client.post('/api/files/'+action+'/confirm',json={'confirmed':True}).status_code==409
    with (root/'big.bin').open('wb') as f:
        f.truncate(10*1024*1024+1)
    assert client.post('/api/files/request',json={'path':'big.bin'}).status_code==413


def test_symlinks_and_windows_stream_paths_are_blocked(client, tmp_path):
    root = tmp_path/'inbox'
    assert client.post('/api/files/request',json={'path':'ok.txt:secret'}).status_code==403
    assert client.post('/api/files/request',json={'path':'..\\secret.txt'}).status_code==403
    outside=tmp_path/'secret.txt';outside.write_text('secret')
    try:
        (root/'link.txt').symlink_to(outside)
    except OSError:
        pytest.skip('Creating symlinks needs Windows Developer Mode or appropriate OS permission')
    assert client.post('/api/files/request',json={'path':'link.txt'}).status_code==403


def test_telegram_only_accepts_allowlisted_private_owner_chats():
    private = {'from': {'id': 123}, 'chat': {'id': 123, 'type': 'private'}}
    assert authorized(private, {'123'})
    assert not authorized(private, set())
    assert not authorized({'from': {'id': 123}, 'chat': {'id': -1, 'type': 'group'}}, {'123'})
    assert not authorized({'from': {'id': 999}, 'chat': {'id': 123, 'type': 'private'}}, {'123'})


def test_telegram_commands_without_provider(app):
    store=app.state.store
    assert asyncio.run(handle('/remember I study CSE','1',store,'Asia/Kolkata'))=='Saved that memory.'
    assert 'CSE' in asyncio.run(handle('/memories','1',store,'Asia/Kolkata'))
    assert 'not configured' in asyncio.run(handle('hello','1',store,'Asia/Kolkata'))
    assert 'Usage:' in asyncio.run(handle('/remind bad','1',store,'Asia/Kolkata'))
    assert 'saved' in asyncio.run(handle('/remind 2099-01-01T19:00:00+05:30 | Test','1',store,'Asia/Kolkata'))
    row=store.rows('SELECT * FROM reminders')[0]
    assert asyncio.run(handle('/cancel '+str(row['id']),'1',store,'Asia/Kolkata'))=='Reminder cancelled.'


@pytest.mark.parametrize('provider',['gemini','groq','ollama'])
def test_provider_payloads_and_outputs(monkeypatch, provider):
    monkeypatch.setenv(provider.upper()+'_MODEL','test-model')
    monkeypatch.setenv(provider.upper()+'_API_KEY','secret')
    monkeypatch.setenv('OLLAMA_ENABLED','true')
    real=httpx.AsyncClient
    def respond(request):
        assert 'Bujji' in request.content.decode()
        if provider=='gemini':
            return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'Hello'}]}}]})
        if provider=='groq':
            return httpx.Response(200,json={'choices':[{'message':{'content':'Hello'}}]})
        return httpx.Response(200,json={'message':{'content':'Hello'}})
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond)))
    result=asyncio.run(providers.reply([{'role':'user','content':'Hello'}],[],requested=provider))
    assert result=={'text':'Hello','provider':provider,'model':'test-model'}


@pytest.mark.parametrize('status',[401,429,500])
def test_provider_errors_do_not_leak_keys_or_claim_success(monkeypatch,status):
    monkeypatch.setenv('GROQ_API_KEY','never-print-this-key');monkeypatch.setenv('GROQ_MODEL','test')
    real=httpx.AsyncClient
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'error':'never-print-this-key'}))))
    with pytest.raises(providers.ProviderError) as exc:
        asyncio.run(providers.reply([{'role':'user','content':'Hello'}],[],requested='groq'))
    assert 'never-print' not in str(exc.value)


@pytest.mark.parametrize('status,code,expected',[
    (400,'model_decommissioned','GROQ_MODEL'),
    (404,'model_not_found','GROQ_MODEL'),
    (400,'invalid_request_error','HTTP 400'),
    (413,None,'HTTP 413'),
    (502,None,'temporarily unavailable'),
])
def test_actionable_provider_errors_redact_response_bodies(monkeypatch,status,code,expected):
    monkeypatch.setenv('GROQ_API_KEY','secret-key');monkeypatch.setenv('GROQ_MODEL','wrong-model')
    real=httpx.AsyncClient
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'error':{'code':code,'message':'secret-key and private message'}}))))
    with pytest.raises(providers.ProviderError) as exc:
        asyncio.run(providers.reply([{'role':'user','content':'Hello'}],[],requested='groq'))
    assert expected in str(exc.value)
    assert 'secret-key' not in str(exc.value)
    assert 'private message' not in str(exc.value)


@pytest.mark.parametrize('failure,expected',[(httpx.ConnectError,'Could not connect securely'),(httpx.ReadTimeout,'timed out')])
def test_network_failures_are_distinguished(monkeypatch,failure,expected):
    monkeypatch.setenv('GROQ_API_KEY','secret-key');monkeypatch.setenv('GROQ_MODEL','test')
    real=httpx.AsyncClient
    def fail(request):
        raise failure('secret-key must not appear',request=request)
    monkeypatch.setattr(providers.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(fail)))
    with pytest.raises(providers.ProviderError) as exc:
        asyncio.run(providers.reply([{'role':'user','content':'Hello'}],[],requested='groq'))
    assert expected in str(exc.value)
    assert 'secret-key' not in str(exc.value)


def test_diagnostics_only_exposes_allowlisted_error_labels():
    from bujji.diagnostics import error_summary, model_id
    response=httpx.Response(400,json={'error':{'status':'INVALID_ARGUMENT','message':'private api key','details':[{'reason':'API_KEY_INVALID','metadata':{'key':'private'}},{'reason':'private-key'}]}})
    assert error_summary(response)=='HTTP 400 / INVALID_ARGUMENT / API_KEY_INVALID'
    assert error_summary(httpx.Response(500,text='private api key'))=='HTTP 500'
    assert model_id('gemini-2.5-flash')=='gemini-2.5-flash'
    assert model_id('not a model\nsecret')=='(blank or invalid model ID)'
