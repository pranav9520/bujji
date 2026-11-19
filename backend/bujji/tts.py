"""Shared Gemini speech codec and Gemini prebuilt speech profile."""
import base64
import hashlib
import math
import time
from collections import OrderedDict
import io
import json
import os
import threading
from pathlib import Path
import re
import wave
import httpx

MODELS = ('gemini-3.8-flash-tts', 'gemini-3.8-flash-lite-tts', 'gemini-3.1-flash-tts-preview', 'gemini-2.5-flash-preview-tts')


BASE_STYLE = (
    'An original young ADULT female companion with native Telugu pronunciation and natural Indian English. '
    'Friendly, expressive, conversational and human-sounding. Read Telugu script natively; switch smoothly '
    'to English for the English words. Medium natural pitch, unhurried conversational rhythm, subtle smiles '
    'and brief natural pauses. No exaggerated slang, childish squeaking, announcer delivery or robotic cadence. '
    'Do not imitate a particular real person. Read the supplied transcript exactly; do not read these directions.'
)


PROFILES = {
    'A': {'voice':'Leda', 'label':'Youthful and playful', 'style':'Light playful energy, a friendly little tease, never shrill.'},
    'B': {'voice':'Aoede', 'label':'Warm and casually teasing', 'style':'Warm, breezy and relaxed, like a trusted friend joking gently.'},
    'C': {'voice':'Zephyr', 'label':'Bright and confident', 'style':'Bright, upbeat and confident, with controlled energy and a natural smile.'},
}


class TTSFailure(Exception):
    pass


class TTSRateLimit(TTSFailure):
    def __init__(self, seconds):
        self.seconds = max(1, math.ceil(seconds))
        super().__init__(f"Voice rate limit: wait {self.seconds} seconds before generating new speech. Cached speech and text chat remain available. A daily quota, if exhausted, may take longer to reset. No paid fallback was used.")


def retry_seconds(response):
    delay = 60.0
    try:
        delay = max(delay, float(response.headers.get("Retry-After", "0")))
    except (ValueError, TypeError):
        pass
    try:
        for detail in response.json().get("error", {}).get("details", []):
            if detail.get("@type", "").endswith("google.rpc.RetryInfo"):
                delay = max(delay, float(detail.get("retryDelay", "0s").removesuffix("s")))
    except (ValueError, TypeError, AttributeError):
        pass
    return min(delay, 86400)


def check_response(response):
    if response.is_success:
        return
    if response.status_code == 429:
        raise TTSRateLimit(retry_seconds(response))
    labels = {400:'TTS request rejected; check model and voice compatibility.',401:'Gemini credentials were rejected.',403:'Gemini TTS access was denied for this project.',404:'This TTS model is unavailable for your account.',429:'Free quota/rate limit reached; wait before retrying. No paid fallback was used.'}
    text = labels.get(response.status_code, 'The TTS service is temporarily unavailable.' if response.status_code>=500 else 'The TTS request failed.')
    raise TTSFailure(f'HTTP {response.status_code}: {text}')


def payload(model, profile, text):
    style = BASE_STYLE + ' ' + profile['style']
    if model.startswith('gemini-3.8-'):
        parts = [{'text':text, 'speech_metadata':{'style':style}}]
        voice_config = {'voice':profile['voice']}
    else:
        parts = [{'text':style+'\n\nTranscript:\n'+text}]
        voice_config = {'prebuiltVoiceConfig':{'voiceName':profile['voice']}}
    return {'contents':[{'role':'user','parts':parts}], 'generationConfig':{'responseModalities':['AUDIO'],'speechConfig':{'voiceConfig':voice_config}}}


async def choose_model(client, headers, requested=None):
    available = set()
    params = {'pageSize':100}
    for _ in range(5):
        response = await client.get('https://generativelanguage.googleapis.com/v1beta/models',headers=headers,params=params)
        check_response(response)
        data = response.json()
        for item in data.get('models',[]):
            if isinstance(item,dict) and isinstance(item.get('name'),str):
                name = item['name'].removeprefix('models/')
                if name in MODELS and 'generateContent' in item.get('supportedGenerationMethods',[]):
                    available.add(name)
        if not data.get('nextPageToken'):
            break
        params['pageToken'] = data['nextPageToken']
    if requested:
        if requested not in available:
            raise TTSFailure('The requested TTS model is not in your account’s returned model list. Chat models cannot generate this preview.')
        return requested
    for model in MODELS:
        if model in available:
            return model
    raise TTSFailure('No supported TTS model was found for this account. Keep billing disabled; check the TTS options in Google AI Studio. Your existing Bujji chat model is unchanged.')


def wav_bytes(data, mime):
    if len(data)>8*1024*1024 or not data:
        raise TTSFailure('Unexpected speech audio size; playback was not started.')
    if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        result=data
    elif mime.split(';')[0].lower() in {'audio/l16','audio/pcm'} and len(data)%2==0:
        rate_match=re.search(r'rate=(\d+)',mime)
        rate=int(rate_match.group(1)) if rate_match else 24000
        if rate not in {16000,22050,24000,44100,48000}:
            raise TTSFailure('Unsupported PCM sample rate.')
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(data)
        result=buffer.getvalue()
    else:
        raise TTSFailure('The provider did not return a supported WAV/PCM recording.')
    try:
        with wave.open(io.BytesIO(result),'rb') as recording:
            if recording.getnchannels() not in {1,2} or recording.getsampwidth()!=2 or recording.getnframes()/recording.getframerate()>90:
                raise TTSFailure('Unexpected preview audio format or duration.')
    except (wave.Error,EOFError,ZeroDivisionError):
        raise TTSFailure('The returned WAV was not readable.') from None
    return result


def decode_audio(response):
    try:
        for part in response['candidates'][0]['content']['parts']:
            inline=part.get('inlineData',{})
            if isinstance(inline.get('data'),str):
                decoded=base64.b64decode(inline['data'],validate=True)
                return wav_bytes(decoded,inline.get('mimeType',''))
    except (KeyError,IndexError,TypeError,ValueError):
        raise TTSFailure('The provider returned no usable speech audio. No raw response or key was printed.') from None
    raise TTSFailure('No audio was generated. A safety or model limit may have blocked the sample.')


_selection_lock=threading.Lock()


def selected_model(data_dir):
    override=os.getenv('GEMINI_TTS_MODEL','').strip()
    if override:
        if override not in MODELS:
            raise TTSFailure('GEMINI_TTS_MODEL must be one of the supported Gemini speech models. Chat/STT routes are separate.')
        return override
    # Pin the accepted audition model once. Future preview experiments must not
    # silently change the runtime voice/model before another explicit approval.
    with _selection_lock:
        settings_file=Path(data_dir)/'voice-settings.json'
        if settings_file.exists():
            try:
                if settings_file.is_symlink() or settings_file.stat().st_size>4096:
                    raise ValueError()
                saved=json.loads(settings_file.read_text(encoding='utf-8'))
                if not isinstance(saved,dict) or saved.get('voice')!='Aoede' or saved.get('model') not in MODELS:
                    raise ValueError()
                return saved['model']
            except (OSError,ValueError,TypeError):
                raise TTSFailure('Saved voice settings could not be read. Your text chat is unaffected; set GEMINI_TTS_MODEL explicitly while checking voice-settings.json locally.') from None
        selected=MODELS[0]
        root=Path(data_dir)/'voice-previews'
        for manifest in sorted(root.glob('*/audition.json'),reverse=True)[:100]:
            try:
                if manifest.is_symlink() or manifest.parent.is_symlink() or manifest.stat().st_size>32768:
                    continue
                data=json.loads(manifest.read_text(encoding='utf-8'))
                if isinstance(data,dict) and data.get('model') in MODELS and isinstance(data.get('completed'),list) and 'B' in data['completed']:
                    selected=data['model'];break
            except (OSError,ValueError,TypeError):
                continue
        temp=settings_file.with_suffix('.tmp')
        try:
            temp.write_text(json.dumps({'profile':'B','voice':'Aoede','model':selected},indent=2),encoding='utf-8')
            temp.replace(settings_file)
        except OSError:
            raise TTSFailure('Could not save your selected voice model. Check write access to the Bujji data folder; no chat data was changed.') from None
        return selected


async def _generate(text,data_dir):
    key=os.getenv('GEMINI_API_KEY','').strip()
    if not key:
        raise TTSFailure('Configure GEMINI_API_KEY for the configured Bujji voice. Your text reply is still available.')
    model=selected_model(data_dir)
    try:
        async with httpx.AsyncClient(timeout=90,trust_env=False) as client:
            response=await client.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',headers={'x-goog-api-key':key},json=payload(model,PROFILES['B'],text))
        check_response(response)
        return decode_audio(response.json()),model
    except httpx.TimeoutException:
        raise TTSFailure('Bujji voice generation timed out. Your text reply is available; try Read aloud again later.') from None
    except httpx.HTTPError:
        raise TTSFailure('Could not reach the voice service. Your text reply is available; no browser voice fallback was used.') from None
    except (ValueError,KeyError,IndexError,TypeError,AttributeError):
        raise TTSFailure('The voice service returned an unexpected response. Your text reply is still available.') from None


# Private, bounded in-memory cache: no transcripts/audio written to disk.
# Keyed by account, data folder, model and complete voice instructions.
_audio_cache = OrderedDict()
_cooldowns = {}
_active_accounts = set()
_CACHE_BYTES = 24 * 1024 * 1024
_CACHE_TTL = 1800


async def _synthesize_gemini(text, data_dir, ephemeral=False):
    key = os.getenv('GEMINI_API_KEY', '').strip()
    model = selected_model(data_dir)
    account = hashlib.sha256(key.encode()).hexdigest()
    identity = hashlib.sha256(json.dumps([str(Path(data_dir).resolve()), account, model, BASE_STYLE, PROFILES['B'], text], sort_keys=True).encode()).hexdigest()
    now = time.monotonic()
    for cached_key, (_, _, created) in list(_audio_cache.items()):
        if now - created >= _CACHE_TTL:
            del _audio_cache[cached_key]
    if not ephemeral and identity in _audio_cache:
        audio, saved_model, _ = _audio_cache[identity]
        _audio_cache.move_to_end(identity)
        return audio, saved_model
    if _cooldowns.get(account, 0) > now:
        raise TTSRateLimit(_cooldowns[account] - now)
    _cooldowns.pop(account, None)
    if account in _active_accounts:
        raise TTSFailure('Voice generation is already running. Wait for it to finish before requesting another recording.')
    _active_accounts.add(account)
    try:
        result = await _generate(text, data_dir)
        if not ephemeral: _audio_cache[identity] = (*result, time.monotonic())
        while sum(len(item[0]) for item in _audio_cache.values()) > _CACHE_BYTES or len(_audio_cache) > 16:
            _audio_cache.popitem(last=False)
        return result
    except TTSRateLimit as exc:
        _cooldowns[account] = time.monotonic() + exc.seconds
        raise
    finally:
        _active_accounts.discard(account)



def voice_status(data_dir):
    provider=os.getenv('BUJJI_TTS_PROVIDER','gemini').strip().lower()
    if provider=='hima':
        from .local_voice import status
        return status(data_dir)
    return {'provider':provider,'voice':'Aoede' if provider=='gemini' else 'unconfigured','model':os.getenv('GEMINI_TTS_MODEL','saved Gemini model'),'local':False,'ready':provider=='gemini' and bool(os.getenv('GEMINI_API_KEY'))}


async def synthesize(text,data_dir,ephemeral=False):
    provider=os.getenv('BUJJI_TTS_PROVIDER','gemini').strip().lower()
    if provider=='hima':
        from .local_voice import synthesize as local_synthesize, LocalVoiceError
        try:return await local_synthesize(text,data_dir,ephemeral)
        except LocalVoiceError as exc:raise TTSFailure(str(exc)) from None
    if provider=='gemini':return await _synthesize_gemini(text,data_dir,ephemeral)
    raise TTSFailure('Set BUJJI_TTS_PROVIDER to hima (selected local voice) or explicitly to gemini. No automatic fallback is enabled.')
