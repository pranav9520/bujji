# Architecture

- `backend/src/bujji`: FastAPI service, provider routing, local storage, pairing/sync, file tools and job validation.
- `frontend/src`: TypeScript/React desktop interface, microphone sessions and the native bridge.
- `desktop`: Electron shell, preload/policy boundary and Windows control worker.
- `android/app/src/main`: Java Android host and bundled web interface, provider clients, device storage, pairing and native Android services.
- `tests` and `android/tests`: backend/browser checks; Java unit tests live under the Android app's test source tree.
- `scripts`: reproducible setup, build, release checks and publication hygiene.

The Electron renderer uses a narrow preload API. The Windows worker validates supported action types; it is not an arbitrary shell. Phone control goes through authenticated pairing and separately granted scopes. File actions have path and operation checks; an LLM response is never itself authority to bypass native validation. Owner configuration and paired-device credentials are separate.

Desktop data/configuration lives in its local workspace. Android settings/data are local to its application sandbox. Memory/reminder sync is manual; API keys are not shared. First-run profile setup removes assumptions about a particular owner. Provider routing and speech configuration are independent.

Read SECURITY.md and PRIVACY.md for trust boundaries and provider data flows. Optional voice models are outside the normal build and retain their own terms. Dependency locks and CI improve reproducibility but do not replace real Windows and Android device testing.
