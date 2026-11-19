import time
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from bujji.main import create_app
from bujji.config import Settings
from bujji import speech
import httpx

MASTER='owner-private-token-'*3
@pytest.fixture
def app(tmp_path):
    return create_app(Settings(token=MASTER,data=tmp_path/'data',files=tmp_path/'files'),background=False)
@pytest.fixture
def client(app):
    with TestClient(app) as c: yield c

def owner():return {'Authorization':'Bearer '+MASTER}
def paired(c):
    code=c.post('/api/devices/pairing',headers=owner()).json()['code']
    r=c.post('/api/devices/pair',json={'code':code,'name':'Phone'})
    assert r.status_code==200,r.text
    return r.json(),{'Authorization':'Bearer '+r.json()['token']}
def exchange(c,h,changes=()):
    r=c.post('/api/devices/sync',headers=h,json={'changes':list(changes)})
    assert r.status_code==200,r.text
    return r.json()
def memory(text='Project context',key=None,revision=0,deleted=False):
    return {'id':key or str(uuid.uuid4()),'kind':'memory','revision':revision,'body':text,'deleted':deleted}
def test_phone_token_is_scoped_and_one_use(client):
    code=client.post('/api/devices/pairing',headers=owner()).json()['code']
    r=client.post('/api/devices/pair',json={'code':code,'name':'Phone'}).json();h={'Authorization':'Bearer '+r['token']}
    assert client.get('/api/devices/status',headers=h).status_code==200
    for path in ['/api/memories','/api/status','/api/messages','/api/devices','/api/work-focus']:
        assert client.get(path,headers=h).status_code==401
    assert client.post('/api/devices/pairing',headers=h).status_code==401
    assert client.post('/api/devices/pair',json={'code':code,'name':'Phone'}).status_code==403
    assert client.get('/api/devices',headers=owner()).json()[0]['id']==r['id']
    assert 'token' not in client.get('/api/devices',headers=owner()).text
    client.delete('/api/devices/'+r['id'],headers=owner())
    assert client.get('/api/devices/status',headers=h).status_code==401
    assert client.post('/api/devices/sync',headers=h,json={'changes':[]}).status_code==401

def test_pair_code_attempt_lock_expiry_and_restart(app,client):
    code=client.post('/api/devices/pairing',headers=owner()).json()['code']
    for _ in range(5):assert client.post('/api/devices/pair',json={'code':'0'*16,'name':'Phone'}).status_code==403
    assert client.post('/api/devices/pair',json={'code':code,'name':'Phone'}).status_code==403
    code=client.post('/api/devices/pairing',headers=owner()).json()['code'];app.state.devices.pending['expires']=time.time()-1
    assert client.post('/api/devices/pair',json={'code':code,'name':'Phone'}).status_code==403

def test_memory_phone_to_laptop_laptop_edits_and_tombstones(client):
    _,h=paired(client);m=memory();r=exchange(client,h,[m]);record=r['records'][0]
    laptop=client.get('/api/memories',headers=owner()).json()[0]
    assert laptop['content']==m['body']
    client.put('/api/memories/'+str(laptop['id']),headers=owner(),json={'content':'Updated on laptop'})
    updated=exchange(client,h)['records'][0];assert updated['revision']>record['revision']
    assert updated['payload']['body']=='Updated on laptop'
    client.delete('/api/memories/'+str(laptop['id']),headers=owner())
    removed=exchange(client,h)['records'][0];assert removed['payload']['deleted'] is True
    assert exchange(client,h)['records'][0]['revision']==removed['revision']

def test_stale_phone_does_not_overwrite_laptop(client):
    _,h=paired(client);m=memory();r=exchange(client,h,[m]);revision=r['records'][0]['revision']
    laptop=client.get('/api/memories',headers=owner()).json()[0]
    client.put('/api/memories/'+str(laptop['id']),headers=owner(),json={'content':'Laptop wins'})
    result=exchange(client,h,[memory('Offline phone edit',m['id'],revision)])
    assert result['results']==[{'id':m['id'],'status':'conflict'}]
    assert result['records'][0]['payload']['body']=='Laptop wins'

def test_duplicate_content_and_retry_are_idempotent(client):
    _,h=paired(client)
    client.post('/api/memories',headers=owner(),json={'content':'Already here'})
    m=memory('Already here');r=exchange(client,h,[m]);assert r['results'][0]['status']=='duplicate'
    assert r['results'][0]['remote_id']==r['records'][0]['id']
    m=memory('New fact');r=exchange(client,h,[m]);retry=exchange(client,h,[m]);assert retry['results'][0]['status']=='conflict'
    assert len(client.get('/api/memories',headers=owner()).json())==2

def test_shared_reminder_and_scheduler_state(client,app):
    from bujji.reminders import tick
    _,h=paired(client);due=int((datetime.now(timezone.utc)+timedelta(minutes=10)).timestamp()*1000)
    change={'id':str(uuid.uuid4()),'kind':'reminder','revision':0,'title':'Study','due':due,'repeat':'none','status':'pending'}
    r=exchange(client,h,[change]);assert client.get('/api/reminders',headers=owner()).json()[0]['title']=='Study'
    tick(app.state.store,'Asia/Kolkata',datetime.fromtimestamp(due/1000,timezone.utc)+timedelta(seconds=1))
    r=exchange(client,h);assert r['records'][0]['payload']['status']=='done'

def test_cancelled_reminder_sync_and_transaction_rollback(client):
    _,h=paired(client);due=int((datetime.now(timezone.utc)+timedelta(minutes=10)).timestamp()*1000)
    change={'id':str(uuid.uuid4()),'kind':'reminder','revision':0,'title':'Study','due':due,'repeat':'daily','status':'pending'}
    r=exchange(client,h,[change]);change['revision']=r['records'][0]['revision'];change['status']='cancelled';exchange(client,h,[change]);assert client.get('/api/reminders',headers=owner()).json()[0]['status']=='cancelled'
    r=client.post('/api/devices/sync',headers=h,json={'changes':[memory('Must roll back'),memory('   ')]});assert r.status_code==422
    assert client.get('/api/memories',headers=owner()).json()==[]

def test_validation_auth_and_no_extra_capabilities(client):
    assert client.post('/api/devices/sync',json={'changes':[]}).status_code==401
    _,h=paired(client)
    assert client.post('/api/devices/sync',headers=h,json={'changes':[{'id':str(uuid.uuid4()),'kind':'shell','revision':0}]}).status_code==422
    assert client.post('/api/devices/sync',headers=h,json={'changes':[],'command':'anything'}).status_code==422

def test_microphone_transcription_retries_transient_once(monkeypatch):
    import asyncio
    monkeypatch.setenv('BUJJI_STT_PROVIDER','gemini');monkeypatch.setenv('GEMINI_API_KEY','secret');monkeypatch.setenv('GEMINI_MODEL','gemini-test')
    real=httpx.AsyncClient;calls=[]
    def reply(request):
        calls.append(request)
        return httpx.Response(503) if len(calls)==1 else httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{"text":"Hello"}'}]}}]})
    monkeypatch.setattr(speech.httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(reply)))
    assert asyncio.run(speech.transcribe(b'audio','audio/webm','en-IN'))['text']=='Hello'
    assert len(calls)==2
