# Maintainer and release guide

Keep a prepared repository private until its source, tracked-file audit, licences, tests and intended public contents have been reviewed. Publishing visibility is a separate deliberate GitHub setting. Never import private project history or force-push over an existing personal repository.

The community identity is `org.bujji.companion` on Android and `org.bujji.desktop` / BujjiCommunity on Windows. Keep signing keys and private data outside git. Initial source distribution can be reviewed without publishing binaries.

CI runs on pushes and pull requests. Actions are pinned to commit hashes. Review Dependabot updates and untrusted contributions; never add secrets to fork-PR jobs. Configure repository permissions for workflows and enable GitHub private vulnerability reporting where available.

For signed Android releases create and securely back up one stable release keystore, then configure these GitHub Actions secrets:

- ANDROID_KEYSTORE_BASE64: base64 of that private keystore.
- ANDROID_STORE_PASSWORD: keystore password.
- ANDROID_KEY_ALIAS: signing alias.
- ANDROID_KEY_PASSWORD: key password.

The release workflow translates these to BUJJI_ANDROID_* Gradle variables and removes its transient key. Do not put values in an issue, commit, log or build artifact. Losing the key prevents compatible signed updates. Debug keys are local-only and must not be used as the official release identity.

Before tagging, update versions together in pyproject.toml, frontend package/lock, desktop/package.json, Android Gradle versionName/versionCode and runtime status labels. Run `RELEASE_TAG=vX.Y.Z python scripts/check_release.py` (PowerShell uses `$env:RELEASE_TAG`). Run CI and the real-device acceptance checks in TESTING.md. Create the matching tag only when ready. The Release builds workflow packages a Windows ZIP, signed Android APK and SHA256SUMS; missing signing secrets intentionally block publication. No signing secrets or official binaries are supplied by this source copy.

Verify artifacts on a clean Windows machine and Android device before recommending installation. Windows binaries are not code-signed by this workflow. Retain dependency/model notices. Optional models are excluded by default. Check generated THIRD_PARTY_LICENSES.json in the Windows package. GitHub-generated release notes still need human review.
