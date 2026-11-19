import base64
import json
import sys
from types import SimpleNamespace
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from bujji.config import Settings
from bujji.main import create_app
from bujji import speech, chime

TOKEN='speech-test-token-'*3

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('BUJJI_STT_PROVIDER','gemini')
    monkeypatch.setenv('GEMINI_API_KEY','private-key')
    monkeypatch.setenv('GEMINI_MODEL','gemini-test')
    app=create_app(Settings(token=TOKEN,data=tmp_path/'data',files=tmp_path/'inbox'),background=False)
    with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:
        yield client


def test_speech_auth_format_size_and_language_validation(client,monkeypatch):
    assert client.post('/api/speech/transcribe',headers={'Authorization':''},content=b'clip').status_code==401
    assert client.post('/api/speech/transcribe',headers={'Content-Type':'text/plain'},content=b'clip').status_code==415
    assert client.post('/api/speech/transcribe',headers={'Content-Type':'audio/webm'},content=b'').status_code==422
    assert client.post('/api/speech/transcribe?language=invalid',headers={'Content-Type':'audio/webm'},content=b'clip').status_code==422
    assert client.post('/api/speech/transcribe',headers={'Content-Type':'audio/webm'},content=b'x'*(speech.MAX_AUDIO_BYTES+1)).status_code==413
    # Streaming bodies without a Content-Length are bounded too.
    def body():
        yield b'x'*(speech.MAX_AUDIO_BYTES//2)
        yield b'x'*(speech.MAX_AUDIO_BYTES//2+1)
    assert client.post('/api/speech/transcribe',headers={'Content-Type':'audio/webm'},content=body()).status_code==413


def test_gemini_audio_is_inline_and_transcript_is_not_saved(client,monkeypatch):
    real=httpx.AsyncClient
    def respond(request):
        data=json.loads(request.content)
        parts=data['contents'][0]['parts']
        assert base64.b64decode(parts[1]['inlineData']['data'])==b'test audio'
        assert parts[1]['inlineData']['mimeType']=='audio/webm'
        assert 'do not translate' in parts[0]['text']
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps({'text':'Hello Bujji, repu reminder unda?'})}]}}]})
    monkeypatch.setattr(speech.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond)))
    r=client.post('/api/speech/transcribe?language=te-IN',headers={'Content-Type':'audio/webm;codecs=opus'},content=b'test audio')
    assert r.status_code==200 and r.json()['text']=='Hello Bujji, repu reminder unda?'
    assert client.get('/api/messages').json()==[]
    assert client.get('/api/memories').json()==[]


def test_groq_uses_transcription_endpoint_not_chat_model(client,monkeypatch):
    monkeypatch.setenv('BUJJI_STT_PROVIDER','groq');monkeypatch.setenv('GROQ_API_KEY','private-groq-key')
    real=httpx.AsyncClient
    def respond(request):
        assert request.url.path=='/openai/v1/audio/transcriptions'
        assert b'whisper-large-v3-turbo' in request.content
        assert b'test audio' in request.content
        return httpx.Response(200,json={'text':'Telugu and English transcript'})
    monkeypatch.setattr(speech.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond)))
    assert client.post('/api/speech/transcribe',headers={'Content-Type':'audio/ogg'},content=b'test audio').json()['provider']=='groq'


@pytest.mark.parametrize('status',[400,401,429,503])
def test_speech_errors_do_not_leak_audio_or_keys(client,monkeypatch,status):
    real=httpx.AsyncClient
    monkeypatch.setattr(speech.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'error':'private-key and private audio'}))))
    r=client.post('/api/speech/transcribe',headers={'Content-Type':'audio/webm'},content=b'private audio')
    assert r.status_code==503
    assert 'private-key' not in r.text and 'private audio' not in r.text


def test_silence_has_no_fabricated_transcript(client,monkeypatch):
    real=httpx.AsyncClient
    monkeypatch.setattr(speech.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{"text":""}'}]}}]}))))
    r=client.post('/api/speech/transcribe',headers={'Content-Type':'audio/webm'},content=b'silent clip')
    assert r.status_code==503 and 'No clear speech' in r.json()['detail']


def test_bundled_chime_uses_only_fixed_asset_and_reports_start(monkeypatch):
    calls=[]
    monkeypatch.setattr(chime,'os',SimpleNamespace(name='nt'))
    monkeypatch.setitem(sys.modules,'winsound',SimpleNamespace(SND_FILENAME=1,SND_ASYNC=2,SND_NODEFAULT=4,PlaySound=lambda path,flags:calls.append((path,flags))))
    assert chime.play_chime()=={'ok':True,'reason':'started'}
    assert Path(calls[0][0]).name=='reminder.wav' and Path(calls[0][0]).is_file()
    assert calls[0][1]==7
    def fail(*args):raise RuntimeError('device unavailable')
    sys.modules['winsound'].PlaySound=fail
    assert chime.play_chime()=={'ok':False,'reason':'failed'}
