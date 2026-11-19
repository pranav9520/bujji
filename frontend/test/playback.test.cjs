'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');
async function setup(t,fail=false) {
 const {SpeechPlayback,speechText}=await import('../.voice-test/playback.js');
 const old={Audio:globalThis.Audio,document:globalThis.document,create:URL.createObjectURL,revoke:URL.revokeObjectURL};
 const audios=[],created=[],revoked=[];
 globalThis.document={hidden:false};
 URL.createObjectURL=blob=>{const url='blob:sample-'+created.length;created.push(url);return url};
 URL.revokeObjectURL=url=>revoked.push(url);
 globalThis.Audio=class {constructor(url){this.url=url;audios.push(this)}async play(){if(fail){const error=new Error('blocked');error.name='NotAllowedError';throw error}this.played=true}pause(){this.paused=true}removeAttribute(){}load(){}};
 t.after(()=>{globalThis.Audio=old.Audio;globalThis.document=old.document;URL.createObjectURL=old.create;URL.revokeObjectURL=old.revoke});
 return {player:new SpeechPlayback(),speechText,audios,created,revoked};
}
test('speech script omits code, verification and raw URLs and bounds length',async t=>{
 const {speechText}=await setup(t);
 const prepared=speechText('## Hello **Alex**\n```js\nsecret code\n```\n[notes](https://example.com)\n\nVerification: Not executed');
 assert.match(prepared.text,/Hello Alex/);assert.doesNotMatch(prepared.text,/secret code|Verification|https:/);
 const long=speechText('word '.repeat(800));assert.equal(long.shortened,true);assert.ok(long.text.length<=600);
});
test('playback ends cleanly and revokes its audio URL',async t=>{
 const {player,audios,revoked}=await setup(t);const statuses=[],errors=[];let finished=0;
 await player.play('Hello',async()=>new Blob(['wav']),s=>statuses.push(s),e=>errors.push(e),()=>finished++);
 assert.equal(audios.length,1);assert.equal(audios[0].played,true);
 assert.equal(finished,0);audios[0].onended();assert.equal(finished,1);assert.equal(audios[0].paused,true);assert.equal(revoked.length,1);assert.equal(errors.length,0);assert.equal(statuses.at(-1),'');
});
test('stopping generation aborts upload and prevents late playback',async t=>{
 const {player,audios,created}=await setup(t);let release,signal;
 const pending=new Promise(r=>release=r);
 const done=player.play('Hello',async(text,s)=>{signal=s;return pending},()=>{},()=>{});
 player.stop();release(new Blob(['wav']));await done;
 assert.equal(signal.aborted,true);assert.equal(audios.length,0);assert.equal(created.length,0);
});
test('replacement reads only the newest reply',async t=>{
 const {player,audios}=await setup(t);let release;
 const old=player.play('old',()=>new Promise(r=>release=r),()=>{},()=>{});
 await player.play('new',async()=>new Blob(['new']),()=>{},()=>{});
 release(new Blob(['old']));await old;assert.equal(audios.length,1);player.stop();
});
test('autoplay failure is surfaced without losing text or leaking URLs',async t=>{
 const {player,revoked}=await setup(t,true);const errors=[];
 await player.play('Hello',async()=>new Blob(['wav']),()=>{},e=>errors.push(e));
 assert.match(errors[0],/playback was blocked/);assert.equal(revoked.length,1);
});
test('hidden page cannot start late speech',async t=>{
 const {player,audios}=await setup(t);const statuses=[];
 await player.play('Hello',async()=>{document.hidden=true;return new Blob(['wav'])},s=>statuses.push(s),()=>{});
 assert.equal(audios.length,0);assert.equal(statuses.at(-1),'');
});
test('repeated click during generation does not restart a paid/quota request',async t=>{
 const {player,audios}=await setup(t);let release,calls=0;
 const fetcher=()=>{calls++;return new Promise(r=>release=r)};
 const first=player.play('same',fetcher,()=>{},()=>{});
 await player.play('same',fetcher,()=>{},()=>{});
 assert.equal(calls,1);
 release(new Blob(['wav']));await first;
 assert.equal(audios.length,1);player.stop();
});
