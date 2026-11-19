# Android setup

Build prerequisites: JDK **17**, Android SDK Platform 35 and Build Tools 35.0.0. Set JAVA_HOME to JDK 17 and ANDROID_HOME to your SDK. On Windows run `scripts/android-build.ps1`. On Linux/macOS run `cd android && ./gradlew :app:assembleDebug :app:testDebugUnitTest :app:lintDebug`.

The debug APK is `android/app/build/outputs/apk/debug/app-debug.apk`. Transfer it to your phone, allow installation from that source temporarily, and open it. The community package is `org.bujji.companion`. A private or differently signed edition is a separate installation; its data is not silently imported.

Choose your name, then configure an AI provider, key and exact enabled model ID in Settings. Select **Use this provider for all chat tasks** for a simple setup with a general-purpose provider. Perplexity is intended for research and cannot replace every general route. Speech input has its own provider configuration; spoken replies use the installed Android voice, whose pronunciation varies by device.

Grant microphone permission for speech and notification permission for reminders. Clock requests hand off to the installed Clock app; availability and confirmation depend on that app. Usage-access permission is optional for screen-time estimates. OEM battery management can delay background notifications; test reminders with the phone locked before relying on them. No always-on wake word or unrestricted phone screen control is provided.

Keep `android/.local/debug.keystore` privately for compatible future debug installs. Never commit it. Official release builds require a stable separate release key; see MAINTAINERS.md. A signing mismatch requires the original key or a separate installation; uninstalling erases local app data. Back up/export important data first.

For laptop access follow PAIRING.md. The laptop must remain awake and its backend reachable. This app is not a cloud relay or live remote-desktop video stream.
