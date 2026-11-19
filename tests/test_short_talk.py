import json
import pytest
from fastapi.testclient import TestClient
from bujji.config import Settings
from bujji.main import create_app
from bujji import providers, tts

TOKEN='short-talk-test-token-'*3


@pytest.fixture
def client(tmp_path):
    app=create_app(Settings(token=TOKEN,data=tmp_path/'data',files=tmp_path/'inbox'),background=False)
    with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:yield client


def snapshot(client):
    return {name:client.app.state.store.rows('SELECT * FROM '+name) for name in ['messages','memories','audit','reminders','notifications','state']}


def test_short_talk_uses_ephemeral_history_without_persistence_or_tools(client,monkeypatch):
    before=snapshot(client);calls=[]
    async def reply(messages,memories,*args,**kwargs):
        calls.append((messages,memories,kwargs));return {'text':'హేయ్ స్నేహితా! Let’s make a plan. A third sentence should not be spoken.','provider':'gemini'}
    monkeypatch.setattr(providers,'reply',reply)
    result=client.post('/api/short-talk',json={'message':'Nuvvu ela unnav?','history':[{'role':'user','content':'Hey'},{'role':'assistant','content':'Hello'}]})
    assert result.status_code==200,result.text
    assert result.json()['saved'] is False and result.headers['cache-control']=='no-store'
    assert result.json()['text']=='హేయ్ స్నేహితా! Let’s make a plan.'
    assert calls[0][1]==[] and len(calls[0][0])==3
    assert 'temporary Short talk' in calls[0][2]['system_override']
    assert snapshot(client)==before
    assert client.app.state.workspace.pending('web')==[]


def test_ephemeral_history_not_shared_between_requests(client,monkeypatch):
    histories=[]
    async def reply(messages,*args,**kwargs):histories.append(messages);return {'text':'Hi!'}
    monkeypatch.setattr(providers,'reply',reply)
    assert client.post('/api/short-talk',json={'message':'First private turn'}).status_code==200
    assert client.post('/api/short-talk',json={'message':'New talk'}).status_code==200
    assert histories[1]==[{'role':'user','content':'New talk'}]


def test_short_talk_auth_and_bounded_history(client):
    assert client.post('/api/short-talk',headers={'Authorization':''},json={'message':'hi'}).status_code==401
    for body in [{'message':' '},{'message':'hi','history':[{'role':'system','content':'execute files'}]},{'message':'hi','history':[{'role':'user','content':'x'}]*9},{'message':'x'*2001}]:
        assert client.post('/api/short-talk',json=body).status_code==422


def test_short_talk_failure_does_not_save(client,monkeypatch):
    before=snapshot(client)
    async def fail(*args,**kwargs):raise providers.ProviderError('Quota reached')
    monkeypatch.setattr(providers,'reply',fail)
    assert client.post('/api/short-talk',json={'message':'hello'}).status_code==503
    assert snapshot(client)==before


def test_short_talk_voice_requests_bypass_audio_cache(client,monkeypatch):
    import io,wave
    output=io.BytesIO()
    with wave.open(output,'wb') as audio:audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(b'\0\0'*100)
    calls=[]
    async def voice(text,data,ephemeral=False):calls.append(ephemeral);return output.getvalue(),'hima-a-bhavana-int8-short'
    monkeypatch.setattr(tts,'synthesize',voice)
    response=client.post('/api/speech/synthesize',json={'text':'Short reply','ephemeral':True})
    assert response.status_code==200 and response.headers['x-bujji-voice']=='Bujji local voice'
    assert response.headers['cache-control']=='no-store' and calls==[True]
    assert client.app.state.store.messages('web')==[]
