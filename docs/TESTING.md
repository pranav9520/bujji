# Testing and acceptance

Run backend tests with `python -m pytest tests -q` after installing the locked dependencies and test extra. Run frontend `npm ci`, `npm run build`, `npm run test:voice` and desktop `npm ci`, `npm test` in their respective directories.

For browser flows install Python Playwright and Chromium, build the frontend, then run `tests/browser_ui_refresh.py`, `tests/browser_device_pairing.py` and `android/tests/ui_smoke.py`. PLAYWRIGHT_CHROMIUM_EXECUTABLE can select an existing browser. Tests use temporary local data and mocked external providers; they do not spend real API credits intentionally.

With JDK 17 and the Android SDK, run `android/gradlew -p android :app:assembleDebug :app:testDebugUnitTest :app:lintDebug`. Run `python scripts/check_public_tree.py` after staging intended source files: it scans tracked files, not all ignored private files. It is a heuristic, not proof that no secret can exist. Review the staged diff and history separately.

Before a release, manually test first-run name/key setup, restart persistence, three-second silence handling, Short talk, saved chat, reminders while locked, Focus pause/resume, device pairing/revocation, manual sync, harmless Windows control and a small dummy PDF copied through phone chat. Verify Stop and failed/disconnected operations. Test upgrades with the same signing key and back up data first.

Browser mocks and Android JVM tests do not prove real microphone, OEM notification delivery, provider availability, Windows UIAutomation or phone downloads. Linux build verification does not produce a tested Windows executable. Report these limitations with a release instead of claiming every possible bug is fixed.

## Initial community preparation checks

The prepared source passed 212 Python tests, 74 Android JVM tests, 19 voice tests and 13 Electron policy tests. The frontend production build, Android debug build/lint and all three browser flows passed locally. The tracked-file credential/artifact audit and a separate identity/path review passed. These checks used Linux, JDK 17, Python 3.12 and mocked provider/browser flows. Windows packaging and real-phone acceptance remain separate release checks; no signed official binaries are claimed here.
