import {useEffect,useRef,useState} from 'react';
import {VoiceCapture} from './voice';
import {SpeechPlayback,speechText} from './playback';

type Win={id:string;title:string;exe:string};
type Plan={plan_id:string;summary:string;confirmation_required:boolean;actions:any[]};
export function ComputerWidget(){
 const desktop=window.bujjiDesktop;
 const [ready,setReady]=useState(false),[busy,setBusy]=useState(false),[listening,setListening]=useState(false);
 const [input,setInput]=useState(''),[status,setStatus]=useState('Starting…'),[error,setError]=useState('');
 const [windows,setWindows]=useState<Win[]>([]),[target,setTarget]=useState(''),[read,setRead]=useState(false);
 const [detected,setDetected]=useState(''),[diagnostics,setDiagnostics]=useState<Record<string,unknown>|null>(null);
 const [plan,setPlan]=useState<Plan|null>(null),[results,setResults]=useState<string[]>([]),[routines,setRoutines]=useState<string[]>([]);
 const review=false;
 const [keep,setKeep]=useState(false),[aloud,setAloud]=useState(false),[routineName,setRoutineName]=useState('');
 const [completed,setCompleted]=useState('');
 const capture=useRef(new VoiceCapture()),player=useRef(new SpeechPlayback()),stt=useRef<AbortController|null>(null);
 const auth=useRef(''),epoch=useRef(0),mounted=useRef(true),busyRef=useRef(false),planRef=useRef<Plan|null>(null);
 const latest=useRef({target,read,keep,aloud});latest.current={target,read,keep,aloud};
 const listenAgain=useRef<()=>void>(()=>{});
 function setPending(value:Plan|null){planRef.current=value;setPlan(value)}
 async function api(path:string,options:RequestInit={}){
  const response=await fetch('/api'+path,{...options,headers:{Authorization:'Bearer '+auth.current,'Content-Type':'application/json',...options.headers}});
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:'Bujji request failed')}
  return response;
 }
 function halt(message='Stopped. Completed actions are not undone.'){
  epoch.current++;stt.current?.abort();capture.current.abort();player.current.stop();setListening(false);setKeep(false);latest.current.keep=false;setPending(null);setCompleted('');setBusy(false);busyRef.current=false;setStatus(message);
  void desktop?.computer({operation:'stop'}).catch(()=>{});
 }
 function humanError(e:unknown){return ((e as Error).message||'Computer request failed').replace(/^Error invoking remote method ['"][^'"]+['"]:\s*(?:Error:\s*)?/,'')}
 async function diagnostic(){try{const value=await desktop!.computer({operation:'diagnostics'});if(mounted.current)setDiagnostics(value)}catch{}}
 async function refresh(){
  if(!desktop||busyRef.current)return;
  setStatus('Checking open windows…');
  try{
   const data=await desktop.computer({operation:'status',target:latest.current.target,read_screen:false});if(!mounted.current)return;
   setWindows(data.windows);setDetected(data.windows.find((w:Win)=>w.id===data.target)?.title||'');setRoutines(data.routines);setDiagnostics(data.diagnostics||null);setError('');setStatus('Ready · say what you want to do');
  }catch(e){if(mounted.current){setError(humanError(e));setStatus('Ready for website commands · window discovery needs a retry');await diagnostic()}}
 }

 useEffect(()=>{
  mounted.current=true;let active=true;
  if(!desktop){setError('Open this widget from the Bujji Windows app.');return}
  void desktop.bootstrap().then(async boot=>{if(!active)return;if(boot.origin!==location.origin)throw new Error('Desktop pairing failed');auth.current=boot.token;setReady(true);setStatus('Ready · say what you want to do');const info=await desktop.computer({operation:'info'});if(active){setRoutines(Array.isArray(info.routines)?info.routines:[]);setDiagnostics(info.diagnostics||null)}}).catch(e=>{if(active){setError(humanError(e));setStatus('Desktop connection needs attention — close and reopen the widget')}});
  const hidden=()=>{if(document.hidden)halt('Paused · press Listen when you return')};
  document.addEventListener('visibilitychange',hidden);
  const unsubscribe=desktop.onHidden(()=>halt('Paused · press Listen when you return'));
  return()=>{active=false;mounted.current=false;epoch.current++;stt.current?.abort();capture.current.abort();player.current.stop();unsubscribe();document.removeEventListener('visibilitychange',hidden)};
 },[]);
 function fail(e:unknown){setError(humanError(e));void diagnostic();setKeep(false);latest.current.keep=false;setStatus('Paused · check the message, then retry')}
 async function finish(message:string,run:number){
  if(run!==epoch.current||!mounted.current)return;
  setStatus(message);
  if(latest.current.aloud){
   await new Promise<void>((resolve,reject)=>{void player.current.play(speechText(message).text,async(text,signal)=>(await api('/speech/synthesize',{method:'POST',signal,body:JSON.stringify({text,ephemeral:true})})).blob(),setStatus,e=>reject(new Error(e)),resolve)}).catch(e=>{if(run===epoch.current)setError('Voice: '+e.message)});
  }
  if(run===epoch.current&&latest.current.keep&&!document.hidden)setTimeout(()=>{if(run===epoch.current&&latest.current.keep)listenAgain.current()},250);
 }
 async function execute(value:Plan,confirmed:boolean){
  const run=epoch.current;busyRef.current=true;setBusy(true);setStatus('Running the listed actions…');setError('');setPending(null);
  try{
   const result=await desktop!.computer({operation:'execute',plan_id:value.plan_id,confirmed});
   if(run!==epoch.current)return;
   if(!result.completed){setKeep(false);latest.current.keep=false;}
   setResults(result.results.map((x:any)=>x.detail));setCompleted(result.plan_id);await finish(result.results.map((x:any)=>x.detail).join(' '),run);
  }catch(e){if(run===epoch.current)fail(e)}finally{if(run===epoch.current){busyRef.current=false;setBusy(false)}}
 }
 async function submit(text:string){
  if(!text.trim()||busyRef.current||!desktop)return;
  player.current.stop();capture.current.abort();setListening(false);setInput(text);
  const pending=planRef.current;
  if(/^(stop|pause|cancel|వద్దు)[.!]?$/i.test(text.trim())){halt('Stopped / cancelled');return}
  if(pending&&/^(approve(?: this)?|confirm|yes|అవును)[.!]?$/i.test(text.trim())){await execute(pending,true);return}
  if(pending&&/^(cancel|no|stop|వద్దు)[.!]?$/i.test(text.trim())){halt('Cancelled the pending plan');return}
  const run=epoch.current;busyRef.current=true;setBusy(true);setError('');setResults([]);setCompleted('');setPending(null);setStatus('Preparing a computer plan…');
  try{
   const next=await desktop.computer({operation:'plan',message:text,target:latest.current.target,read_screen:latest.current.read,direct:!review});
   if(run!==epoch.current)return;
   if(!next.actions.length){await finish(next.summary,run);return}
   setPending(next);
   if(next.confirmation_required)await finish('Needs your OK',run);
   else{busyRef.current=false;await execute(next,false)}
  }catch(e){if(run===epoch.current)fail(e)}finally{if(run===epoch.current){busyRef.current=false;setBusy(false)}}
 }
 async function listen(){
  if(busyRef.current||document.hidden||!ready)return;
  player.current.stop();setError('');const run=epoch.current;setStatus('Listening · 3 seconds of quiet to send');
  await capture.current.start(async blob=>{
   if(run!==epoch.current)return;
   busyRef.current=true;setBusy(true);setStatus('Understanding your command…');const controller=new AbortController();stt.current=controller;
   try{
    const data=await (await api('/speech/transcribe?language=te-IN',{method:'POST',signal:controller.signal,headers:{'Content-Type':blob.type},body:blob})).json();
    if(run!==epoch.current||controller.signal.aborted||document.hidden)return;
    busyRef.current=false;setBusy(false);await submit(data.text);
   }catch(e){if(run===epoch.current&&(e as Error).name!=='AbortError')fail(e)}finally{if(run===epoch.current){busyRef.current=false;setBusy(false)}}
  },setListening,message=>{if(run===epoch.current){setKeep(false);latest.current.keep=false;setError(message);setStatus('Paused · press Listen to try again')}});
 }
 listenAgain.current=()=>void listen();
 async function saveRoutine(){
  try{const result=await desktop!.computer({operation:'save_routine',plan_id:completed,name:routineName,confirmed:true});setRoutines(items=>[...items,result.name]);setRoutineName('');setStatus('Routine saved. Say “run '+result.name+'”.')}
  catch(e){fail(e)}
 }
 return <main className="computer-widget">
  <header><div className="widget-brand"><i className="widget-orb"/><span><b>Bujji</b><small>{review?'Review mode':'Direct control'}</small></span></div><button aria-label="Close computer control" onClick={()=>{halt();void desktop?.closeComputer()}}>×</button></header>
  {detected&&<p className="widget-target">{detected}</p>}
  <details className="widget-options"><summary>Options</summary>
   <label>Target app <select value={target} disabled={busy||listening||!!plan} onChange={e=>{setTarget(e.target.value);setPending(null)}}><option value="">Automatic</option>{windows.map(w=><option key={w.id} value={w.id}>{w.exe} · {w.title}</option>)}</select></label>
   <button disabled={busy||listening||!!plan} onClick={()=>void refresh()}>Refresh apps</button>
   <label className="widget-check"><input type="checkbox" checked={read} disabled={busy||listening||!!plan} onChange={e=>setRead(e.target.checked)}/>Read target app text</label>
   <small>Window titles go to your AI provider. This option also sends accessible text; password fields are excluded.</small>
   <small>Commands run directly. Windows prompts and protected-action checks remain.</small><div className="widget-checks"><label><input type="checkbox" checked={keep} onChange={e=>{setKeep(e.target.checked);latest.current.keep=e.target.checked}}/>Keep listening</label><label><input type="checkbox" checked={aloud} onChange={e=>setAloud(e.target.checked)}/>Speak replies</label></div>
  </details>
  <p className="widget-status" role="status">{results.length&&completed&&!busy&&!listening?'Ready for next command':status}</p>{error&&<><p role="alert" className="widget-error">{error}</p><details className="widget-diagnostics"><summary>Diagnostics</summary><pre>{JSON.stringify(diagnostics||{code:'unavailable'},null,2)}</pre><button disabled={busy} onClick={()=>void diagnostic()}>Refresh</button></details></>}
  <div className="widget-buttons"><button className="primary" disabled={!ready||busy||listening} onClick={()=>void listen()}>Listen</button>{listening&&<button onClick={()=>capture.current.stop()}>Send now</button>}{(listening||busy)&&<button onClick={()=>halt()}>Stop</button>}</div>
  {!plan&&<form onSubmit={e=>{e.preventDefault();void submit(input)}}><textarea aria-label="Computer command" value={input} onChange={e=>setInput(e.target.value)} placeholder="Open YouTube, put Notepad on the left…" maxLength={2000}/><button disabled={!ready||busy||listening||!input.trim()}>Run command</button></form>}
  {plan&&<section className="widget-plan"><blockquote className="widget-command">{input}</blockquote><strong>Needs your OK</strong><ol>{plan.actions.map((item,index)=><li key={index}>{item.action.op.replaceAll('_',' ')} · {item.target||item.app||item.action.url} {item.action.command?.replaceAll('_',' ')}{item.field&&<p>Field: {item.field}</p>}{item.action.text&&<blockquote>{item.action.text}</blockquote>}</li>)}</ol><p>Approval expires in 2 minutes.</p><button disabled={busy||listening} onClick={()=>void execute(plan,true)}>Yes, do it</button><button onClick={()=>halt('Cancelled the pending plan')}>Cancel</button></section>}
  {!!results.length&&<section className="widget-results"><strong>Action results</strong><ol>{results.map((line,index)=><li key={index}>{line}</li>)}</ol></section>}
  {completed&&<details className="widget-routine"><summary>Save routine</summary><input value={routineName} onChange={e=>setRoutineName(e.target.value)} placeholder="Routine name" maxLength={60}/><button disabled={busy||listening||!routineName.trim()} onClick={()=>void saveRoutine()}>Save these steps as routine</button><small>App, website, tab and window steps only.</small></details>}
  {!!routines.length&&<section><strong>Saved routines</strong>{routines.map(name=><div className="widget-routine-row" key={name}><button disabled={busy||listening} onClick={()=>void submit('run '+name)}>{name}</button><button disabled={busy||listening} onClick={()=>{void desktop!.computer({operation:'delete_routine',name,confirmed:true}).then(()=>setRoutines(items=>items.filter(n=>n!==name))).catch(fail)}}>Delete</button></div>)}</section>}
 </main>;
}
