# AI and local configuration

Windows source setup reads the local `.env`; packaged builds provide a configuration-folder button in Settings. Android stores its own settings. Keys are not synchronized between devices. `.env.example` documents supported variables without real credentials. Restart the Windows backend after environment edits.

Use exact model IDs enabled in your provider account. Set the corresponding API key and model together. A ChatGPT, Claude or other consumer subscription does not automatically include API credits.

| Provider | Role | Environment variables |
| --- | --- | --- |
| Gemini | General chat and optional audio/document capabilities | GEMINI_API_KEY, GEMINI_MODEL |
| OpenAI | General/study/coding | OPENAI_API_KEY, OPENAI_MODEL |
| Anthropic | Writing/analysis/coding | ANTHROPIC_API_KEY, ANTHROPIC_MODEL |
| Perplexity | Research | PERPLEXITY_API_KEY, PERPLEXITY_MODEL |
| Groq | General chat; separate optional transcription | GROQ_API_KEY, GROQ_MODEL |
| Ollama | Optional local desktop chat | OLLAMA_ENABLED, OLLAMA_MODEL |

Task routing supports daily, study, research, coding, writing and analysis. Fresh desktop configuration routes them to Gemini; Settings can change these. Android's one-provider checkbox applies a configured general provider to all chat routes. Specialist routes need their own configured keys. NotebookLM is not integrated. No automatic account rotation or unlimited cloud quota is provided.

BUJJI_STT_PROVIDER chooses Gemini or Groq speech input independently of chat routing. GEMINI_STT_MODEL/GROQ_STT_MODEL must support transcription. Gemini document OCR and Gemini TTS require models with those specific capabilities; a chat model is not interchangeable. See VOICE.md. A 429 is a provider quota/rate limit; a 503 is temporary service unavailability. Neither can be eliminated by changing UI settings.

Set BUJJI_TIMEZONE to your IANA timezone; the template defaults to UTC. BUJJI_TOKEN is the private owner credential generated at setup. Keep it secret. BUJJI_DATA_DIR and BUJJI_FILE_ROOT control local storage; use absolute paths when managing a custom service. Do not configure a public bind address without a separately reviewed deployment design.

The profile name is a local UI preference. Optional Telegram and local-model settings are disabled unless configured. Telegram is disabled by the desktop launcher. Provider requests may transmit chat, selected document excerpts or permitted screen text; read PRIVACY.md before enabling them.
