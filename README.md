<p align="center"><img src="desktop/assets/icon.png" width="88" alt="Bujji logo"></p>
<h1 align="center">Bujji</h1>
<p align="center"><strong>Your assistant. Your workspace. Your devices.</strong></p>

Bujji is an open-source personal assistant for **Windows laptops/desktops and Android phones**. You can talk or type, save useful facts, set local reminders, run Focus sessions, find supported documents, and perform supported Windows actions. Pair your phone with your laptop to share memories/reminders, request laptop commands, and download permitted laptop files.

This guide assumes you have never installed a programming project before. You do **not** need to understand the code to follow the main setup. Do one section at a time and try its small test before moving on.

**Start with the laptop and typed chat. Add voice next. Add Android and Tailscale last.** You do not have to enable every feature at once.

> **Before you start:** Bujji's source code is free under the MIT licence. External AI services have their **own availability, costs and quotas**. You bring your own API keys. No personal account, unlimited AI access or paid subscription is included. Local reminders, saved memory and Focus controls can work without an AI key; asking an AI to interpret a request is a separate online feature.

<a id="contents"></a>
## Find the instructions you need

| I want to… | Go here |
| --- | --- |
| Understand what works | [Features and limits](#features) |
| Understand words such as terminal and API key | [Small dictionary](#dictionary) |
| Install Bujji on Windows for the first time | [Windows setup](#windows) |
| Get a Gemini API key and choose a model | [Gemini setup](#gemini) |
| Find and edit the correct `.env` file | [Configuration file](#env) |
| Apply a key/model change and restart | [Restart and daily launch](#restart) |
| Use the microphone, spoken replies or Short talk | [Voice](#voice) |
| Find files and create a Desktop folder | [Files and folders](#files) |
| Save a preference, reminder or Focus session | [Memory](#memory), [reminders](#reminders), [Focus](#focus) |
| Open apps, manage tabs or arrange windows | [Laptop computer control](#computer-control) |
| Use different AI providers for different tasks | [AI routing](#routing) |
| Install and set up the Android app | [Android](#android) |
| Connect laptop and phone privately | [Tailscale](#tailscale), then [pairing](#pairing) |
| Control the laptop from the phone | [Remote control](#phone-control) |
| Browse/download laptop files on the phone | [Phone file access](#phone-files) |
| Share memories and reminders between devices | [Sync](#sync) |
| Set a phone Clock alarm or screen-time nudges | [Phone extras](#phone-extras) |
| Update Bujji without losing settings | [Updates and backups](#updates) |
| Fix an error | [Troubleshooting](#troubleshooting) |
| Build an APK/Windows ZIP or work on the code | [Builds](#builds), [developer notes](#development) |
| Find official download, API and help links | [Link directory](#links) |

<a id="features"></a>
## 1. What Bujji can—and cannot—do

| Feature | Windows | Android | What to know |
| --- | --- | --- | --- |
| Saved conversations | Yes | Yes | AI replies need a configured provider and internet. Full chat history is not shared by device sync. |
| Short talk | Yes | Yes | Temporary conversation, useful brief answers, no local saved chat or action tools in this mode. |
| Microphone input | Gemini or Groq | Gemini or Groq | Recording stops after about three seconds of quiet, with a 20-second capture limit. Transcription has separate provider limits. |
| Spoken replies | Optional Gemini TTS; experimental local runtime | Installed Android text-to-speech engine | A chat model, transcription model and speech-output model are different things. |
| Saved memory/preferences | Local | Local | Explicit saved facts; not model training and not automatic access to every past conversation. |
| Reminders and notifications | Local | Local | Delivery depends on the app/service running and OS permissions. These are not Google Calendar events. |
| Deep Work / Focus | Yes | Yes | Timers, tasks, breaks and history. Quiet settings affect Bujji; they do not block every other app. |
| General local file tools | Yes | Through paired laptop access | Desktop chat can find/read supported files and prepare approved new folders, copies and new text files. |
| Windows computer commands | Native widget | Through a paired laptop | Supported apps, websites, tabs, windows and accessible controls; not arbitrary shell execution or universal automation. |
| Shared memory/reminders | Paired | Paired | **Manual** sync. Computer control and file access require additional grants. |
| Download laptop files to phone | Serves permitted files | Saves permitted files | Up to **25 MB per download**. Phone-to-laptop upload is not implemented. |
| Clock handoff and screen-time estimates | — | Yes | Requires the relevant Android capabilities/permissions; see [phone extras](#phone-extras). |

**Not included:** an always-on wake word, live remote-desktop video, unrestricted system access, silent handling of Windows security prompts, automatic two-way file transfer, full conversation-history sync, or NotebookLM integration. Gmail, Google Calendar, Google Drive, GitHub and Spotify account integrations are not part of this build. Opening one of their websites is different from connecting its account/API.

A paired laptop must be **awake, connected and running Bujji**. Windows screen actions also require an **unlocked interactive session**. A phone cannot command a switched-off laptop through this implementation.

<a id="dictionary"></a>
## 2. A small dictionary

| Word | Plain-English meaning |
| --- | --- |
| Repository / repo | The project folder hosted on GitHub. |
| Source code | The files from which the app is built. A source ZIP is not an installer. |
| Terminal / PowerShell | A window where you type commands for your computer. For the Windows instructions below, use **PowerShell**, not Command Prompt. |
| Command | An instruction you copy into PowerShell, then run by pressing Enter. Do not copy the surrounding explanation or the `PS C:\…>` prompt. |
| `.env` | A private text file containing your laptop's settings and API keys. It has no `.txt` ending. |
| API key | A private credential that lets an app call an AI provider using your project/account. Treat it like a password. |
| Model ID | The exact technical name of the model you want to use. A display name such as “Gemini Flash” is not necessarily a valid model ID. |
| Backend | The local service doing Bujji's laptop work. The Windows app starts it for you. |
| `.venv` | Bujji's separate Python environment. Setup creates it; you do not need to activate it manually for our scripts. |
| ZIP / APK / EXE | A ZIP is an archive to extract; an APK installs an Android app; an EXE runs a Windows program. |
| Tailscale / tailnet | A private network connecting your devices. Your devices must join the same tailnet. |
| Pairing | Bujji's own step for trusting a phone after networking works. It is separate from signing into Tailscale. |

### Three credentials you must not confuse

| Credential | Where it comes from | Where it belongs |
| --- | --- | --- |
| Gemini/other provider API key | The provider's website | The matching laptop `.env` line, or Android's **API key** field. |
| `BUJJI_TOKEN` | Generated locally during setup | Laptop owner connection. The browser Settings field calls this **Pairing token**; the native desktop app normally supplies it automatically. |
| Phone pairing code | Laptop **Devices → Generate phone pairing code** | Android **One-use laptop pairing code**. It has 16 hexadecimal characters and expires after ten minutes. |

**Never paste a Gemini key into the phone pairing-code field, or replace `BUJJI_TOKEN` with your Gemini key.**

<a id="windows"></a>
## 3. Install Bujji on Windows

### 3.1 Choose the correct download

Open [Bujji Releases](https://github.com/pranav9520/bujji/releases).

- If a Windows application ZIP is published, follow **3.2**.
- If no ready-made Windows application is listed, follow **3.3** to run from source.
- GitHub's green **Code → Download ZIP** gives you **source code**, not a ready-made Windows application.

An empty Releases page does not mean your download failed. It means a maintainer has not published a release there yet. Do not use unrelated executables from another repository or rename a source ZIP to `.exe`.

### 3.2 If you have a ready-made Windows application ZIP

1. Download the Windows **x64 application ZIP** from the release's **Assets** list.
2. In File Explorer, right-click it and select **Extract All**.
3. Extract to a permanent folder you control, such as a folder inside Documents.
4. Open the extracted folder and run **Bujji.exe**.
5. Keep **all** extracted files together. The EXE needs its `resources` and other files.
6. Open Bujji **Settings → Open configuration folder**. Configure its `.env` using [sections 4–5](#gemini).
7. Quit Bujji from its tray menu and reopen the EXE after saving the configuration.

For a Desktop shortcut, create a **shortcut pointing to this EXE**. Do not copy or move only the EXE onto the Desktop.

Packaged builds create their own private configuration/data workspace. They do not read a source checkout's `.env`. See the [location table](#env).

Windows may show a publisher/SmartScreen warning for an unsigned community build. Use a build from the repository/maintainer you intended to trust; compare its checksum when one is published. Do not turn off Windows security globally to install it.

**You do not need Python, Node.js or Git just to run a correctly packaged Windows ZIP.**

### 3.3 If you are running from source: install the tools once

Use Windows 10/11 **x64**. Install:

| Tool | Official download | What to choose |
| --- | --- | --- |
| Python | [Windows downloads](https://www.python.org/downloads/windows/) | Python **3.11 or 3.12**, 64-bit. These are the documented setup targets. Enable **Add python.exe to PATH** in its installer. |
| Node.js | [Node.js downloads](https://nodejs.org/en/download) | A supported LTS release **22.12 or newer**; Node 22 is used in CI. Keep npm enabled in the installer. |
| Git, optional | [Git for Windows](https://git-scm.com/install/windows) | Needed for `git clone`/`git pull`. You can instead download the source ZIP. |
| VS Code, optional | [VS Code](https://code.visualstudio.com/download) | An editor with a convenient terminal. Notepad is enough to edit `.env`. |

**You do not need Java or Android Studio for the laptop-only setup.** Those are needed only if you build the Android app yourself.

After installing Python/Node, close and reopen your terminal/editor so it sees the new tools. In PowerShell, run each line:

```powershell
python --version
node --version
npm.cmd --version
```

You should see version numbers, not “not recognized.” If Python opens the Microsoft Store, fix the Python installation/PATH first; see [troubleshooting](#troubleshooting).

### 3.4 Download the source

**Option A — no Git commands:**

1. Open [the repository](https://github.com/pranav9520/bujji).
2. Click **Code → Download ZIP**.
3. Right-click the downloaded ZIP → **Extract All**.
4. Open the extracted project folder. It should contain `README.md`, `scripts`, `backend`, `frontend` and `android`.
5. Make sure you are not still viewing the ZIP itself; File Explorer should no longer offer **Extract All** as its main action.

**Option B — with Git:** open PowerShell in the parent folder where you want the project and run:

```powershell
git clone https://github.com/pranav9520/bujji.git
cd bujji
```

You only clone once. If that folder already exists, open the existing folder or choose another location; do not delete your existing data to make the command work.

### 3.5 Open PowerShell in the correct folder

The easiest method:

1. Open the extracted/cloned project folder in File Explorer.
2. Click its **address bar** at the top.
3. Type `powershell` and press Enter.
4. A PowerShell window opens in that folder.
5. Run this check:

```powershell
Test-Path .\scripts\setup.ps1
```

It should print **True**. If it prints **False**, you are in the wrong folder. Find the folder containing `scripts`, then open PowerShell there.

In VS Code, open that same folder using **File → Open Folder**, then **Terminal → New Terminal**. Use the terminal's menu to select PowerShell if necessary.

### 3.6 Run setup

```powershell
.\scripts\setup.ps1
```

Setup creates `.venv`, installs Python packages, creates `.env` with a random private owner token, downloads frontend dependencies and builds the interface. Wait until it finishes and you can type another command. The first run needs internet and can take a while.

Then install the optional Windows-control dependencies **if you want computer control**:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[desktop-control]"
```

This extra is not installed by the basic setup script. It is included by the Windows packaging/build script. It is needed for native Windows-control operations in a source installation.

If PowerShell explicitly says scripts cannot run because of its execution policy, review the scripts you downloaded. For a trusted checkout, you can allow them for **this terminal session only**:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup.ps1
```

Do not change the machine-wide execution policy or disable your antivirus as a general setup step.

**Next:** get your own Gemini key, edit `.env`, then launch the app. You do not need to compile a Windows EXE to use the source version.

<a id="gemini"></a>
## 4. Get a Gemini key and choose the right model

### 4.1 Create your own key

1. Open [Google AI Studio API keys](https://aistudio.google.com/apikey).
2. Sign in with your own Google account.
3. Accept the service's terms if you want to use it and are eligible.
4. Choose **Create API key** or the equivalent current button.
5. Select/create the Google Cloud project requested by the page. If there is no eligible project, follow the page's project-creation instructions.
6. Copy the generated key. You will paste it into your private configuration—not a chat, issue, screenshot or public README.

Google can change button names, project requirements, region eligibility, free-tier access and quotas. The official [API-key guide](https://ai.google.dev/gemini-api/docs/api-key) is the reference if its page differs.

Do not enable billing simply because a tutorial says to. First check [pricing](https://ai.google.dev/gemini-api/docs/pricing) and [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits). An API account/project is separate from a consumer Gemini subscription.

### 4.2 Model IDs must be exact

The general-purpose example in this guide is:

```env
GEMINI_MODEL=gemini-3.8-flash
```

This is a **model ID**, not an API key. It is listed in Google's [model catalogue](https://ai.google.dev/gemini-api/docs/models) and has a [model page](https://aistudio.google.com/docs/models/gemini-3.8-flash). The linked documentation lists text, image, video, audio and PDF inputs, with text output.

**Check that your project actually has access to it.** Provider models and free-tier availability change. If it is unavailable, use an exact currently enabled model ID from the official catalogue/your account, with the capabilities you need. An older tutorial's model ID is not a permanent guarantee of availability.

Examples of different jobs:

| Job | Example configuration | Capability needed |
| --- | --- | --- |
| Normal replies/file planning | `GEMINI_MODEL=gemini-3.8-flash` | Text replies; structured JSON for tools. |
| Microphone transcription on the laptop | `GEMINI_STT_MODEL=gemini-3.8-flash` | Audio input → text. |
| Document OCR on the laptop | `GEMINI_DOCUMENT_MODEL=gemini-3.8-flash` | Image/PDF input → extracted text. |
| Spoken laptop replies | `GEMINI_TTS_MODEL=gemini-3.8-flash-tts` | Text → generated audio. See the [speech guide](https://ai.google.dev/gemini-api/docs/speech-generation). |

**Do not put a TTS model in `GEMINI_MODEL` just because you want voice.** A speech-output model is not your general chat/transcription model. Bujji's supported desktop speech-output IDs are listed in [tts.py](backend/bujji/tts.py); changing to an arbitrary newer TTS ID may need a code update.

### 4.3 Can I use the same key on my own laptop and phone?

Yes, you can configure your own key on both of your devices if your provider's terms/project allow that. Requests still share that project's quota/billing. Pairing does not copy API keys between devices. A friend setting up a separate Bujji should create **their own key**.

<a id="env"></a>
## 5. Where to put the key: the correct `.env`

### 5.1 Find the file used by the version you are running

| How you run Bujji | Configuration to edit |
| --- | --- |
| Source, using `desktop-start.ps1` | `.env` inside your cloned/extracted project folder, beside `README.md`. |
| Packaged Windows EXE | `%APPDATA%\BujjiCommunity\workspace\.env`. Start the app once to create it, then use **Settings → Open configuration folder**. |
| Android APK | No `.env` editing. Use the app's **Settings → API key** and **Model ID** fields. |

For a packaged app, you can also press **Windows + R**, paste the following folder path, and press Enter:

```text
%APPDATA%\BujjiCommunity\workspace
```

Changing a source folder's `.env` does **not** configure an already packaged EXE. Changing `.env.example` configures **neither** running version; it is a template.

### 5.2 Open and edit it

For a source setup, from the same project PowerShell window:

```powershell
notepad .env
```

For a packaged app, open the configuration folder and open its `.env` in Notepad/your editor.

Find these lines and replace only their values:

```env
GEMINI_API_KEY=paste_your_own_actual_key_here
GEMINI_MODEL=gemini-3.8-flash
BUJJI_TIMEZONE=Asia/Kolkata
```

- Replace `paste_your_own_actual_key_here` with the key you copied. Do not leave that example text there.
- Paste only the key value after `=`. Do not paste `GEMINI_API_KEY=` a second time.
- Use the exact model ID with no accidental spaces or extra words.
- `Asia/Kolkata` is appropriate for India. Use your own [IANA timezone name](https://www.iana.org/time-zones) elsewhere, such as `Europe/London` or `America/New_York`.
- The generated template defaults to UTC. Choose your actual timezone before testing reminders.
- Keep the generated **`BUJJI_TOKEN`**. Do not erase it, share it, or replace it with the provider key.
- Keep the existing storage/port settings unless you deliberately need to change them.
- Do not add several active copies of the same setting. Edit the existing line.
- A line beginning with `#` is a comment and is not active. Remove the initial `#` when enabling an optional setting.

Press **Ctrl + S** to save. If Notepad opens **Save As**, use the name `.env` and **Save as type: All files**, not `.env.txt`. In File Explorer, enable **View → Show → File name extensions** to check the real name.

If `.env` is missing after a source setup, run setup again. It creates the file only when missing and keeps existing configuration. Do not overwrite an existing `.env` by copying the whole template over it; that can erase your generated token and keys.

### 5.3 Start with one provider for every chat task

A fresh template has these defaults:

```env
BUJJI_DAILY_PROVIDER=gemini
BUJJI_STUDY_PROVIDER=gemini
BUJJI_RESEARCH_PROVIDER=gemini
BUJJI_CODING_PROVIDER=gemini
BUJJI_WRITING_PROVIDER=gemini
BUJJI_ANALYSIS_PROVIDER=gemini
```

Keep these while learning the app. If you previously saved different routes in Settings, those **saved routes take priority**. Open **Settings → AI task routing**, choose Gemini for all six categories, then **Save AI routes**. Do not use **Use suggested routes** until you have configured the providers it selects.

A “Web research” category routed to a general model does not by itself enable live web browsing. The Perplexity route has the explicit research/web tools; see [routing](#routing).

<a id="restart"></a>
## 6. Apply changes, launch and use Bujji each day

### 6.1 After editing `.env`

1. Save the file with **Ctrl + S**.
2. If Bujji is running, find its icon in the Windows system tray near the clock. The small **up-arrow** may reveal hidden icons.
3. Use its tray menu → **Quit Bujji**. Clicking the window's **X** normally only hides it; that does not reload `.env`.
4. Start the **same version** you configured:

**Source installation:**

```powershell
.\scripts\desktop-start.ps1
```

**Packaged installation:** open `Bujji.exe` in its extracted application folder, or its shortcut.

**You do not need to rebuild, reinstall, delete data or restart Windows just to apply a key/model change.** You need the running backend to restart.

### 6.2 First successful test

1. Choose your name when **Make Bujji yours** appears.
2. Open **Conversation** or choose **Type instead**.
3. Type `Hi` and send it.
4. Wait for a reply before testing files or remote commands.
5. If it fails, use the exact error in [troubleshooting](#troubleshooting).

The native desktop app normally supplies its owner token automatically. If you deliberately run the browser-only server, its Settings **Pairing token** field needs the private `BUJJI_TOKEN` value, not a Gemini key.

### 6.3 Normal daily launch

For source mode, open PowerShell in the project folder and run `desktop-start.ps1` again. The terminal can stay busy while Electron is running; leave it open/minimized for that session. You do not need to rerun setup every day.

The first desktop launch may download Electron if it is not installed yet. Later launches reuse it. Closing to tray keeps the app's backend/reminders active. **Quit Bujji** stops it. A source install does not automatically become a startup app; packaged builds expose **Launch at Windows sign-in** in Settings.

Use `desktop-start.ps1` for the Windows app. `start.ps1` is a browser-only development server; it does not give you the desktop bridge or automatically discover native file locations in the same way.

<a id="voice"></a>
## 7. Enable and test voice

There are **three separate steps**: record/transcribe what you say, generate a text reply, then optionally read that reply aloud. Success at one step does not prove the others are configured.

### 7.1 Laptop microphone input

Add/edit these laptop `.env` settings:

```env
BUJJI_STT_PROVIDER=gemini
GEMINI_STT_MODEL=gemini-3.8-flash
```

This uses your existing Gemini key and a model that accepts audio. Save and [restart Bujji](#restart).

1. In Windows, open **Settings → Privacy & security → Microphone** and allow microphone access for the relevant desktop apps. Windows 10 wording can differ.
2. In Bujji Settings, choose **Speech recognition language** appropriate to your speech.
3. Choose **Talk to Bujji** and allow a microphone prompt if shown.
4. Say a short clear sentence, then pause.
5. Around three seconds of quiet ends the recording. You can also stop it manually. A recording is limited to 20 seconds.

In normal conversation, the transcript can submit automatically. To check it before sending, enable **Review voice before sending** in Conversation. This is a separate control; do not assume the Deep Work timer switch is a universal transcript-review setting.

Fans/background speech can affect silence detection. Start with a short sentence in a quiet room. This is not always-on wake-word listening.

### 7.2 Laptop spoken replies

For optional Gemini speech output:

```env
BUJJI_TTS_PROVIDER=gemini
GEMINI_TTS_MODEL=gemini-3.8-flash-tts
```

Keep `GEMINI_MODEL` and `GEMINI_STT_MODEL` as general/audio-input models. Confirm access to the separate TTS model in your project, save, and restart.

- Use **Read aloud** on an assistant reply for a first test.
- To read future replies automatically, enable **Settings → Bujji’s voice → Automatically speak replies**.
- **Stop voice** or starting the microphone interrupts playback.
- Check Windows output volume and Bujji/backend app volume if you hear nothing.

A voice quota error can leave text chat fully usable. A Gemini microphone-transcription 503 is about **input speech**, not necessarily the voice selected for output. Read the specific message before changing settings.

### 7.3 Optional Groq transcription

If you want Groq instead of Gemini for laptop microphone input, get a key from [Groq](https://console.groq.com/keys) and use:

```env
GROQ_API_KEY=paste_your_own_groq_key_here
BUJJI_STT_PROVIDER=groq
GROQ_STT_MODEL=whisper-large-v3-turbo
```

Keep chat routing unchanged unless you also intend to configure a Groq **chat** model. An STT model is not a chat model. Save/restart and test the microphone again. Groq has its own access and usage limits; selecting it is not unlimited free speech.

### 7.4 Short talk

On the home screen, choose **Short talk** for a temporary spoken conversation. It keeps responses brief and does not navigate into the normal saved conversation flow.

- It can answer ordinary, study and factual questions briefly.
- It does not run file actions, save memories or schedule reminders through its temporary chat tools.
- End Short talk to discard its local temporary context.
- “Unsaved” refers to Bujji's local history, not a promise about a remote provider's retention.

### 7.5 Experimental local laptop voice

Skip this for the simplest setup. The default community build does **not** bundle local model weights or a celebrity voice clone.

Developers who deliberately want the optional local CPU voice should first read [Voice options](docs/VOICE.md), the [pinned model manifest](backend/bujji/assets/hima-a.json), and the [upstream model page and terms](https://huggingface.co/Prahaladha/hima-tts-nano-te-ONNX). The application licence does not grant model rights.

For a source install, after reviewing/accepting the upstream terms:

```powershell
.\scripts\setup-local-voice.ps1 -AcceptModelLicense
```

Then set `BUJJI_TTS_PROVIDER=hima` in the source `.env`, restart and test a short reply. This adds separate runtime/model downloads and can use CPU/RAM during synthesis. Download size is not the same as RAM consumption, and pronunciation/latency depend on the model/hardware.

A packaged app needs a build containing the optional runtime and correctly installed assets in its **packaged workspace**. Running the source setup script alone does not add missing modules to an existing EXE. See [building](#builds) and [Voice options](docs/VOICE.md).

<a id="files"></a>
## 8. Find documents and create a Desktop folder

Use the **Windows desktop application** for this—not a source ZIP filename, Short talk, or an ordinary web page without the native desktop context.

### First test with dummy files

1. Create a small text file in Downloads named `bujji-test.txt`. Put a harmless sentence inside it.
2. Open Bujji **Conversation**.
3. Expand **Tools** and enable **File access**.
4. For this first test, choose **Daily chat** and **Gemini**/a configured general chat provider. Leave **Collaborative AI** off.
5. Ask: `Find bujji-test.txt in Downloads and tell me what it says.`
6. Confirm the returned file/path is the one you made.
7. Ask: `Create a new folder called Bujji Test on my Desktop and copy bujji-test.txt into it.`
8. Review the exact proposed paths/actions. Choose **Approve and run** if they are correct.
9. Open the Desktop folder in File Explorer and check the copy.

Bujji discovers the available locations itself; you do not need to type your Windows username or pre-select a certificate folder. If several files match, clarify which one. Do not approve an invented or incorrect path.

The file agent supports approved **create folder**, **copy**, **write a new supported text/code file**, and **remember** actions. It does not silently overwrite an existing destination. It does not expose arbitrary shell commands, delete/move/rename operations or unrestricted editing of existing files.

**A proposal is not completion.** Check the execution results. If one step fails, earlier successful steps can remain; subsequent steps stop. Do not assume the app rolled the whole plan back.

### Supported reads and limits

- UTF-8 text/code, text-based PDFs and DOCX are supported for local text reading.
- Desktop document read/copy helpers impose a **10 MB per-file** bound. PDF text reading is limited to **ten pages** in this workflow.
- PNG/JPEG or scanned PDFs need OCR rather than ordinary text extraction.
- Search is bounded, not a complete permanent index of every drive. A partial search or no match is not proof the file does not exist. Try a narrower location and a distinctive filename.
- Hidden/system/dependency/credential paths, links and protected locations are excluded. Windows permissions still apply.
- Remote phone **downloads** use a different **25 MB** limit; downloading a file and extracting its contents are different operations.

### Optional OCR for images/scans

1. Configure a Gemini model that accepts the document type, for example:

```env
GEMINI_DOCUMENT_MODEL=gemini-3.8-flash
```

2. Save/restart.
3. In Conversation → **Tools**, check **OCR for images / scans** for that request.
4. Ask about the specific document.

OCR sends the image/PDF to Gemini. The app resets the per-request OCR choice; do not assume a later scan automatically has cloud OCR permission. OCR can fail on handwriting, poor images or quota/access limits. Review important extracted text yourself.

<a id="memory"></a>
## 9. Save useful facts in Memory

1. Open **Memory** on the laptop or phone.
2. Use its add/save control to enter a short fact, such as `I prefer concise explanations with examples.`
3. Save it and check it appears in the list.
4. Ask a relevant follow-up in normal chat.

On the laptop, a conversation request to remember a fact can also produce an approval through the file/memory agent. On Android, supported action requests can present their own review card. Until saved/approved, an AI sentence saying “I will remember” is not proof of storage.

You can edit/delete memories using the available app controls. Memory means selected saved facts are supplied as future context; it does not train a new model or automatically make every old conversation available. Use [manual sync](#sync) to share saved memories across paired devices.

<a id="reminders"></a>
## 10. Set reminders and hear notifications

### Windows

1. Open **Reminders** or the home-screen reminder shortcut.
2. Add a title, future date/time and recurrence if wanted.
3. Save it and check it appears as upcoming.
4. In **Settings → Windows desktop**, enable **Reminder sounds**.
5. Choose **Test notification & sound**. If needed, try **Test sound only**.
6. Check Windows **Settings → System → Notifications**, output device and Volume mixer if the test does not work.

For your first real test, set a reminder two or three minutes ahead and keep Bujji running. Do not enable Quiet Bujji reminders during this test.

Closing Bujji to the tray keeps its service alive. Quitting it or shutting down the laptop cannot deliver a real-time alert while it is off. Late reminders can be recorded as missed when the service runs again.

### Android

1. Open **Reminders → Add reminder**.
2. Enter the title/time and save.
3. Use the app's notification-permission prompt/banner if notifications are off.
4. In Settings → **Permissions**, enable **Reminder notifications** and, where supported, **Precise reminder timing**.
5. Choose **Send a test notification**.
6. Test a near-future reminder with the phone locked as well as unlocked.

Android notification channels, volume, Do Not Disturb and the phone maker's battery settings affect delivery/sound. Exact-alarm permission improves scheduling but is not a promise that an OEM will never delay an alert.

Bujji reminders are **local app reminders**, not automatic entries in Google Calendar. A reminder synchronized to both devices can alert on both.

<a id="focus"></a>
## 11. Use Focus / Deep Work

On Windows, turn on the sidebar **Focus mode** switch. On Android, open **Focus**.

1. Choose what you want to work on.
2. Set work minutes, break minutes and number of sessions.
3. Choose **Start focus**.
4. Use **Pause**, **Resume**, **End** or **Reset** as appropriate.
5. Add tasks and mark completed ones.
6. If you want, enable **Quiet Bujji reminders** and automatic breaks.

Quiet settings reduce Bujji's own ordinary alerts. They do **not** block all websites, silence every other app, or enable system-wide Do Not Disturb. Work/break notifications can still appear. The next work round can wait for you to start it after a break.

History and totals measure timer/session time, not your actual concentration. Set **Review voice before sending** separately if you want to check transcriptions.

**Advanced AI collaboration:** Conversation → **AI collaboration → Collaborative AI** is a separate optional workflow: plan → build → review → revise. It makes multiple AI calls and can take longer/use more quota. Its “review” is model-generated critique, not proof that code was executed or tests passed. Leave it off for first setup and ordinary file tests.

<a id="computer-control"></a>
## 12. Control the laptop with Bujji's widget

### Enable it

1. Run the **Windows desktop app**, not just the browser-only backend.
2. For a source install, install the [Windows-control extra](#windows) if you skipped it.
3. Configure the laptop's general AI route. Some simple commands use local fast paths; more complex requests need its model/key.
4. On Overview, choose **Control my computer**. Keep the widget open while using it.
5. Type a harmless command and choose **Run command**, or choose **Listen** to speak.

Try these individually:

```text
Open YouTube
Open Notepad
Put Notepad on the left
New tab
Search for Python tutorials
```

Website/search launch often works without selecting an app first. For an ambiguous window command, expand **Options → Target app**, choose the intended open window, or choose **Refresh apps**. Automatic targeting cannot always choose correctly among several matching windows.

### Screen text, typing and clicking

Enable **Read target app text** only when you want Bujji to inspect the selected app's accessible text. Window titles can already be sent to the planner; enabling text reading adds accessible contents to the request. It is **not** a live screenshot/video feed. An app that exposes little accessibility information may not be controllable this way.

Typing/clicking requires a supported inspected control, not just an arbitrary place on a screen. Passwords, terminals, payment/security actions and other protected controls are restricted. Windows security prompts/UAC still apply. An elevated or locked app may not accept control.

Supported commands normally run directly once control is enabled. This does not remove native validation, restrictions, or the separate approval needed for file-agent changes.

- **Stop** stops pending/remaining work; already completed actions are not undone.
- **Keep listening** can rearm capture while this control surface is active. It is not a system-wide wake word.
- **Speak replies** reads results if speech output is configured.
- After suitable completed steps, **Save routine** can save app/website/tab/window sequences. Typing/click routines are not saved because their screen targets change.

<a id="routing"></a>
## 13. Choose different AI providers for different jobs

You can keep Gemini for everything initially. Add other providers only if you want them and understand their API pricing.

| Provider | Get a key | Model reference | Laptop variables |
| --- | --- | --- | --- |
| Gemini | [AI Studio keys](https://aistudio.google.com/apikey) | [Models](https://ai.google.dev/gemini-api/docs/models) | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| OpenAI | [API keys](https://platform.openai.com/api-keys) | [Models](https://platform.openai.com/docs/models) | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Anthropic / Claude | [API keys](https://platform.claude.com/settings/keys) | [Model overview](https://platform.claude.com/docs/en/about-claude/models/overview) | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| Groq | [Console keys](https://console.groq.com/keys) | [Supported models](https://console.groq.com/docs/models) | `GROQ_API_KEY`, `GROQ_MODEL` |
| Perplexity | [API account/keys](https://www.perplexity.ai/account/api/keys) | [API documentation](https://docs.perplexity.ai/) | `PERPLEXITY_API_KEY`, `PERPLEXITY_MODEL` |
| Ollama, optional laptop only | [Download](https://ollama.com/download) | [Model library](https://ollama.com/library) | `OLLAMA_ENABLED=true`, `OLLAMA_MODEL` |

For a laptop provider, add its own key and exact enabled **model ID** to `.env`, save and restart. Then open **Settings → AI task routing**, select the provider for the categories you want, and **Save AI routes**.

Example choices—not mandatory requirements:

| Category | Possible choice |
| --- | --- |
| Daily chat | Gemini or another general chat provider |
| Study | OpenAI or your preferred general model |
| Web research | Perplexity, configured for its research route |
| Coding / writing | Claude or your preferred general model |
| Analysis | OpenAI or another supported general model |

A ChatGPT/Claude website subscription does not automatically pay for API use. NotebookLM is not integrated. Giving a model the “Study” task does not give it automatic access to your notebooks, Drive or Google account.

Perplexity is a research route with web-search/source handling, not a local-action planner. Use a configured general chat provider for local file tasks. Ollama requires a separately installed local server and downloaded model, with hardware/resource needs of its own.

Chat routing does **not** change microphone or spoken-reply settings. Bujji does not silently rotate accounts or charge another provider when the chosen one fails. A saved route pointing to an unconfigured provider stops with an error; change the route or configure that provider.

<a id="android"></a>
## 14. Install and configure Android

### 14.1 Get a compatible APK

The app's minimum Android version is **Android 8.0**. Features/permission handling vary with newer Android versions and phone manufacturers.

1. Look for an Android APK in [Bujji Releases](https://github.com/pranav9520/bujji/releases), if one is published.
2. If no APK is published, ask the maintainer for an intended build or follow [building an APK](#builds). The source ZIP is not an APK.
3. Transfer/download the APK to your phone using your own trusted method.
4. Tap the APK in the phone's Files/Downloads app.
5. If Android asks, temporarily allow installation from that browser/file manager and finish installing.
6. Open Bujji. Remove that source's installation permission afterward if you no longer need it.

For one-off testing, a successful [CI run](https://github.com/pranav9520/bujji/actions/workflows/ci.yml) can provide an `android-debug` artifact: sign in to GitHub, open a successful **main** run, find **Artifacts**, download/extract the ZIP, then use the APK inside. Artifacts expire. These are test builds, not stable signed releases; different CI runs can use different debug signing keys and may not update over one another.

The community app ID is `org.bujji.companion`. A differently named/signed private edition is not automatically migrated. Do not uninstall an old app with important data before backing it up.

### 14.2 Configure one provider first

1. Enter your preferred name and choose **Continue**.
2. Open **Settings** using the app's settings control.
3. Set **AI provider** to Gemini.
4. Set **Model ID** to an exact audio/text-capable ID available to your project, such as `gemini-3.8-flash`.
5. Paste the **key value only** into **API key**. Do not paste an entire `GEMINI_API_KEY=…` line.
6. Set **Voice input provider** to Gemini for the simplest first setup.
7. Check **Use this provider for all chat tasks**. This avoids unconfigured specialist routes during your first test.
8. Optionally enable **Speak replies**.
9. Choose **Save settings**.
10. Open **Chat**, type `Hi`, and test before using the microphone.

Android saves its settings locally; you do not need to edit the laptop's `.env` or rebuild the APK to change this key. When revisiting settings, **Key saved · leave blank to keep** means the existing key is stored; do not keep pasting it unnecessarily. Configure additional providers one at a time, then set routes under **AI task routing**.

The phone's key and the laptop's key are independent settings. Pairing them does not copy either one.

### 14.3 Voice on Android

- Allow microphone permission when prompted.
- Use **Talk to Bujji** for normal conversation or **Short talk** for temporary conversation.
- Three seconds of quiet ends a recording; input still goes to the configured transcription provider.
- Chat → **Options → Review voice transcripts** controls review before normal submission.
- Spoken output uses the phone's installed **Android text-to-speech engine**, not the laptop's Gemini/local voice.
- If pronunciation/language is poor, open Android Settings and search for **Text-to-speech output**. Choose/install a suitable engine/language/voice, then test its sample. Phone menu names vary.
- Changing the laptop's TTS model does not change the phone's device voice.

<a id="tailscale"></a>
## 15. Connect the devices with Tailscale

**Do this only after Bujji works separately on the laptop and phone.** Tailscale supplies the private network; Bujji pairing supplies app permissions. You need both for cross-device work.

The devices can use different Wi-Fi/mobile networks. They must both be online and joined to the **same tailnet**. Merely using the same home Wi-Fi is not enough for this pairing method.

### 15.1 Install and sign in

1. Install [Tailscale for Windows](https://tailscale.com/download/windows) on the laptop.
2. Open it and sign in. Follow its setup if you are creating a personal network for the first time.
3. Install [Tailscale for Android](https://tailscale.com/download/android) on the phone.
4. Sign in using the same Tailscale account/tailnet for this simple two-device setup.
5. Approve Android's VPN-connection prompt and turn the connection on.
6. Check both devices appear online in the [Tailscale Machines page](https://login.tailscale.com/admin/machines).

Your Tailscale sign-in does **not** have to be the same account that owns your Gemini API key. It is the two devices' **tailnet** that must match. Review Tailscale's [personal-use/pricing terms](https://tailscale.com/pricing) for your situation.

### 15.2 Check the Windows command works

Open a **new** PowerShell window after installation:

```powershell
tailscale version
tailscale status
```

If `tailscale` is not recognized, close/reopen PowerShell. If it is installed in the standard Windows location, you can test it with:

```powershell
& "$env:ProgramFiles\Tailscale\tailscale.exe" version
```

If that works but the short command does not, use the full path for the commands below or fix PATH through Tailscale's installation instructions. Do not change unrelated system paths blindly.

### 15.3 Start the laptop app, then enable private HTTPS forwarding

1. Start **Bujji's Windows desktop app** and leave it running.
2. Keep its default `BUJJI_DESKTOP_PORT=8765`, unless you intentionally configured another port.
3. In a separate PowerShell window, run:

```powershell
tailscale serve --bg http://127.0.0.1:8765
```

This tells Tailscale: “Send private HTTPS traffic for this laptop to Bujji's local service.” `--bg` keeps Serve's forwarding configuration in the background; it does not keep Bujji itself running.

If Tailscale prints a link asking you to enable HTTPS/Serve, open that **official Tailscale link**, sign in as the tailnet administrator and follow it. Tailscale may ask for HTTPS certificates/MagicDNS settings to be enabled. Then run the command again. Use the official [Serve instructions](https://tailscale.com/kb/1242/tailscale-serve) and [HTTPS setup guide](https://tailscale.com/kb/1153/enabling-https) if the prompts differ.

Now check:

```powershell
tailscale serve status
```

You should see an HTTPS address and a target such as `http://127.0.0.1:8765`. Copy the **actual HTTPS address printed for your laptop**. It will look similar to this example:

```text
https://my-laptop.tail123456.ts.net
```

**Do not copy that example as your own address.** Your machine/tailnet names will differ.

### 15.4 Which address should I paste into Bujji Android?

Use the HTTPS `.ts.net` origin from **Serve status**:

- Start with `https://`.
- Use your own complete machine/tailnet name ending in `.ts.net`.
- Do not use `localhost`, `127.0.0.1`, a `100.x` IP address, `http://`, `:8765`, an `/api` path or a pairing code as the address.
- The current Android client accepts this private Tailscale HTTPS form on its normal HTTPS port. It is not a generic custom-server URL setting.

If you changed `BUJJI_DESKTOP_PORT`, use that port in the **Serve target**. The phone still uses the HTTPS address Serve publishes. The browser-only development server's default port is 8000; that is a different launch method. Use the native desktop method for the guide's full feature set.

Keep this private. **Do not use Tailscale Funnel or public router port forwarding.** If you already use Serve for another service, inspect its configuration before replacing its root target; do not reset another project's routes just to follow this guide.

After a reboot, verify Tailscale is connected and **start Bujji again**. Serve forwarding can persist, but it cannot forward to a backend that is not running.

<a id="pairing"></a>
## 16. Pair Bujji Android with the laptop

### On the laptop

1. Open **Devices**.
2. Expand **Setup** if you want to see the built-in connection instructions.
3. Choose **Generate phone pairing code**.
4. Keep the resulting **16-character code** handy. It is one-use and valid for ten minutes.

### On the phone

1. Open Bujji **Settings**.
2. Scroll to **Laptop connection**.
3. In **Laptop Tailscale HTTPS address**, paste your actual Serve HTTPS address.
4. In **One-use laptop pairing code**, paste the code just generated—not an API key or `BUJJI_TOKEN`.
5. Read and check the memory/reminder sharing confirmation if you want to pair.
6. Choose **Pair my laptop**.

If it says the code expired/locked/incorrect, generate a new code on the laptop. Five failed code attempts lock that code. Copy it carefully without extra spaces/characters.

### Grant only the extra features you want

Back on the laptop, choose **Devices → Refresh connected devices**. Find your phone. The separate switches are:

- **Phone control**: allows supported remote laptop commands.
- **Browse/download files**: allows permitted read-only laptop file access/downloads.

Pairing initially enables memory/reminder sync; it does **not** automatically grant both of these extra permissions. Turn them on for your own phone if you want the following features.

Use **Revoke** on the laptop if a phone is lost/no longer trusted. Android's **Disconnect phone** clears its connection; it is not a substitute for revoking a credential on the laptop when a device is lost.

<a id="phone-control"></a>
## 17. Control the laptop from the phone

1. Keep Tailscale connected on both devices and Bujji running on an awake, unlocked laptop.
2. Enable that phone's **Phone control** switch on the laptop.
3. On Android Home → **Connected devices**, choose **Control laptop**.
4. Start with typed `Open Notepad`, then choose **Run**.
5. Watch the laptop and check the returned action result.
6. Test **Speak** afterward, once phone microphone transcription works.

In **Screen options**, leave **Auto target** for simple commands. Use **Refresh open windows** and **Target window** when several windows make the request ambiguous. **Read accessible screen text** sends permitted text to the laptop's selected AI provider; enable it only when needed.

**Keep listening** can rearm capture while this control page is active. It is not an Android background wake-word service. **Stop** halts remaining steps, not actions already completed. If a request times out, check the laptop before repeating it; a delivered action might already have happened.

The laptop still performs the action. The phone is not streaming a live desktop video, unlocking the PC, bypassing UAC, or taking unrestricted control of every program.

### Which device needs which key?

| Activity | Configuration used |
| --- | --- |
| Standalone phone chat | Phone's saved provider/model/key |
| Phone microphone transcription | Phone's selected voice-input provider/key/model |
| Phone spoken output | Android's installed device voice |
| Remote command planning or laptop file-agent reasoning | Laptop's configured route/model/key; some simple fast paths do not call AI |
| Laptop cloud speech/transcription | Laptop's own `.env` speech settings |

Configuring only the phone does not configure the laptop's AI tools, and vice versa.

<a id="phone-files"></a>
## 18. Find and save laptop files on the phone

Enable the paired phone's **Browse/download files** grant and keep laptop **Conversation → Tools → File access** enabled.

### Through normal phone chat

1. Put a small dummy PDF/text file in laptop Downloads.
2. Open Android **Chat**.
3. Ask `Find bujji-test.txt in my laptop Downloads.`
4. Choose the correct candidate if several appear.
5. Use **Save** on the file card.
6. On Android 10+, check the phone's **Downloads/Bujji** folder. Older Android versions may open a **Save as** document picker instead.

An explicit transfer request such as `Send bujji-test.txt from my laptop Downloads to this phone` may auto-save a single verified, non-partial match. Multiple or partial matches remain manual. A match appearing in chat is not proof the download succeeded—look for the saved receipt/file.

### By browsing

In Android Chat, choose **Laptop files**. Open a permitted root/folder, browse or search, select a file and choose the save control. This is an alternative when you are unsure of its exact name. You do not have to know the full Windows path before trying discovery.

**Limits:** up to **25 MB per download**, excluded/protected paths remain blocked, searches are bounded, and not every downloadable format has a text preview. Files such as spreadsheets/archives can require another phone app to open them. This version does not upload phone files back to the laptop.

For a remote file task, use normal Chat, not Short talk. If the phone's automatic intent recognition misses your wording, open Chat **Options → Search laptop for this chat**, or choose **Laptop files** explicitly.

<a id="sync"></a>
## 19. Manually sync saved memories and reminders

1. Pair both devices and keep them online.
2. On Android → **Settings → Laptop connection**, choose **Sync now**.
3. Check Memory/Reminders on both devices.
4. After making more changes, choose **Sync now** again.

This exchanges **saved memories and reminder records**. It does not share API keys, full chat histories, every document, Focus history, notification history or app settings. Sync is not automatic continuous cloud backup.

If you edit the same record differently on both devices before syncing, a conflict can occur. Android's **Sync recovery** area can retain a phone copy when a laptop version wins. Read/copy any details you want to keep into a new record before discarding anything. Shared reminders can notify on both devices.

For a first test, save a harmless memory such as `Demo preference: short replies`, sync, and check it appears on the other device.

<a id="phone-extras"></a>
## 20. Android Clock, screen time and permissions

### Clock alarm handoff

Open **Reminders → Clock alarm**, enter a label/time and choose **Open Clock to confirm**. Bujji asks the installed Clock app to handle it.

**Check the actual day and time inside Clock before saving.** Android's generic alarm handoff cannot reliably pass an arbitrary future date to every Clock app. Bujji cannot verify that another app accepted the alarm. A local Bujji reminder and a system Clock alarm are separate things.

### Screen-time estimates and break nudges

1. Open Bujji **Settings → Screen time**.
2. Use **Open Usage Access** / **Manage Usage Access**.
3. In Android's list, find Bujji and allow Usage Access if you want this feature.
4. Return to Bujji and refresh the estimate.
5. Enable **Remind me to take a break**.
6. Choose a **Daily budget (minutes)**. For eight hours, enter **480**.
7. Choose a nudge interval and quiet hours, then **Save my balance settings**.

The estimate uses Android usage events, not your messages or a screenshot stream. It may differ from Digital Wellbeing. Background checks run roughly every 15 minutes and can be delayed by Android. There are up to three nudges per day outside quiet hours; Quiet Focus can suppress them.

### If alerts do not arrive

In Bujji **Settings → Permissions**, use the controls for notifications, precise reminders and battery/background settings. On the phone, menu names vary; search Android Settings for **Bujji**, **Notifications**, **Alarms & reminders**, **Usage access**, or **Battery**. Allow background activity where appropriate, then test while locked. On some phones, force-stopping an app prevents background work until it is opened again.

<a id="updates"></a>
## 21. Updating, restarting and backups

### Changing a key/model is not a software update

Edit the correct `.env`, save, quit the tray process and reopen the same app. On Android, save the changed Settings. **Do not delete your database, reinstall the app or rebuild an APK just to change a key.**

### Before a software update

- Quit Bujji completely.
- For a source install, privately copy `.env` and the configured data folder (`data` by default). Custom data locations need their own backup.
- For a packaged Windows build, privately back up `%APPDATA%\BujjiCommunity` so its workspace/settings are included.
- On Android, use **Settings → Export backup** and save that JSON somewhere you control. Imports use **Import & merge**, not a guaranteed full cross-platform migration.
- Backups can contain private conversations/memories. Android exports exclude API keys; Windows `.env` backups contain secrets. Do not upload these to an issue or public repo.

### Source cloned with Git

From the project folder, after quitting Bujji and backing up:

```powershell
git pull --ff-only
.\scripts\setup.ps1
.\.venv\Scripts\python.exe -m pip install -e ".[desktop-control]"
.\scripts\desktop-start.ps1
```

The control-extra line is needed only if you use Windows control. If Git reports local changes, a merge conflict or that it cannot fast-forward, stop and ask for help. Do not use `reset --hard` or delete your workspace just to force the update.

### Source downloaded as ZIP

Download/extract the new source into a **new** folder. While the old app is stopped, privately copy your `.env` and data to the appropriate new location, then run setup there. Do not copy old `.venv`, `node_modules` or build outputs as a substitute for setup. Compare new template settings with your configuration rather than overwriting your token/keys. Keep your backup until the new version is working.

### Packaged Windows update

Quit the tray app, extract the entire new application ZIP into a new application folder, and run its EXE. Community packaged settings/data remain in the separate AppData workspace. Update your shortcut to point to the new EXE. Do not open old and new builds against the same data simultaneously.

### Android update

A compatible update needs the **same package ID and signing key**, with a suitable version code. Keep your own local debug keystore or the maintainer's stable release-signing identity for future builds. An APK from a different debug CI run may not match. Do not uninstall an app containing important data just to bypass a signing error; export first and understand the migration.

<a id="troubleshooting"></a>
## 22. Troubleshooting by symptom

| What you see | What it usually means | What to do |
| --- | --- | --- |
| `python` opens Microsoft Store / is not recognized | Python is missing or PATH/Windows app aliases point elsewhere. | Install the documented Python, enable its PATH option and reopen the terminal. Check **Manage app execution aliases** if the Store alias keeps intercepting it. |
| Node/npm is not recognized | Missing Node installation or an old terminal environment. | Install Node LTS, reopen PowerShell, check `node --version` and `npm.cmd --version`. |
| `npm.ps1 cannot be loaded` | PowerShell is selecting a script wrapper. | Use `npm.cmd` as shown; for project `.ps1` files use the session-only execution-policy step if appropriate. |
| `scripts/setup.ps1` not found | Wrong folder or still inside a ZIP. | Extract, open the folder containing `scripts`, and confirm `Test-Path .\scripts\setup.ps1` prints True. |
| A ZIP filename is “not recognized as a command” | An archive name was typed as an executable. | Extract it. Run its app EXE or the source script; do not type the ZIP's name as a command. |
| EXE copied alone will not open | Its resources/libraries were left behind. | Extract/keep the whole app folder. Create a shortcut to its EXE instead of moving the EXE. |
| Python/backend/module missing | Setup/dependency installation did not finish, or the wrong build is being launched. | Read the first failed setup line, finish setup and launch from the intended folder. For source Windows control, install `.[desktop-control]`. |
| Missing/short `BUJJI_TOKEN` | Configuration was not initialized or the owner token was erased. | Run the setup initializer for a missing source `.env`. Keep its generated token; do not put a provider key there. If an existing token was deleted, restore your private backup or follow the recovery note below. |
| Old key/model still appears to be used | Wrong `.env` or the old tray/backend process is still alive. | Check the configuration-location table, save, Quit Bujji from tray and restart that version. |
| Provider “not configured” for Study/etc. | A saved task route points to a provider without both its key and model. | Configure it or set that category to your configured provider in **AI task routing → Save AI routes**. |
| **401 / 403 from an AI provider** | Rejected key, project permission, region or model access. | Check the provider account/key locally. Do not post the key. A 403 is not always solved by generating another key. |
| **400 / 404 from an AI provider** | Often an invalid/retired model or unsupported request/capability. | Copy an exact currently available model ID. A chat model and a TTS model are not interchangeable. Restart after editing laptop settings. |
| **429 / quota / Retry-After** | Provider rate limit or quota was reached. | Wait according to the provider's limits or explicitly choose another separately configured route. There is no guaranteed five-minute or daily reset for every case. |
| **503 / temporarily unavailable** | Upstream service/model unavailable or overloaded. | Retry a short message later, test the model in its provider console and check access/model status. This message alone does not prove all app settings are correct or that the key is wrong. |
| Chat works, microphone fails | Speech-input provider/model/permission problem. | Check microphone permission, STT provider/key and audio-input capability. Reply voice is separate. |
| Text works, Read aloud fails | Speech-output model/key/access/quota or audio-output problem. | Check TTS settings and model access, then sound/output volume. Keep using text while the provider is unavailable. |
| No reminder sound | App sound/OS notifications/volume/quiet/battery settings. | Use the dedicated test controls, disable Quiet Bujji reminders for the test, check OS settings and keep the app/service running. |
| File tools missing / no known locations | Browser-only launch or unavailable native desktop context. | Start `desktop-start.ps1`/the Windows EXE. In Conversation enable **Tools → File access**. |
| Search cannot find a file | Wrong name/location, bounded search, permissions or excluded type/path. | Start with a small ordinary file in Downloads, use a distinctive filename and narrow the folder. No match is not proof of absence. |
| Invalid file-tool response | The model did not produce the required structured action. | Try one smaller clear task, verify the source is found, and keep it on a configured general chat provider. Do not assume a failed proposal changed files. |
| Computer worker error / ambiguous target | Native dependency, Windows session, app accessibility or target issue. | Install the control extra for source mode, unlock Windows, test Notepad, refresh apps and use the widget's Diagnostics. Protected/elevated apps may remain unavailable. |
| Tailscale command missing | Installation/PATH issue. | Reopen PowerShell, or use the full executable path shown in the Tailscale section. |
| Phone cannot reach laptop | App not running, laptop asleep, Tailscale disconnected, wrong tailnet/address/Serve target or HTTPS setup incomplete. | Check each layer in order below. Do not open public router ports as a workaround. |
| Phone code expired/locked | One-use code timed out or reached its attempt limit. | Generate a fresh code in laptop Devices and pair again. |
| Phone **401** | Device token invalid/revoked or connection no longer trusted. | Pair again from a newly generated code if you intend to reconnect it. |
| Phone **403** for files/control | The paired phone lacks that capability. | Enable its separate **Phone control** / **Browse/download files** grant on the laptop. |
| File candidate found, but not saved | Transfer failed, file too large, unavailable source, phone storage or permission issue. | Check the save receipt, 25 MB bound and phone Downloads/Bujji or Save-as picker. Retry only after checking the existing file. |
| Java class-file version 69 / Gradle semantic-analysis error | Java 25 was used with an incompatible build setup. | Build this project with **JDK 17**. Align `JAVA_HOME` and the editor's Gradle Java setting. |
| Android update not installed / signature mismatch | Different signing identity/package/version. | Use the matching update/key. Back up before considering any uninstall. |
| npm reports vulnerabilities | A dependency advisory; not automatically an installation failure. | Review/update through maintained changes. Do not blindly run `npm audit fix --force`, which can break the locked app. |

### Network troubleshooting order

1. Does typed chat work on the laptop itself?
2. Is native Bujji still running on the expected local port?
3. Are both devices connected to the same tailnet in Tailscale?
4. Does `tailscale serve status` point to the running Bujji port?
5. Is the phone using the exact HTTPS `.ts.net` address, without `:8765` or an `/api` suffix?
6. Did the phone pair with a fresh code?
7. Is its needed control/files grant enabled?

If the phone's browser reaches a Bujji page or an authentication response at that HTTPS address, that can confirm network reachability; it does not replace pairing in the Android app. Do not paste the laptop owner token into the phone's pairing-code form.

### Recovering an accidentally erased owner token

If you have no private backup of the old value, quit Bujji, generate a fresh token locally, and put it on the existing `BUJJI_TOKEN=` line in the correct `.env`. For a source installation:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

This prints a **new secret** in your own terminal. Do not screenshot/share it. Save/restart, and reconnect any browser owner session using the new token. This is not an AI key and does not restore a provider's quota. A packaged user without Python should restore a private configuration backup or get help with local token regeneration rather than downloading a stranger's token.

### Asking for help

Open an [issue](https://github.com/pranav9520/bujji/issues) with OS/app version, how you installed, the feature, harmless reproduction steps and a **redacted** error. The model ID is useful; the actual API key is not. Never attach `.env`, databases, signing keys, pairing tokens, backups or private documents.

<a id="builds"></a>
## 23. Optional: build your own APK or Windows ZIP

Skip this if you already have the application build you need. Compiling is different from configuring an installed app.

### Android APK on Windows

1. Complete/download the source setup above.
2. Install [Temurin JDK 17](https://adoptium.net/temurin/releases/?version=17). Choose a Windows x64 **JDK**, not Java 25 or just a JRE.
3. Install [Android Studio](https://developer.android.com/studio) and open its **SDK Manager**. An emulator is not required for installing on your real phone.
4. In **SDK Platforms**, install **Android API 35**.
5. In **SDK Tools**, install **Android SDK Build-Tools 35.0.0**, **Android SDK Command-line Tools**, and Platform-Tools. Use **Show Package Details** if necessary to select the exact build-tools version.
6. Set `JAVA_HOME` to your JDK 17 installation folder and `ANDROID_HOME` to the SDK path shown by SDK Manager. They are folder paths, not paths to `java.exe` or Android Studio itself.
7. Reopen PowerShell/editor after changing permanent environment variables.

You can set these for one PowerShell session instead. Replace the JDK example with the **real folder on your PC**:

```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\your-actual-jdk-17-folder"
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
& "$env:JAVA_HOME\bin\java.exe" -version
```

If your SDK is stored elsewhere, use that actual path too. The version output must show Java **17**. Then, from the repository root:

```powershell
.\scripts\android-build.ps1
```

The Gradle wrapper downloads its required Gradle version; do not install a random global Gradle version to replace it. The script builds and runs Android unit/lint checks. Find the test APK at:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

Transfer that APK to your phone and install it. Privately preserve `android/.local/debug.keystore` for compatible future local debug updates. Do not commit it. If VS Code imports the Android project with the wrong Java, set its Gradle Java home to the same JDK 17 or use the documented terminal build; Java language-server settings alone may not change Gradle's JVM.

### Windows application ZIP

On Windows, after source setup:

```powershell
.\scripts\desktop-build.ps1
```

This packages the Python backend and desktop UI. Output is under `desktop/release`. It is a full application ZIP; extract all its contents to test it.

The optional `-IncludeLocalVoice` build switch adds runtime dependencies, **not automatic model downloads or model-licence permission**. See [Voice options](docs/VOICE.md).

### Official signed Android releases

Maintainers need a stable private signing keystore and the four release secrets described in [MAINTAINERS.md](docs/MAINTAINERS.md). The release workflow also checks versions/tags and generates checksums. Debug artifacts are not a replacement for a stable signing plan. Never store release secrets in README, source files or issue comments.

<a id="development"></a>
## 24. For developers: structure, tests and non-Windows use

| Folder | Purpose |
| --- | --- |
| `backend/bujji` | Python/FastAPI service, storage, providers, tools, pairing and sync |
| `frontend` | Desktop web interface |
| `desktop` | Electron shell, narrow native bridge and packaging |
| `android` | Java Android app and its bundled interface |
| `scripts` | Setup, build and publication checks |
| `tests` | Backend and browser checks |
| `.github/workflows` | CI and release automation |
| `docs` | Architecture, platform guides, privacy/security and maintenance |

The laptop app owns its backend process. Local storage uses SQLite. Models interpret requests; typed tool validation and native code decide which supported operations can execute. Android has its own local backend/data, not an embedded copy of the laptop Python server. Pairing provides scoped cross-device operations.

For development, run the checks relevant to your change. For example, after installing the Python/test dependencies:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:voice
npm.cmd --prefix desktop test
.\.venv\Scripts\python.exe scripts\check_public_tree.py
```

Frontend/desktop test commands need their corresponding npm dependencies installed. The public-tree checker scans **tracked files**; it is a heuristic, not proof that every possible secret is absent. Browser flows, Android builds/lint and platform acceptance are explained in [TESTING.md](docs/TESTING.md). Mock/JVM/browser tests do not prove native Windows controls, actual provider access or OEM notification delivery.

On Linux/macOS, the backend/web interface can run for development, but the documented packaged desktop/native computer controls target Windows:

```bash
./scripts/setup.sh
# Edit .env privately before starting.
.venv/bin/python -m uvicorn bujji.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Open `http://127.0.0.1:8000` and use your generated owner token in browser Settings. Keep it bound to loopback. This browser-only path does not automatically provide the native Windows bridge. Android can also be built with JDK 17/SDK on a supported development machine using `cd android && ./gradlew :app:assembleDebug`.

<a id="links"></a>
## 25. Official links and deeper guides

### Bujji

- [Repository](https://github.com/pranav9520/bujji) · [Releases](https://github.com/pranav9520/bujji/releases) · [CI/build artifacts](https://github.com/pranav9520/bujji/actions/workflows/ci.yml) · [Report an issue](https://github.com/pranav9520/bujji/issues)
- [Windows guide](docs/WINDOWS.md) · [Android guide](docs/ANDROID.md) · [Pairing guide](docs/PAIRING.md)
- [AI configuration](docs/CONFIGURATION.md) · [Voice options](docs/VOICE.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Architecture](docs/ARCHITECTURE.md) · [Testing](docs/TESTING.md) · [Contributing](CONTRIBUTING.md) · [Release maintenance](docs/MAINTAINERS.md)
- [Privacy](PRIVACY.md) · [Security](SECURITY.md) · [MIT licence](LICENSE) · [Third-party notices](NOTICE.md)
- [Configuration template](.env.example) · [Supported desktop speech models](backend/bujji/tts.py)

### Installation tools

- [Python for Windows](https://www.python.org/downloads/windows/)
- [Node.js](https://nodejs.org/en/download)
- [Git for Windows](https://git-scm.com/install/windows)
- [VS Code](https://code.visualstudio.com/download)
- [JDK 17](https://adoptium.net/temurin/releases/?version=17)
- [Android Studio / SDK](https://developer.android.com/studio)

### Gemini

- [Get/manage an API key](https://aistudio.google.com/apikey)
- [Official key instructions](https://ai.google.dev/gemini-api/docs/api-key)
- [Current models](https://ai.google.dev/gemini-api/docs/models)
- [Speech generation](https://ai.google.dev/gemini-api/docs/speech-generation)
- [Audio input](https://ai.google.dev/gemini-api/docs/audio)
- [Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Troubleshooting the Gemini API](https://ai.google.dev/gemini-api/docs/troubleshooting)

### Tailscale

- [Windows download](https://tailscale.com/download/windows) · [Android download](https://tailscale.com/download/android)
- [Device list](https://login.tailscale.com/admin/machines) · [DNS settings](https://login.tailscale.com/admin/dns)
- [Serve command reference](https://tailscale.com/kb/1242/tailscale-serve)
- [HTTPS setup](https://tailscale.com/kb/1153/enabling-https)
- [MagicDNS](https://tailscale.com/kb/1081/magicdns)
- [Connection troubleshooting](https://tailscale.com/kb/1023/troubleshooting)
- [Plans/pricing](https://tailscale.com/pricing)

## A sensible first test session

Try these in order rather than enabling everything at once:

1. Laptop typed `Hi` works.
2. A harmless saved memory survives a restart.
3. A near-future reminder produces a notification/sound.
4. Microphone transcription works, then Read aloud works.
5. A dummy file can be found and copied into a newly approved Desktop folder.
6. Typed Notepad control works in the laptop widget.
7. Android standalone typed chat/reminders work.
8. Tailscale networking and Bujji pairing succeed.
9. Manual memory sync works.
10. A permitted typed remote command and a small dummy download work on the phone.

Then expand to your normal tasks. Bujji is community software: provider access, operating-system behavior and models change. Keep private backups, review real action results and report reproducible problems without sharing secrets.
