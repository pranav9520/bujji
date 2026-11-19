"""One local synthesis request per child process; exit releases model RAM."""
import io
import json
import os
import re
import sys
import wave
from pathlib import Path
from .local_voice_assets import verify, manifest, AssetError


class VoiceInputError(Exception):
    pass


def chunks(text,limit=220):
    """Restore the audition's packed phrasing; bound unusually long sentences."""
    result=[]
    for sentence in re.split(r'(?<=[.!?।॥])\s+',text.strip()):
        sentence=' '.join(sentence.split())
        if not sentence:continue
        if len(sentence)<=limit:
            # Match the original engine: keep nearby sentences in one inference.
            if result and len(result[-1])+1+len(sentence)<=limit:
                result[-1]+=' '+sentence
            else:result.append(sentence)
            continue
        current=''
        for word in sentence.split():
            if len(word)>limit:raise VoiceInputError('A word/identifier is too long for local speech. Use a shorter spoken reply; the text remains available.')
            if current and len(current)+1+len(word)>limit:
                result.append(current);current=''
            current=(current+' '+word).strip()
        if current:result.append(current)
    return result


def generate(text,data):
    root=verify(data,full=True)
    # Imported only in this short-lived worker, never the main API process.
    import hashlib
    import types
    import numpy as np
    import onnxruntime as ort
    ort.disable_telemetry_events()
    def source_module(name,relative):
        content=(root/relative).read_bytes()
        if hashlib.sha256(content).hexdigest()!=manifest()['files'][relative]['sha256']:raise AssetError('Voice runtime source integrity check failed.')
        result=types.ModuleType(name);result.__file__=str(root/relative);sys.modules[name]=result
        exec(compile(content,str(root/relative),'exec'),result.__dict__)
        return result
    # Execute hash-verified source bytes directly, avoiding unverified .pyc caches.
    normalize=source_module('normalize','text/normalize.py')
    source_module('indic_languages','text/indic_languages.py')
    module=source_module('bujji_hima_pinned','hima_onnx/__init__.py')
    module._load_normalize=lambda _:normalize.normalize
    def session(self,path):
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
        options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return ort.InferenceSession(path,sess_options=options,providers=['CPUExecutionProvider'])
    module.OnnxTTS._session=session
    tts=module.OnnxTTS(str(root),precision='int8',threads=2)
    # Keep original packed phrasing; bound normalized input to protect long replies.
    normalized=tts._normalize(text,language='te')
    parts=chunks(normalized)
    if not parts:raise VoiceInputError('No pronounceable text was supplied.')
    if len(normalized)>2400:raise VoiceInputError('The normalized reply is too long to read aloud. Use a shorter reply.')
    tts._sentences=lambda _:parts
    audio=tts.say(normalized,voice='Bhavana',seed=41,retries=2)
    duration=len(audio)/24000
    if not 0<duration<=90 or not np.isfinite(audio).all():raise VoiceInputError('Local speech exceeded its length or audio limits. The text reply remains available.')
    if float(np.sqrt(np.mean(audio**2)))<0.0001 or tts._longest_silence(audio)>=3:
        raise VoiceInputError('Local voice returned silent/unstable audio. Try a shorter reply; no cloud fallback was used.')
    pcm=(np.clip(audio,-1,1)*32767).astype('<i2').tobytes()
    output=io.BytesIO()
    with wave.open(output,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(pcm)
    return output.getvalue()


def main():
    try:
        if os.name!='nt':
            try:os.nice(5)
            except OSError:pass
        raw=sys.stdin.buffer.read(16385)
        if len(raw)>16384:raise VoiceInputError('Voice request is too large.')
        body=json.loads(raw)
        if not isinstance(body,dict) or not isinstance(body.get('text'),str) or not 1<=len(body['text'])<=2000 or not isinstance(body.get('data'),str):raise VoiceInputError('Invalid local voice request.')
        sys.stdout.buffer.write(generate(body['text'],Path(body['data'])))
        sys.stdout.buffer.flush()
        return 0
    except (AssetError,VoiceInputError) as exc:
        sys.stderr.write(json.dumps({'error':str(exc)}));return 1
    except Exception:
        sys.stderr.write(json.dumps({'error':'Optional local voice could not generate this reply. Check the installed voice dependencies/assets or try a shorter reply. No cloud fallback was used.'}));return 1


if __name__=='__main__':raise SystemExit(main())
