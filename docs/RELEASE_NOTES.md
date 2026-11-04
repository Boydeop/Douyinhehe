# Douyinhehe Pro v2.1.0 · Engineering Preview

**Windows x64 portable:** download `DouyinhehePro-Windows-x64.zip`, verify the
SHA-256 against `SHA256SUMS.txt`, then extract the **whole** `DouyinhehePro`
folder and open `DouyinhehePro.exe`. Do not move the EXE outside that folder.

Highlights:
- yt-dlp downloader diagnosis in Vietnamese and a user-confirmed Windows-only
  downloader update; validates official GitHub asset SHA-256 + checksum manifest.
- Subtitle readability check (42 characters/line, 20 CPS, 2-line warnings,
  time overlaps) and a 5-second FFmpeg preview.
- Per-niche Chinese/Vietnamese glossary, context and optional second Gemini
  review with cache isolation. No automatic paid fallback.
- Rights expiration and optional SHA-256 for the original permission file;
  each batch job rechecks permissions before rendering.
- Offline Piper adapter (requires your own executable and licensed voice model),
  in addition to the system voice provider.
- Brand CTA color, position and font presets, CSV campaign performance by
  video ID, and import of locally recorded clips.
- Structured, rotating logs with API-key redaction and downloadable report.
- Windows + Ubuntu CI, lint, static typing, FFmpeg integration tests and
  a packaged `--self-test` smoke test.

**Important:** Publishing via Meta, TikTok, YouTube, Instagram and Threads requires
valid account access, OAuth permissions and provider configuration. Cloud
scheduling requires a server. AI-translated subtitles need a user-provided
Gemini key and confirmed free-tier eligibility. Credit and edits do not override
copyright terms or platform originality policies.

**License notice:** source is MIT; redistribution of bundled Qt/FFmpeg and other
components is subject to their separate licenses. See `THIRD_PARTY.md` and
`FFMPEG_BUILDINFO.txt` inside the ZIP. This prerelease is not code-signed.
