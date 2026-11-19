"""Async owned local-voice child: one worker, cancellation, no idle model RAM."""
import asyncio
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .local_voice_assets import verify, AssetError

MODEL='hima-a-bhavana-int8-packed-v2'
_active=False
_cache=OrderedDict()


class LocalVoiceError(Exception):
    pass


def status(data):
    try:verify(data,full=False);ready=True
    except (AssetError,OSError):ready=False
    return {'provider':'local','voice':'Bujji local voice','model':'local-a-v2','ready':ready,'local':True,'threads':2,'idle_model_loaded':False}


def command():
    if getattr(sys,'frozen',False):return [sys.executable,'--voice-worker']
    return [sys.executable,'-m','bujji.local_voice_worker']


def worker_environment():
    allowed={'SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP','USERPROFILE','HOME','APPDATA','LOCALAPPDATA','LANG','LC_ALL'}
    env={k:v for k,v in os.environ.items() if k.upper() in allowed}
    env.update(PYTHONUTF8='1',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    return env


async def synthesize(text,data,ephemeral=False):
    global _active
    now=time.monotonic()
    for key,(_,created) in list(_cache.items()):
        if now-created>600:del _cache[key]
    identity=hashlib.sha256((str(Path(data).resolve())+'\0'+MODEL+'\0'+text).encode()).hexdigest()
    if not ephemeral and identity in _cache:
        return _cache[identity][0],MODEL
    if _active:raise LocalVoiceError('Local voice is already generating. Stop the other speech or wait; parallel workers are disabled to limit RAM.')
    try:verify(data,full=False)
    except (AssetError,OSError) as exc:raise LocalVoiceError(str(exc) if isinstance(exc,AssetError) else 'Local voice assets are unavailable.') from None
    _active=True;process=None
    try:
        flags=(subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name=='nt' else 0
        process=await asyncio.create_subprocess_exec(*command(),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=worker_environment(),creationflags=flags)
        payload=json.dumps({'text':text,'data':str(Path(data).resolve())},ensure_ascii=False).encode('utf-8')
        async with asyncio.timeout(120):audio,error=await process.communicate(payload)
        if process.returncode!=0:
            try:message=json.loads(error.decode('utf-8').splitlines()[-1])['error']
            except (ValueError,KeyError,IndexError,UnicodeError):message='Optional local voice failed. Check setup-local-voice.ps1 and retry. No cloud fallback was used.'
            raise LocalVoiceError(message)
        from .tts import wav_bytes
        audio=wav_bytes(audio,'audio/wav')
        if not ephemeral:
            _cache[identity]=(audio,time.monotonic())
            while len(_cache)>4 or sum(len(item[0]) for item in _cache.values())>8*1024*1024:_cache.popitem(last=False)
        return audio,MODEL
    except TimeoutError:
        raise LocalVoiceError('Local voice generation timed out and was stopped. Your text reply is available.') from None
    except OSError:
        raise LocalVoiceError('The local voice worker could not start. Rebuild the desktop app with local-voice dependencies.') from None
    finally:
        if process and process.returncode is None:
            try:process.kill()
            except ProcessLookupError:pass
            await process.wait()
        _active=False
