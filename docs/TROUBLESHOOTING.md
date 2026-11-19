# Troubleshooting

- **Unsupported class file major version 69:** Gradle is being run with Java 25. Select JDK 17 in JAVA_HOME and VS Code/Android Studio Gradle settings, stop old Gradle daemons, then rebuild. Verify `java -version` and `android/gradlew --version`.
- **Copied EXE will not open:** restore/extract the entire ZIP and create a shortcut to its executable. The executable needs its resources and libraries beside it.
- **Old interface:** quit the tray process, close old development servers and launch the intended extracted build. Different workspaces/installations may retain different data.
- **Missing AI response:** configure both a key and an enabled exact model ID for the selected route. Model 400/404 errors often indicate an unsupported model or capability. Do not paste keys into issues.
- **Voice 429/503:** wait for provider recovery/quota reset, use text or choose a separately configured supported engine. Cached speech is not evidence of new-generation availability. Android voice quality depends on the installed speech engine.
- **Phone cannot connect:** confirm the laptop is awake, Bujji is running, private Tailscale connectivity works and the saved address is correct. Renew expired pairing codes and review separate device grants. Do not forward a public port as a workaround.
- **File not found/copy fails:** ask chat to search a known user folder with a distinctive filename. Search and preview are bounded; excluded/system/hidden/linked files are unavailable. Try a small ordinary PDF under 25 MB and check the phone's download permission/storage. Transfer is laptop-to-phone in this version.
- **Control fails:** unlock Windows, refresh open apps and test Notepad. UAC, secure desktop, elevated apps and inaccessible controls may not work. Stop ongoing commands before retrying. Linux browser tests cannot verify the native Windows worker.
- **APK update rejected:** check package ID and signing key. Keep the same key for future updates. Uninstall only after backing up data.
- **Delayed reminders:** enable notifications and check Android battery restrictions. Test while locked. Clock handoff and scheduled delivery depend on the OS and installed apps.

When reporting a bug, include OS/app versions, harmless reproduction steps and redacted errors. Exclude `.env`, databases, tokens, personal documents and screenshots containing private information.
