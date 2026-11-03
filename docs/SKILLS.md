# Skills & repository adoption audit for Douyinhehe Pro 2.0

This page records what was reviewed and what the application actually executes. A GitHub **agent skill is usually guidance for coding agents, not a drop-in DLL in the Windows executable.** Never install entire agent runtimes into the desktop app merely to check a box.

| Upstream | License / role | Integration scope in v2 |
| --- | --- | --- |
| [morluto/rea](https://github.com/morluto/rea) (`reverse-engineer-anything`) | MIT, analyses packaged binaries/PyInstaller archives | **Optional developer QA only**: can inspect the *self-built* Windows EXE/archive after CI, not bundled or used to access other apps or bypass protections. Skill explicitly says to skip REA when full source is available. |
| [kajisho5/ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) | MIT, deterministic media editing & verification | Adopt **probe → edit → inspect** approach; FFmpeg invoked directly in our code. No embedded MCP runtime. |
| [kajisho5/video-editing-skill](https://github.com/kajisho5/video-editing-skill) | MIT, typed editing graph | Use a typed `EditPreset` and stable batch manifest, with validations and test coverage. No code vendored. |
| [kajisho5/qc-skill](https://github.com/kajisho5/qc-skill) | MIT, artifact QA | Implement `delivery_preflight` over ffprobe results. This is *not* a guarantee of platform approval. |
| [kajisho5/subtitle-skill](https://github.com/kajisho5/subtitle-skill) | MIT, SRT and hard captions | Existing SRT validation and FFmpeg subtitles; no agent dependency bundled. |
| [google-gemini/gemini-skills](https://github.com/google-gemini/gemini-skills) | Apache-2.0, SDK usage | Gemini developer guidance; `google-genai` is optional at runtime. No automatic paid model fallback. |
| [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense; download adapter | Existing authorized-link downloader; failure to access Douyin is reported, not bypassed. |
| [gitroomhq/postiz-app](https://github.com/gitroomhq/postiz-app) | AGPL-3.0, scheduler service | Separate hosted service called over documented API, never bundled in EXE. |

## REA package verification (optional, developer-owned Windows build)

1. Download the official GitHub Actions artifact from **this** repository. Check its SHA-256 digest and unpack in a safe directory.
2. Verify the EXE's `--self-test`, inspect its `bin/ffmpeg.exe` and `bin/ffprobe.exe` versions, then inspect with your *own* REA environment if already configured. For a PyInstaller executable, REA's `open_binary` artifact route can inspect the PyInstaller archive inventory. Do not claim binary analysis unless it was actually run.
3. Verify files and third-party licensing before redistribution; a successful build is not a complete license compliance review.

**No REA runtime was embedded or installed by this repository.** `rea-agents` requires a compatible Node.js runtime and potentially optional analysis tools; do not force these onto ordinary app users.
