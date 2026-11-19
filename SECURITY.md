# Security

Do not post secrets or exploit details in a public issue. Use this repository's **Security → Report a vulnerability** feature if enabled. If it is unavailable, open a minimal issue asking maintainers to enable private vulnerability reporting without including sensitive details.

Bujji is not a hardened multi-user server. The owner token controls the local backend and belongs only on the owner's device. Pairing tokens are separate, revocable and limited to sync plus explicitly granted remote capabilities. Keep the backend on loopback; pair through private Tailscale Serve with certificate verification, not Funnel or public port forwarding.

Keep API keys, `.env`, Android signing keys and databases out of Git and screenshots. Android provider keys use Keystore encryption. Windows source/workspace configuration is a local `.env` protected by OS account/file access, not a hardware vault. Use a trusted OS account and backups you control.

Models cannot authorize their own writes. Desktop file changes use validated reviewed plans. Remote file chat is read-only on the laptop; explicit phone transfers write a copy into phone Downloads. Native controls reject unsupported/credential/payment/security actions and re-check targets. OS prompts remain. These are application safeguards, not a guarantee against every failure.

Dependencies, OS accessibility, file permissions, networking and providers have their own risks/limits. Public releases should use a stable private signing key; never distribute that key. See docs/MAINTAINERS.md for release checks and docs/TROUBLESHOOTING.md for safe diagnostics.
