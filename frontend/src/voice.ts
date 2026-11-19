/** Local RMS gate: three consecutive seconds below the speech threshold. */
export class SilenceDetector {
  private lastSound: number;
  heardSpeech = false;
  constructor(now: number) {
    this.lastSound = now;
  }
  update(rms: number, now: number) {
    if (rms > 0.015) {
      this.lastSound = now;
      this.heardSpeech = true;
    }
    return now - this.lastSound >= 3000;
  }
}
/** Browser-independent capture: no SpeechRecognition network service. */
export class VoiceCapture {
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private monitor: ReturnType<typeof setInterval> | null = null;
  private audioContext: AudioContext | null = null;
  private cleanupMonitor() {
    if (this.monitor) clearInterval(this.monitor);
    this.monitor = null;
    void this.audioContext?.close();
    this.audioContext = null;
  }
  private epoch = 0;
  private active = false;
  stop() {
    this.cleanupMonitor();
    if (this.recorder?.state === "recording") this.recorder.stop();
  }
  abort() {
    this.epoch++;
    this.active = false;
    if (this.timer) clearTimeout(this.timer);
    this.stop();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }
  async start(
    onAudio: (blob: Blob) => void,
    onState: (active: boolean) => void,
    onError: (message: string) => void,
  ) {
    if (this.active) return;
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      onError(
        "Audio recording is unavailable. Use the desktop app or a supported browser on HTTPS; typed chat still works.",
      );
      return;
    }
    this.active = true;
    const epoch = ++this.epoch;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: false,
      });
      if (epoch !== this.epoch || document.hidden) {
        stream.getTracks().forEach((track) => track.stop());
        if (epoch === this.epoch) this.active = false;
        return;
      }
      this.stream = stream;
      const mime = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
        "audio/mp4",
      ].find((type) => MediaRecorder.isTypeSupported(type));
      if (!mime)
        throw new Error(
          "This device has no supported audio recording format. Use text for now.",
        );
      const recorder = new MediaRecorder(stream, {
        mimeType: mime,
        audioBitsPerSecond: 64000,
      });
      this.recorder = recorder;
      let detector: SilenceDetector | null = null;
      let parts: Blob[] = [],
        size = 0,
        failed = false;
      recorder.ondataavailable = (event) => {
        size += event.data.size;
        if (size > 2 * 1024 * 1024) {
          failed = true;
          this.stop();
          onError("Recording exceeded 2 MB. Please try a shorter message.");
        } else if (event.data.size) parts.push(event.data);
      };
      recorder.onerror = () => {
        failed = true;
        this.stop();
        onError(
          "Recording failed. Check your selected input device or use text.",
        );
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        if (epoch !== this.epoch) {
          parts = [];
          return;
        }
        this.cleanupMonitor();
        this.active = false;
        this.recorder = null;
        this.stream = null;
        if (this.timer) clearTimeout(this.timer);
        onState(false);
        if (!failed && size > 0 && (!detector || detector.heardSpeech))
          onAudio(new Blob(parts, { type: mime }));
        else if (!failed && detector && !detector.heardSpeech)
          onError("No speech detected. Tap the microphone to try again.");
        parts = [];
      };
      // Only amplitude is inspected locally; audio is uploaded after recording stops.
      if (typeof AudioContext !== "undefined") {
        const context = new AudioContext();
        this.audioContext = context;
        const analyser = context.createAnalyser();
        analyser.fftSize = 2048;
        context.createMediaStreamSource(stream).connect(analyser);
        await context.resume();
        if (epoch !== this.epoch) {
          if (context.state !== "closed") void context.close();
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        const samples = new Float32Array(analyser.fftSize);
        detector = new SilenceDetector(performance.now());
        this.monitor = setInterval(() => {
          analyser.getFloatTimeDomainData(samples);
          const rms = Math.sqrt(
            samples.reduce((sum, x) => sum + x * x, 0) / samples.length,
          );
          if (detector!.update(rms, performance.now())) this.stop();
        }, 100);
      }
      if (epoch !== this.epoch || document.hidden) {
        this.abort();
        return;
      }
      recorder.start(250);
      onState(true);
      this.timer = setTimeout(() => this.stop(), 20000);
    } catch (error) {
      if (epoch !== this.epoch) return;
      this.abort();
      onState(false);
      onError(
        (error as Error).name === "NotAllowedError"
          ? "Microphone access was denied. Check Windows Privacy → Microphone and allow desktop apps, then try again."
          : (error as Error).name === "NotFoundError"
            ? "No microphone was found. Select or connect an input device."
            : "Could not start recording. Check microphone permissions and that another app is not using the device.",
      );
    }
  }
}
