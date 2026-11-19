import asyncio
import hashlib
import io
import json
import sys
import wave
import pytest
from bujji import local_voice, local_voice_assets, local_voice_worker, tts


def wav():
    out=io.BytesIO()
    with wave.open(out,'wb') as audio:audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(b'\x00\x01'*200)
    return out.getvalue()


def test_explicit_local_voice_needs_no_gemini_key(monkeypatch,tmp_path):
    monkeypatch.setenv('BUJJI_TTS_PROVIDER','hima');monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    calls=[]
    async def voice(text,data,ephemeral=False):calls.append((text,ephemeral));return wav(),local_voice.MODEL
    monkeypatch.setattr(local_voice,'synthesize',voice)
    result=asyncio.run(tts.synthesize('హలో!',tmp_path,ephemeral=True))
    assert result[1]==local_voice.MODEL and calls==[('హలో!',True)]


def test_missing_assets_never_download_or_fallback(monkeypatch,tmp_path):
    monkeypatch.setenv('BUJJI_TTS_PROVIDER','hima');local_voice._cache.clear()
    async def forbidden(*args,**kwargs):pytest.fail('Cloud fallback must not run')
    monkeypatch.setattr(tts,'_generate',forbidden)
    with pytest.raises(tts.TTSFailure,match='setup-local-voice'):
        asyncio.run(tts.synthesize('hello',tmp_path))
    assert not list(tmp_path.iterdir())


def test_chunking_preserves_words_and_bounds_long_sentences():
    text='హేయ్ స్నేహితా! '+('ఈ రోజు study plan చూద్దాం '*10)
    parts=local_voice_worker.chunks(text)
    assert max(map(len,parts))<=220
    assert ' '.join(parts)==' '.join(text.split())
    with pytest.raises(local_voice_worker.VoiceInputError):local_voice_worker.chunks('x'*221)


def test_worker_environment_drops_credentials_and_bounds_threads(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','private-key');monkeypatch.setenv('BUJJI_TOKEN','private-token')
    env=local_voice.worker_environment()
    assert 'GEMINI_API_KEY' not in env and 'BUJJI_TOKEN' not in env
    assert env['OMP_NUM_THREADS']=='2' and env['OPENBLAS_NUM_THREADS']=='1'
    assert env['HF_HUB_OFFLINE']=='1'


def test_asset_integrity_and_links_are_checked(tmp_path,monkeypatch):
    content=b'approved model asset';spec={'folder':'model','files':{'weights.bin':{'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}}}
    monkeypatch.setattr(local_voice_assets,'manifest',lambda:spec)
    root=tmp_path/'model';root.mkdir();asset=root/'weights.bin';asset.write_bytes(content)
    assert local_voice_assets.verify(tmp_path)==root
    asset.write_bytes(b'x'*len(content))
    with pytest.raises(local_voice_assets.AssetError,match='integrity'):local_voice_assets.verify(tmp_path)
    asset.unlink();outside=tmp_path/'outside';outside.write_bytes(content);asset.symlink_to(outside)
    with pytest.raises(local_voice_assets.AssetError):local_voice_assets.verify(tmp_path)


def test_local_worker_cancellation_kills_process_and_releases_slot(tmp_path,monkeypatch):
    async def scenario():
        local_voice._cache.clear();local_voice._active=False
        monkeypatch.setattr(local_voice,'verify',lambda *a,**k:tmp_path)
        entered=asyncio.Event()
        class Process:
            returncode=None;killed=False
            async def communicate(self,payload):entered.set();await asyncio.sleep(30)
            def kill(self):self.killed=True;self.returncode=-9
            async def wait(self):return self.returncode
        process=Process()
        async def spawn(*args,**kwargs):return process
        monkeypatch.setattr(local_voice.asyncio,'create_subprocess_exec',spawn)
        task=asyncio.create_task(local_voice.synthesize('hello',tmp_path,True));await entered.wait()
        with pytest.raises(local_voice.LocalVoiceError,match='already generating'):await local_voice.synthesize('other',tmp_path,True)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert process.killed and not local_voice._active
    asyncio.run(scenario())


def test_local_cache_is_bounded_and_ephemeral_does_not_reuse_it(tmp_path,monkeypatch):
    async def scenario():
        local_voice._cache.clear();local_voice._active=False
        monkeypatch.setattr(local_voice,'verify',lambda *a,**k:tmp_path);calls=[]
        class Process:
            returncode=0
            async def communicate(self,payload):calls.append(payload);return wav(),b''
        async def spawn(*args,**kwargs):return Process()
        monkeypatch.setattr(local_voice.asyncio,'create_subprocess_exec',spawn)
        for _ in range(2):assert (await local_voice.synthesize('normal',tmp_path))[0]==wav()
        assert len(calls)==1
        for _ in range(2):await local_voice.synthesize('private',tmp_path,True)
        assert len(calls)==3
        assert len(local_voice._cache)==1
    asyncio.run(scenario())


def test_original_a_phrasing_does_not_split_short_sentences():
    text='హేయ్ స్నేహితా! నేను బుజ్జిని. ఇవాళ నీ study plan సిద్ధం చేద్దాం. ముందు పని పూర్తి చేద్దాం, తర్వాత సరదాగా మాట్లాడుకుందాం. Ready?'
    assert local_voice_worker.chunks(text)==[text]
    long='word '*120
    assert ' '.join(local_voice_worker.chunks(long))==long.strip()
    assert max(map(len,local_voice_worker.chunks(long)))<=220
