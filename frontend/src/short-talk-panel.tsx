import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { VoiceCapture } from './voice';
import { SpeechPlayback, speechText } from './playback';
import { ShortTalkSession, type ShortPhase } from './short-talk';
export type ShortTalkHandle = { end(): void };
type Props = { api(path: string, options?: RequestInit): Promise<Response>; provider: string; language: string; onClose(): void };

export const ShortTalkPanel = forwardRef<ShortTalkHandle, Props>(function ShortTalkPanel(props, ref) {
  const latest = useRef(props); latest.current = props;
  const mounted = useRef(true);
  const [phase, setPhase] = useState<ShortPhase>('idle');
  const [turn, setTurn] = useState({user:'',assistant:''});
  const [error, setError] = useState('');
  const [voiceStatus, setVoiceStatus] = useState('');
  const playback = useRef(new SpeechPlayback());
  const session = useRef<ShortTalkSession | null>(null);
  if (!session.current) session.current = new ShortTalkSession({
    capture:new VoiceCapture(),
    visible:() => !document.hidden,
    transcribe:async (blob,signal) => (await (await latest.current.api('/speech/transcribe?language='+encodeURIComponent(latest.current.language), {method:'POST',signal,headers:{'Content-Type':blob.type},body:blob})).json()).text,
    reply:async (text,history,signal) => (await (await latest.current.api('/short-talk', {method:'POST',signal,body:JSON.stringify({message:text,history,provider:latest.current.provider})})).json()).text,
    speak:(text,signal) => new Promise<void>((resolve,reject) => {
      const cleanup = () => signal.removeEventListener('abort',cancel);
      const cancel = () => { playback.current.stop(); cleanup(); reject(new DOMException('Short talk ended','AbortError')); };
      if (signal.aborted) { cancel(); return; }
      signal.addEventListener('abort',cancel,{once:true});
      void playback.current.play(speechText(text).text,async (value,audioSignal) => (await latest.current.api('/speech/synthesize', {method:'POST',signal:audioSignal,body:JSON.stringify({text:value,ephemeral:true})})).blob(),
        status => { if(mounted.current)setVoiceStatus(status); },
        message => { cleanup(); reject(new Error(message)); },
        () => { cleanup(); resolve(); });
    }),
    stopSpeaking:() => { playback.current.stop(); if(mounted.current)setVoiceStatus(''); },
    onPhase:value => { if(mounted.current)setPhase(value); },
    onTurn:(user,assistant) => { if(mounted.current)setTurn({user,assistant}); },
    onError:message => { if(mounted.current)setError(message); },
  });
  useImperativeHandle(ref,() => ({end:() => session.current!.end()}),[]);
  useEffect(() => {
    mounted.current=true;
    const close = () => { session.current!.end(); latest.current.onClose(); };
    const hidden = () => { if(document.hidden)close(); };
    document.addEventListener('visibilitychange',hidden);
    const unsubscribe=window.bujjiDesktop?.onHidden(close);
    session.current!.start();
    return () => { mounted.current=false; session.current!.end(); document.removeEventListener('visibilitychange',hidden); unsubscribe?.(); };
  },[]);
  const labels: Record<ShortPhase,string> = {idle:'Starting…',listening:'Listening · 3 seconds of quiet to send',transcribing:'Understanding what you said…',thinking:'Thinking…',speaking:voiceStatus || 'Preparing voice…',paused:'Paused · microphone off'};
  return <div className="short-talk-panel">
    <div className="short-talk-heading"><strong>Short talk</strong><span>NOT SAVED IN BUJJI</span></div>
    <p role="status">{labels[phase]}</p>
    <small>Unsaved chat · processed by your AI provider.</small>
    {turn.user && <p className="short-turn"><b>You:</b> {turn.user}</p>}
    {turn.assistant && <p className="short-turn"><b>Bujji:</b> {turn.assistant}</p>}
    {error && <p role="alert" className="short-talk-error">{error}</p>}
    <div className="short-talk-actions">
      {phase==='paused' ? <button onClick={() => session.current!.resume()}>Resume</button> : <>
        <button onClick={() => session.current!.pause()}>Pause</button>
        {(phase==='speaking' || phase==='thinking') && <button onClick={() => session.current!.resume()}>Interrupt and speak</button>}
      </>}
      <button onClick={() => { session.current!.end(); latest.current.onClose(); }}>End short talk</button>
    </div>
  </div>;
});
