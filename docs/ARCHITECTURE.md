# Architecture

- UI: PySide6 desktop, 7 tabs. Workers execute blocking downloads, renders, transcription and remote API calls outside the UI thread.
- Storage: SQLite local database (licensed sources, affiliate products, publication attempts, translation cache).
- Permission boundary: source permission declared by user before downloader; editing requires an explicit commercial/derivative confirmation. Strong legal rights checks require reviewing the actual documents outside the app.
- Downloader: `yt-dlp` adapter restricted to HTTPS Douyin host URLs. No browser-cookie theft, CAPTCHA bypass, automated evasion or unapproved profile crawling.
- Editor: FFmpeg/FFprobe command arguments are passed as lists, never via shell; all outputs are re-probed. Transparent overlay created with Pillow, visible source credit mandatory. Optional SRT and narration file.
- Translation: Offline Whisper STT + Gemini text translation via the official google-genai SDK. No API calls without explicit Free Tier checkbox; no paid fallback. Cache keyed by input text and model.
- Security: `keyring` stores secrets in the OS credentials vault, not source or SQLite; no secrets in log messages. Postiz base URL must be HTTPS. Network calls use timeouts and no HTTP redirects.
- Publishing: Postiz's hosted/self-hosted server is a separate component. Public API uploads media then creates scheduled posts for explicitly selected integrations and provider settings. Actual platform success must be verified on Postiz/provider dashboards.
- Monetization: manual product/affiliate data, no fake views or conversion assumptions. Organize channels by niche; content strategy and exact cadences are user-defined, not hard-coded.

## Release engineering

GitHub Actions Windows builds `.exe` with PyInstaller in onedir layout and bundles `ffmpeg.exe`/`ffprobe.exe` for portable use. Windows end-to-end tests with real API accounts remain manual. Check redistributable media codec licensing before commercial deployment.
