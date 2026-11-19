# Pair phone and laptop

1. Install and run Bujji on both devices. Give each device its own AI configuration when using standalone chat.
2. Connect both devices to the same private Tailscale network. Keep the backend on loopback; use private **Tailscale Serve**, not Funnel, to expose the laptop service on port 8765 to your tailnet. Check your installed Tailscale version's Serve instructions and use its HTTPS address on the phone.
3. Open Devices on the laptop and create a pairing code. Enter the laptop address and code in the phone's device settings. Codes expire; generate a fresh one if needed. Do not send the laptop owner token to the phone.
4. Review each device's grants on the laptop. Memory/reminder sync, computer control and laptop-file access are separate permissions. Enable only the capabilities you intend to use.
5. Test a harmless command such as opening Notepad, sync a dummy reminder, and find/copy a small test file through phone chat.

Sync is explicit/manual, not a promise of instant background reconciliation. Keep both devices connected while testing. Revoke a phone from Devices when it is lost or no longer trusted. A saved pairing token is sensitive.

File search works inside permitted laptop locations, with exclusions for hidden/system/credential files and links. Copies to the phone are limited to 25 MB per file. Use chat to identify a file, inspect matching results and choose the intended one. This version does not provide phone-to-laptop upload or unrestricted Explorer mirroring.

Remote computer commands operate through Windows' supported controls. They require an unlocked interactive laptop. Stop cancels remaining work, not actions already completed. Native restrictions and operating-system prompts still apply. Never expose the backend port directly to the public internet.
