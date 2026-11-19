export type ShortPhase = 'idle' | 'listening' | 'transcribing' | 'thinking' | 'speaking' | 'paused';
export type ShortTurn = { role: 'user' | 'assistant'; content: string };
export interface ShortCapture {
  start(onAudio: (blob: Blob) => void, onState: (active: boolean) => void, onError: (message: string) => void): Promise<void>;
  abort(): void;
}
export interface ShortDependencies {
  capture: ShortCapture;
  transcribe(blob: Blob, signal: AbortSignal): Promise<string>;
  reply(text: string, history: ShortTurn[], signal: AbortSignal): Promise<string>;
  speak(text: string, signal: AbortSignal): Promise<void>;
  stopSpeaking(): void;
  visible(): boolean;
  settlePlayback?(): Promise<void>;
  onPhase(phase: ShortPhase): void;
  onTurn(user: string, assistant: string): void;
  onError(message: string): void;
}
/** Half-duplex, bounded in-memory dialogue. No navigation or persistence APIs. */
export class ShortTalkSession {
  private epoch = 0;
  private active = false;
  private request: AbortController | null = null;
  private history: ShortTurn[] = [];
  constructor(private deps: ShortDependencies) {}
  start() {
    this.end();
    this.resume();
  }
  resume() {
    this.pause();
    if (!this.deps.visible()) return;
    this.active = true;
    this.deps.onError('');
    void this.listen(this.epoch);
  }
  pause(message = '') {
    this.active = false;
    this.epoch++;
    this.request?.abort();
    this.request = null;
    this.deps.capture.abort();
    this.deps.stopSpeaking();
    this.deps.onPhase('paused');
    if (message) this.deps.onError(message);
  }
  end() {
    this.pause();
    this.history = [];
    this.deps.onTurn('', '');
    this.deps.onError('');
    this.deps.onPhase('idle');
  }
  private valid(epoch: number) {
    return this.active && this.epoch === epoch && this.deps.visible();
  }
  private async listen(epoch: number) {
    if (!this.valid(epoch)) return;
    this.deps.onPhase('listening');
    await this.deps.capture.start(
      blob => { if (this.valid(epoch)) void this.turn(blob, epoch); },
      () => {},
      message => { if (this.valid(epoch)) this.pause(message); },
    );
  }
  private async turn(blob: Blob, epoch: number) {
    if (!this.valid(epoch)) return;
    const controller = new AbortController();
    this.request = controller;
    try {
      this.deps.onPhase('transcribing');
      const text = (await this.deps.transcribe(blob, controller.signal)).trim();
      if (!this.valid(epoch)) return;
      if (!text) { this.pause('No clear speech was heard. Tap Resume to try again.'); return; }
      this.deps.onTurn(text, '');
      this.deps.onPhase('thinking');
      const answer = (await this.deps.reply(text, this.history.slice(-8), controller.signal)).trim();
      if (!this.valid(epoch)) return;
      if (!answer) { this.pause('No reply was returned. Tap Resume to try again.'); return; }
      this.history = [...this.history, {role:'user',content:text.slice(0,1000)}, {role:'assistant',content:answer.slice(0,1000)}].slice(-8) as ShortTurn[];
      this.deps.onTurn(text, answer);
      this.deps.onPhase('speaking');
      await this.deps.speak(answer, controller.signal);
      if (!this.valid(epoch)) return;
      this.request = null;
      await (this.deps.settlePlayback?.() ?? new Promise<void>(resolve => setTimeout(resolve,250)));
      if (this.valid(epoch)) await this.listen(epoch);
    } catch (error) {
      if (!this.valid(epoch)) return;
      this.pause((error as Error).message || 'Short talk could not continue. Tap Resume to retry.');
    }
  }
}
