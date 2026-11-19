<p align="center"><img src="desktop/assets/icon.png" width="86" alt="Bujji logo"></p>
<h1 align="center">Bujji</h1>
<p align="center">Your assistant. Your workspace. Your devices.</p>

Bujji is an open-source Windows and Android assistant for conversations, voice, local memory, reminders and focused work. Pair your phone with your laptop to run permitted Windows commands and find or copy laptop files through phone chat.

**Bring your own AI keys.** Bujji does not include somebody else's account, personal data, unlimited cloud access or model subscriptions. API charges and quotas belong to your chosen provider. Local reminders, memory and Focus do not require an AI account.

[Windows setup](docs/WINDOWS.md) · [Android setup](docs/ANDROID.md) · [Pair your devices](docs/PAIRING.md) · [AI configuration](docs/CONFIGURATION.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

## What works

| Feature | Windows | Android |
| --- | --- | --- |
| Saved chat, memory, reminders, Focus timers/tasks/history | Yes | Yes |
| Temporary Short talk | Yes | Yes |
| Voice input | Configured Gemini/Groq | Configured Gemini/Groq |
| Spoken replies | Optional Gemini TTS; experimental local voice is separate | Installed Android device voice |
| Task routing | Gemini, OpenAI, Claude, Perplexity, Groq; optional Ollama | Gemini, OpenAI, Claude, Perplexity, Groq |
| Local file search/read and reviewed file actions | Yes | Paired laptop search/read/copy to phone |
| Computer commands | Native Windows widget | Paired Windows laptop |
| Shared memory/reminders | Manual sync | Manual sync |
| Screen-time estimates and Clock handoff | — | Android permissions / system Clock |

Direct controls support app/web launch, browser tabs, window arrangement and supported accessible text controls. They are **not** unrestricted remote desktop: there is no live video, shell, wake word, password/payment/security automation or phone-to-laptop upload. Windows prompts and native validation remain. The laptop must be awake, running Bujji, and unlocked for screen actions. File copies are currently limited to 25 MB each; search/preview bounds and hidden/system/credential/link exclusions apply.

## Start here

If a community build is available on the repository's **Releases** page, use its Windows ZIP or Android APK. Otherwise build from source below. Build instructions do not require any private repository or pre-existing workspace.

### Windows from source

Prerequisites: Windows 10/11 x64, Git, **Python 3.11 or 3.12**, and **Node.js 22.12+**. Android compilation is optional and needs JDK 17 separately.

```powershell
git clone <this-repository-url> bujji
cd bujji
.\scripts\setup.ps1
# Edit .env locally: set a provider key/model and your IANA timezone.
.\scripts\desktop-start.ps1
```

Create a distributable with `scripts/desktop-build.ps1`. Extract **all** files from the resulting ZIP before launching Bujji.exe. A copied executable alone will not work. [Windows guide](docs/WINDOWS.md) covers configuration, data locations, backups and shortcuts.

### Android from source

Install JDK 17 and Android SDK Platform/Build Tools 35. Then:

```powershell
.\scripts\android-build.ps1
```

Install `android/app/build/outputs/apk/debug/app-debug.apk` on your own device. Keep the local signing key for compatible future builds. Official community releases require the maintainer's separate signing key. [Android guide](docs/ANDROID.md) includes first-run setup, permissions, updates and the Java 25 / class-file-69 fix.

### Linux/macOS development

The backend and web UI can run for development; **Windows computer control and the packaged desktop release target Windows**.

```bash
./scripts/setup.sh
# Configure .env locally, including a random owner token created by setup.
.venv/bin/python -m uvicorn bujji.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Open the localhost page and enter the owner token from your private `.env` in Settings. Do not expose this server directly to the internet. The Android app can also be built with `cd android && ./gradlew :app:assembleDebug` using JDK 17 and the Android SDK.

## First-run configuration

1. Choose your name in the app; there is no hardcoded personal identity.
2. Configure one provider's key and exact enabled model ID. Fresh-install routes use Gemini by default; choose your configured provider for all tasks or split roles in Settings.
3. Add optional voice/provider settings only if you want them. Read-aloud and external models are not prerequisites for basic local features.
4. For paired use, connect both devices to a private Tailscale network and follow [pairing](docs/PAIRING.md). Memory/reminder sync does not silently grant computer or file access.

The public Android ID is `org.bujji.companion`. Windows uses a separate `BujjiCommunity` workspace. Community builds do not overwrite a differently signed/private edition. Export/import data deliberately if migrating; keys are configured separately on each device.

## Development and contributions

```bash
python -m pip install -r requirements.lock -e '.[test]'
python -m pytest tests -q
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix frontend run test:voice
npm --prefix desktop ci
npm --prefix desktop test
python scripts/check_public_tree.py
```

[Architecture](docs/ARCHITECTURE.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Privacy](PRIVACY.md) · [Maintainer/release guide](docs/MAINTAINERS.md)

CI covers Python tests/public-tree checks, frontend/voice/desktop policy tests, Android build/tests/lint and browser flows. Release automation builds Windows ZIPs and a signed Android APK when version tags and signing secrets are configured. Build artifacts and keys are not source files.

This is community software with known platform/provider limits. Automated checks are not a claim of error-free Windows/iQOO behavior or unlimited AI availability. See [testing and limits](docs/TESTING.md) before relying on a new build for important files.

## Licence

MIT for application code. Keep [third-party notices](NOTICE.md); dependencies and optional models retain their own terms. No private keys, databases, audition recordings or model weights are included.
