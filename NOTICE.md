# Notices

Bujji application code is MIT licensed; see LICENSE.

- Windows computer-control work was informed by the MIT-licensed Atticus macOS project. Its original notice is retained in `docs/third-party/ATTICUS_LICENSE.txt`. Bujji's Windows helper is not a bundled macOS app.
- The Gradle wrapper is distributed under Apache-2.0; its embedded licence is retained in `docs/third-party/GRADLE-WRAPPER-LICENSE.txt`, with the Apache-2.0 text alongside it.
- Lucide icons are ISC licensed. React is MIT licensed. Electron includes Chromium and other components under their respective licences; preserve the licence files distributed with Electron builds.
- Python/Node/Android dependencies retain their upstream licences. Windows builds generate dependency notices and include them with the packaged application; these components are not relicensed by Bujji's MIT licence.
- The bundled reminder chime is a generated tone, not a personal voice recording. No audition recordings, model weights or training data are bundled.
- Optional local speech references an external model with nonstandard terms. It is disabled in the default build and is not covered by Bujji's MIT licence. See `docs/VOICE.md` before downloading or redistributing any model/runtime assets.
