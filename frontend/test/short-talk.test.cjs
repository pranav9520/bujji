const {test}=require('node:test');
const assert=require('node:assert/strict');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function setup(overrides={}) {
 const {ShortTalkSession}=await import('../.voice-test/short-talk.js');
 const state={starts:0,phases:[],turns:[],histories:[],signals:[],visible:true};
 const capture={async start(audio,_state,error){state.starts++;state.audio=audio;state.error=error},abort(){}};
 const deps={capture,async transcribe(_blob,signal){state.signals.push(signal);return 'hello'},async reply(text,history){state.histories.push(history);return 'hi'},async speak(){},stopSpeaking(){},visible:()=>state.visible,settlePlayback:async()=>{},onPhase:p=>state.phases.push(p),onTurn:(...t)=>state.turns.push(t),onError:e=>state.lastError=e,...overrides};
 const session=new ShortTalkSession(deps);session.start();await flush();
 return {session,state,deps};
}
test('waits for complete voice playback before listening again',async()=>{
 let finish;const {session,state}=await setup({speak:()=>new Promise(r=>finish=r)});
 state.audio(new Blob(['audio']));await flush();assert.equal(state.starts,1);assert.equal(state.phases.at(-1),'speaking');
 finish();await flush();assert.equal(state.starts,2);assert.equal(state.phases.at(-1),'listening');session.end();
});
test('ending during transcription aborts and ignores late text',async()=>{
 let finish;const {session,state}=await setup({transcribe:(_b,s)=>{state.signals.push(s);return new Promise(r=>finish=r)}});
 state.audio(new Blob());await flush();session.end();assert.equal(state.signals[0].aborted,true);
 finish('late');await flush();assert.equal(state.histories.length,0);assert.equal(state.starts,1);assert.deepEqual(state.turns.at(-1),['','']);
});
test('end clears context; pause and resume retain only four turn pairs',async()=>{
 const {session,state}=await setup();
 for(let n=0;n<7;n++){state.audio(new Blob());await flush()}
 assert.equal(state.histories.at(-1).length,8);
 session.pause();session.resume();await flush();state.audio(new Blob());await flush();assert.equal(state.histories.at(-1).length,8);
 session.end();session.start();await flush();state.audio(new Blob());await flush();assert.equal(state.histories.at(-1).length,0);session.end();
});
test('silence errors pause without sending requests',async()=>{
 const {session,state}=await setup();state.error('No speech');await flush();assert.equal(state.phases.at(-1),'paused');assert.equal(state.histories.length,0);assert.equal(state.starts,1);session.end();
});
test('hidden view cannot restart microphone after delayed playback',async()=>{
 let finish;const {session,state}=await setup({speak:()=>new Promise(r=>finish=r)});
 state.audio(new Blob());await flush();state.visible=false;finish();await flush();assert.equal(state.starts,1);session.end();
});
test('pause aborts reply and ignores a delayed provider response',async()=>{
 let finish;const {session,state}=await setup({reply:(_t,_h,s)=>{state.signals.push(s);return new Promise(r=>finish=r)}});
 state.audio(new Blob());await flush();session.pause();assert.equal(state.signals.at(-1).aborted,true);finish('late');await flush();assert.equal(state.phases.at(-1),'paused');assert.equal(state.starts,1);session.end();
});
