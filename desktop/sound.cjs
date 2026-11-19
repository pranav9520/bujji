'use strict';
const {randomUUID}=require('node:crypto');
const REASONS=new Set(['started','unsupported','failed']);
class SoundBridge {
  constructor(write,timeout=2500) {this.write=write;this.timeout=timeout;this.pending=new Map();}
  request() {
    const id=randomUUID();
    return new Promise(resolve=>{
      const timer=setTimeout(()=>{this.pending.delete(id);resolve({ok:false,reason:'timeout'});},this.timeout);
      this.pending.set(id,{resolve,timer});
      try {this.write(JSON.stringify({command:'chime',id})+'\n');}
      catch {this.finish(id,{ok:false,reason:'backend-unavailable'});}
    });
  }
  finish(id,result) {const item=this.pending.get(id);if(!item)return;clearTimeout(item.timer);this.pending.delete(id);item.resolve(result);}
  feed(line) {
    if (!line.startsWith('BUJJI_SOUND:')) return;
    try {const data=JSON.parse(line.slice('BUJJI_SOUND:'.length));if(typeof data.id==='string' && typeof data.ok==='boolean' && REASONS.has(data.reason))this.finish(data.id,{ok:data.ok,reason:data.reason});} catch {}
  }
  close() {for(const id of this.pending.keys())this.finish(id,{ok:false,reason:'backend-unavailable'});}
}
module.exports={SoundBridge};
