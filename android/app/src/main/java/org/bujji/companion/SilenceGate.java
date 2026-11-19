package org.bujji.companion;
/** Monotonic microphone gate, shared by normal and short voice capture. */
final class SilenceGate {
 private final long started;private long lastSound;boolean heard;
 SilenceGate(long now){started=lastSound=now;}
 boolean update(int amplitude,long now){if(amplitude>900){heard=true;lastSound=now;}return now-started>=20000||now-lastSound>=3000;}
}
