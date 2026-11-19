'use strict';
// Grant lasts for this app session only; all callers must still validate frame/audio/visibility.
class MicrophoneGate {
  constructor() {this.granted=false;this.pending=null;}
  async request(prompt, stillAllowed) {
    if (!stillAllowed()) return false;
    if (this.granted) return true;
    if (!this.pending) this.pending=Promise.resolve().then(prompt).then(allow=>{this.granted=allow===true && stillAllowed();return this.granted;}).finally(()=>{this.pending=null;});
    return this.pending;
  }
}
module.exports={MicrophoneGate};
