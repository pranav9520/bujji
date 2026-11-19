# Windows setup

Use Windows 10/11 x64. For source builds install Git, Python 3.11/3.12 and Node.js 22.12 or newer, clone this repository, then run `scripts/setup.ps1` followed by `scripts/desktop-start.ps1` in PowerShell. If local script execution is blocked, use a process-scoped execution-policy override only after reviewing the scripts.

Setup creates `.venv`, installs locked dependencies, builds the interface and creates a private `.env` with a random owner token. Edit that file for your provider key, exact model ID and IANA timezone (for example `Asia/Kolkata`). Restart Bujji after changing environment configuration. Never post the file in an issue.

Build a ZIP with `scripts/desktop-build.ps1`. Extract the entire ZIP to a permanent folder and launch Bujji.exe. To create a shortcut, right-click the executable in that extracted folder and create a shortcut; do not move just the executable. Closing the window hides it in the tray; choose **Quit Bujji** to stop it.

Packaged community builds create their configuration under `%APPDATA%\BujjiCommunity\workspace`; use Settings → Open configuration folder to find it. Development builds use the source directory. The separate community workspace does not automatically migrate a private edition. Set your own name on first launch.

Before upgrading, quit Bujji and back up the workspace privately, including configuration and data. Extract the next build into a new application folder. Keep the workspace in place. Do not share backups: they can contain keys and conversation data. Windows SmartScreen may warn about unsigned builds; verify the source and release checksum before running them.

Computer control requires an interactive, unlocked Windows session. It cannot bypass UAC or control the secure desktop. Use Stop to halt remaining steps. Runtime control dependencies are included by the build script; tests on other operating systems do not establish Windows compatibility.
