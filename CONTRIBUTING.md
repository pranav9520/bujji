# Contributing

Use a fork and a short feature branch. Read the setup and architecture guides first. Keep changes scoped, include a concrete before/after example and run the relevant checks in README. Add a regression test for a meaningful bug; do not add tests that only restate the implementation.

Never commit `.env`, account keys, signing keys, databases, private screenshots, model weights, build output or personal paths. Use synthetic fixtures with generic names. Run `python scripts/check_public_tree.py` before opening a pull request. The audit is a guard, not proof that every possible secret has been detected.

Preserve device scopes and native action validation. Model output is data, not authorization. Describe any changes to file access, data export, pairing or action approval clearly in the pull request.

For UI changes, include screenshots made with synthetic data and say which viewport/device was tested. For Windows/Android changes, distinguish actual-device checks from mocked or Linux browser tests. Explain any remaining provider or platform limitations.

Bug reports should include app version, OS/Android version, reproduction steps and redacted error text. Do not attach API keys, owner/pairing tokens, sensitive documents or whole databases. Security issues belong in the private reporting process in SECURITY.md.

Contributions are under the repository's MIT licence; retain third-party licences and attributions. Be respectful, specific and patient when discussing changes.
