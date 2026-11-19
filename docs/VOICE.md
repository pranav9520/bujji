# Voice options and limits

Normal builds do not download or bundle a large local voice model. Windows supports optional configured Gemini speech generation; Android uses its installed Android text-to-speech engine. Cloud speech can have quotas, costs and outages. No engine is promised unlimited, free or instantaneous.

Microphone input uses the configured Gemini/Groq transcription provider independently of the chat provider. Silence handling is three seconds, subject to microphone/browser/OS scheduling. Short talk is temporary conversation, not a separate unlimited voice service. The device's hardware, current memory pressure, network and provider all affect latency.

Experimental desktop Hima/local-voice support is retained for developers, but model files are not distributed here. Review the exact upstream model licence, provenance, language quality and resource requirements before downloading or redistributing it. Application MIT licensing does not grant model rights. The setup script requires explicit `-AcceptModelLicense`; that flag records your acknowledgement, not legal clearance from this project.

`scripts/desktop-build.ps1 -IncludeLocalVoice` includes the optional runtime dependencies only. It does not download a model or automatically select one. Follow the configuration accepted by the source's local-voice module and test with non-sensitive samples. Do not bundle audition recordings, another person's voice or weights in source commits. This experimental option can use substantial RAM/CPU and storage; benchmark on the target laptop before enabling it routinely.

There is no voice cloning service included, no celebrity identity guarantee and no automatic rotation of provider accounts. Prefer an engine whose pronunciation and terms meet your needs; test your name and mixed-language phrases before relying on it.
