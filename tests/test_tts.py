import asyncio
import base64
import io
import json
import socket
import threading
import time
import wave
import httpx
import pytest
from fastapi.testclient import TestClient
from bujji.config import Settings
from bujji.main import create_app
from bujji import tts

TOKEN='tts-test-pairing-'*3


def wav():
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(b'\x00\x01'*100)
    return buffer.getvalue()


@pytest.fixture
def client(tmp_path,monkeypatch):
    tts._audio_cache.clear(); tts._cooldowns.clear(); tts._active_accounts.clear()
    monkeypatch.setenv('BUJJI_TTS_PROVIDER','gemini')
    monkeypatch.setenv('GEMINI_API_KEY','private-key')
    monkeypatch.delenv('GEMINI_TTS_MODEL',raising=False)
    app=create_app(Settings(token=TOKEN,data=tmp_path/'data',files=tmp_path/'inbox'),background=False)
    with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:
        yield client


def test_tts_auth_validation_and_audio_csp(client):
    assert client.post('/api/speech/synthesize',headers={'Authorization':''},json={'text':'Hello'}).status_code==401
    for text in ('','  ','x'*2001):
        assert client.post('/api/speech/synthesize',json={'text':text}).status_code==422
    assert "media-src 'self' blob:" in client.get('/api/status').headers['content-security-policy']


def test_tts_uses_approved_b_profile_and_same_audition_model(client,tmp_path,monkeypatch):
    folder=tmp_path/'data'/'voice-previews'/'20261117-000000'
    folder.mkdir(parents=True)
    (folder/'audition.json').write_text(json.dumps({'model':'gemini-3.1-flash-tts-preview','completed':['A','B','C']}))
    real=httpx.AsyncClient
    def respond(request):
        assert 'gemini-3.1-flash-tts-preview' in str(request.url)
        payload=json.loads(request.content)
        assert payload['generationConfig']['speechConfig']['voiceConfig']['prebuiltVoiceConfig']['voiceName']=='Aoede'
        assert tts.BASE_STYLE+' '+tts.PROFILES['B']['style'] in payload['contents'][0]['parts'][0]['text']
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'inlineData':{'mimeType':'audio/wav','data':base64.b64encode(wav()).decode()}}]}}]})
    monkeypatch.setattr(tts.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond)))
    result=client.post('/api/speech/synthesize',json={'text':'హే స్నేహితా! Ready?'})
    assert result.status_code==200 and result.content==wav()
    assert result.headers['x-bujji-voice']=='Aoede'
    assert result.headers['x-bujji-tts-model']=='gemini-3.1-flash-tts-preview'
    assert result.headers['content-type']=='audio/wav'
    assert client.get('/api/messages').json()==[]


def test_model_manifest_fallback_and_override(tmp_path,monkeypatch):
    monkeypatch.delenv('GEMINI_TTS_MODEL',raising=False)
    folder=tmp_path/'voice-previews'/'latest';folder.mkdir(parents=True)
    (folder/'audition.json').write_text('not json')
    assert tts.selected_model(tmp_path)==tts.MODELS[0]
    monkeypatch.setenv('GEMINI_TTS_MODEL','gemini-3.8-flash-lite-tts')
    assert tts.selected_model(tmp_path)=='gemini-3.8-flash-lite-tts'
    monkeypatch.setenv('GEMINI_TTS_MODEL','gemini-chat-or-unknown')
    with pytest.raises(tts.TTSFailure):tts.selected_model(tmp_path)


@pytest.mark.parametrize('status',[401,429,503])
def test_tts_failure_preserves_text_and_redacts_credentials(client,monkeypatch,status):
    client.app.state.store.message('web','assistant','Existing text reply')
    real=httpx.AsyncClient
    monkeypatch.setattr(tts.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'error':'private-key private text'}))))
    result=client.post('/api/speech/synthesize',json={'text':'Existing text reply'})
    assert result.status_code==(429 if status==429 else 503) and 'private-key' not in result.text and 'private text' not in result.text
    assert client.get('/api/messages').json()==[{'role':'assistant','content':'Existing text reply'}]


def test_tts_http_disconnect_cancels_pending_synthesis(client,monkeypatch):
    import uvicorn
    entered=threading.Event();cancelled=threading.Event()
    async def slow(*args):
        entered.set()
        try:await asyncio.sleep(30)
        finally:cancelled.set()
    monkeypatch.setattr(tts,'synthesize',slow)
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(client.app,log_level='critical',lifespan='off'))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    try:
        deadline=time.monotonic()+5
        while not server.started and time.monotonic()<deadline:time.sleep(.01)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',headers={'Authorization':'Bearer '+TOKEN},timeout=.3,trust_env=False) as network:
            with pytest.raises(httpx.ReadTimeout):network.post('/api/speech/synthesize',json={'text':'Hello'})
        assert entered.is_set() and cancelled.wait(2)
    finally:
        server.should_exit=True;thread.join(timeout=5);sock.close()


def test_future_auditions_do_not_replace_pinned_approved_model(tmp_path,monkeypatch):
    monkeypatch.delenv('GEMINI_TTS_MODEL',raising=False)
    folder=tmp_path/'voice-previews'/'20260101';folder.mkdir(parents=True)
    (folder/'audition.json').write_text(json.dumps({'model':'gemini-3.1-flash-tts-preview','completed':['B']}))
    assert tts.selected_model(tmp_path)=='gemini-3.1-flash-tts-preview'
    newer=folder.parent/'20261201';newer.mkdir()
    (newer/'audition.json').write_text(json.dumps({'model':'gemini-3.8-flash-lite-tts','completed':['B']}))
    assert tts.selected_model(tmp_path)=='gemini-3.1-flash-tts-preview'
    saved=json.loads((tmp_path/'voice-settings.json').read_text())
    assert saved=={'profile':'B','voice':'Aoede','model':'gemini-3.1-flash-tts-preview'}


def test_voice_cache_and_cooldown_avoid_provider_calls(client, monkeypatch):
    calls = []
    async def generate(text, data):
        calls.append(text)
        if text == 'new':
            raise tts.TTSRateLimit(300)
        return wav(), tts.MODELS[0]
    monkeypatch.setattr(tts, '_generate', generate)
    for _ in range(2):
        assert client.post('/api/speech/synthesize', json={'text':'cached'}).content == wav()
    limited = client.post('/api/speech/synthesize', json={'text':'new'})
    assert limited.status_code == 429 and limited.headers['retry-after'] == '300'
    assert client.post('/api/speech/synthesize', json={'text':'other'}).status_code == 429
    assert client.post('/api/speech/synthesize', json={'text':'cached'}).content == wav()
    assert calls == ['cached', 'new']


def test_quota_retry_metadata_is_honored_without_private_details():
    response = httpx.Response(429, headers={'Retry-After':'120'}, json={'error':{'message':'private-key', 'details':[{'@type':'type.googleapis.com/google.rpc.RetryInfo','retryDelay':'300s'}]}})
    with pytest.raises(tts.TTSRateLimit) as caught:
        tts.check_response(response)
    assert caught.value.seconds == 300
    assert 'private-key' not in str(caught.value)


def test_voice_cache_isolated_by_model_and_expires(client, monkeypatch):
    calls = []
    async def generate(text, data):
        calls.append(text)
        return wav(), tts.selected_model(data)
    monkeypatch.setattr(tts, '_generate', generate)
    for model in tts.MODELS[:2]:
        monkeypatch.setenv('GEMINI_TTS_MODEL', model)
        assert client.post('/api/speech/synthesize', json={'text':'hello'}).status_code == 200
    assert len(calls) == 2
    for key, (audio, model, created) in list(tts._audio_cache.items()):
        tts._audio_cache[key] = (audio, model, created-1801)
    assert client.post('/api/speech/synthesize', json={'text':'hello'}).status_code == 200
    assert len(calls) == 3


def test_voice_requests_do_not_overlap_and_cancel_releases_slot(client, monkeypatch):
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        async def slow(text, data):
            entered.set()
            await release.wait()
            return wav(), tts.MODELS[0]
        monkeypatch.setattr(tts, '_generate', slow)
        first = asyncio.create_task(tts.synthesize('first', client.app.state.store.path.rsplit('/',1)[0]))
        await entered.wait()
        with pytest.raises(tts.TTSFailure, match='already running'):
            await tts.synthesize('second', client.app.state.store.path.rsplit('/',1)[0])
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not tts._active_accounts
        release.set()
        assert (await tts.synthesize('second', client.app.state.store.path.rsplit('/',1)[0]))[0] == wav()
    asyncio.run(scenario())
