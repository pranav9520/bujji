/** Owned voice playback with cancellation and blob lifetime cleanup. */
export function speechText(message: string): {
  text: string;
  shortened: boolean;
} {
  let text = message
    .split("\n\nVerification: ")[0]
    .replace(/```[\s\S]*?```/g, " Code block omitted from speech. ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/https?:\/\/\S+/g, " link ")
    .replace(/(^|\n)\s{0,3}#{1,6}\s+/g, "$1")
    .replace(/\*\*|__/g, "")
    .replace(/\s+/g, " ")
    .trim();
  const shortened = text.length > 600;
  if (shortened) {
    let cut = text.lastIndexOf(" ", 580);
    if (cut < 300) cut = 580;
    text = text.slice(0, cut) + "…";
  }
  return { text, shortened };
}

export class SpeechPlayback {
  private pendingText: string | null = null;
  private generation = 0;
  private controller: AbortController | null = null;
  private audio: HTMLAudioElement | null = null;
  private url: string | null = null;
  stop() {
    this.pendingText = null;
    this.generation++;
    this.controller?.abort();
    this.controller = null;
    if (this.audio) {
      this.audio.onended = null;
      this.audio.onerror = null;
      this.audio.pause();
      this.audio.removeAttribute("src");
      this.audio.load();
      this.audio = null;
    }
    if (this.url) {
      URL.revokeObjectURL(this.url);
      this.url = null;
    }
  }
  async play(
    text: string,
    fetchAudio: (text: string, signal: AbortSignal) => Promise<Blob>,
    onStatus: (status: string) => void,
    onError: (message: string) => void,
    onFinished?: () => void,
  ) {
    if (this.pendingText === text) return;
    this.stop();
    this.pendingText = text;
    const generation = this.generation;
    const controller = new AbortController();
    this.controller = controller;
    onStatus("Preparing Bujji’s selected voice…");
    try {
      const blob = await fetchAudio(text, controller.signal);
      if (generation !== this.generation || controller.signal.aborted) return;
      if (document.hidden) {
        this.stop();
        onStatus("");
        return;
      }
      this.pendingText = null;
      this.url = URL.createObjectURL(blob);
      const audio = new Audio(this.url);
      this.audio = audio;
      audio.onended = () => {
        if (generation === this.generation) {
          this.stop();
          onStatus("");
          onFinished?.();
        }
      };
      audio.onerror = () => {
        if (generation === this.generation) {
          this.stop();
          onError(
            "Voice audio could not play. Check the output device and try Read aloud again.",
          );
        }
      };
      await audio.play();
      if (generation === this.generation)
        onStatus(
          "Bujji is speaking · tap Stop voice or the microphone to interrupt.",
        );
    } catch (error) {
      if (generation !== this.generation || controller.signal.aborted) return;
      this.stop();
      onError(
        (error as Error).name === "NotAllowedError"
          ? "Audio playback was blocked. Click Read aloud in the app to try again."
          : (error as Error).message ||
              "Voice playback failed; your text reply is available.",
      );
    }
  }
}
