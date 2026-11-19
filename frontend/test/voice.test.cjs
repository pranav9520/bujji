'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
async function setup(t,getMedia) {
 const {VoiceCapture}=await import('../.voice-test/voice.js');
 const old={navigator:Object.getOwnPropertyDescriptor(globalThis,'navigator'),document:globalThis.document,MediaRecorder:globalThis.MediaRecorder};
 const track={stopped:false,stop(){this.stopped=true}};
 const stream={getTracks:()=>[track]};
 let recorder;
 class FakeRecorder {
  static isTypeSupported(){return true}
  constructor(){recorder=this;this.state='inactive'}
  start(){this.state='recording'}
  stop(){this.state='inactive';queueMicrotask(()=>{this.ondataavailable?.({data:new Blob(['audio'])});this.onstop?.()})}
 }
 Object.defineProperty(globalThis,'navigator',{configurable:true,value:{mediaDevices:{getUserMedia:getMedia||(()=>Promise.resolve(stream))}}});
 globalThis.document={hidden:false};globalThis.MediaRecorder=FakeRecorder;
 t.after(()=>{
  if(old.navigator)Object.defineProperty(globalThis,'navigator',old.navigator);else delete globalThis.navigator;
  globalThis.document=old.document;globalThis.MediaRecorder=old.MediaRecorder;
 });
 return {capture:new VoiceCapture(),track,stream,getRecorder:()=>recorder};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('tap stop submits audio only after stopping and releases microphone',async t=>{
 const {capture,track}=await setup(t);const clips=[],states=[],errors=[];
 await capture.start(blob=>clips.push(blob),state=>states.push(state),error=>errors.push(error));
 assert.deepEqual(states,[true]);assert.equal(clips.length,0);
 capture.stop();await settle();
 assert.deepEqual(states,[true,false]);assert.equal(clips.length,1);assert.equal(track.stopped,true);assert.equal(errors.length,0);
});
test('abort discards the recording instead of uploading it',async t=>{
 const {capture,track}=await setup(t);const clips=[];
 await capture.start(blob=>clips.push(blob),()=>{},()=>{});
 capture.abort();await settle();
 assert.equal(clips.length,0);assert.equal(track.stopped,true);
});
test('abort while permission is pending stops a late stream without recording',async t=>{
 let resolve;const pending=new Promise(r=>resolve=r);
 const {capture,stream,track,getRecorder}=await setup(t,()=>pending);const clips=[];
 const started=capture.start(blob=>clips.push(blob),()=>{},()=>{});
 capture.abort();resolve(stream);await started;
 assert.equal(clips.length,0);assert.equal(track.stopped,true);assert.equal(getRecorder(),undefined);
});
test('rapid repeated start does not create duplicate microphone requests',async t=>{
 let calls=0;let release;const pending=new Promise(r=>release=r);
 const {capture,stream}=await setup(t,()=>{calls++;return pending});
 const first=capture.start(()=>{},()=>{},()=>{});
 await capture.start(()=>{},()=>{},()=>{});assert.equal(calls,1);
 release(stream);await first;capture.abort();await settle();
});
test('three seconds of silence ends capture, speech resets the timer',async()=>{
 const {SilenceDetector}=await import('../.voice-test/voice.js');
 const gate=new SilenceDetector(0);
 assert.equal(gate.update(0,2999),false);
 assert.equal(gate.update(0.05,2999),false);
 assert.equal(gate.heardSpeech,true);
 assert.equal(gate.update(0,5998),false);
 assert.equal(gate.update(0,5999),true);
 const empty=new SilenceDetector(0);
 assert.equal(empty.update(0,3000),true);
 assert.equal(empty.heardSpeech,false);
});
test('silence monitor stops real capture lifecycle and releases audio resources',async t=>{
 const env=await setup(t);const old={AudioContext:globalThis.AudioContext,performance:globalThis.performance,setInterval:globalThis.setInterval,clearInterval:globalThis.clearInterval};
 let now=0,tick,closed=false,cleared=false;
 globalThis.performance={now:()=>now};
 globalThis.setInterval=fn=>{tick=fn;return 42};
 globalThis.clearInterval=()=>{cleared=true};
 class Context {
  createAnalyser(){return {fftSize:2048,getFloatTimeDomainData:data=>data.fill(now===100?0.04:0)}}
  createMediaStreamSource(){return {connect(){}}}
  async resume(){}
  async close(){closed=true}
 }
 globalThis.AudioContext=Context;
 t.after(()=>Object.assign(globalThis,old));
 const clips=[];
 await env.capture.start(blob=>clips.push(blob),()=>{},()=>{});
 now=100;tick();now=3099;tick();assert.equal(env.getRecorder().state,'recording');
 now=3100;tick();await settle();
 assert.equal(clips.length,1);assert.equal(env.track.stopped,true);assert.equal(closed,true);assert.equal(cleared,true);
});
