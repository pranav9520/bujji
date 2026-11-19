# Privacy and data flow

The project adds no product-analytics service. Bujji stores local chats, explicit memories, reminders, Focus records, provider configuration and pairing metadata on your device. The source contains no default person's name, accounts or documents.

Normal AI chat sends the relevant conversation and configured memory context to the selected provider. File tools can send paths/excerpts to that provider. Explicit OCR sends the selected image/PDF to the configured Gemini endpoint. Provider retention, charges and quotas are outside Bujji's control.

Microphone clips are short, stop after quiet/max-duration rules, and go to the configured transcription provider. Temporary local audio files are deleted after processing. Short talk is not saved to local chat/memory, but a remote provider can still process/retain its request under its own terms. Desktop cloud speech sends reply text to Gemini; Android reply speech uses the installed device voice. Experimental local speech is opt-in and separate.

Pairing exchanges saved memories/reminders over private HTTPS. Remote computer/file access requires separate laptop-side per-phone grants. Window titles may reach the laptop planner; accessible screen text is sent when explicitly enabled. There is no live screen-video recording. Browser-only file discovery and downloads do not require a model; conversational searches/summaries can send relevant paths/excerpts to the laptop's chosen provider.

Downloaded files are copies in Android Downloads/Bujji (25 MB/file limit). The original stays on the laptop. Backups contain private records but exclude API keys; they do not bundle laptop documents or phone Downloads. Keep them out of Git and share them only intentionally. Memory/reminder sync does not copy provider keys or merge Focus timers/statistics.

Packaged Windows data: `%APPDATA%\BujjiCommunity\workspace`. Source builds use the configured local data folder. Android data is app-private except explicitly saved Downloads/backups. Closing the Windows window normally leaves the tray/backend running for reminders; use tray Quit to stop it. Android timing/background behavior depends on OS permissions and battery policy.

To remove a paired phone, revoke it in laptop Devices and disconnect locally. Export important data before uninstalling or resetting storage. An installed copy does not update itself merely because this GitHub repository changes.
