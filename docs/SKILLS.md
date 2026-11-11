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


## November 2026 integration research

- [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
  (MIT): reference for visual hierarchy, spacing, design tokens and accessible
  focus states. Adapt patterns to existing Qt widgets, not React or Tailwind
  code. Existing dark theme and QSplitter workspace stay lightweight.
- [kajisho5/ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill)
  (MIT): probe → edit → verify workflow with local FFmpeg/FFprobe. This
  repository calls FFmpeg directly, not an agent server.
- [kajisho5/video-editing-skill](https://github.com/kajisho5/video-editing-skill)
  (MIT): typed operations and verifiable export. Use its operation contract
  as a roadmap for later cuts, concat and speed changes, not as already
  delivered functionality.
- [Johnserf-Seed/f2](https://github.com/Johnserf-Seed/f2)
  (Apache-2.0): isolated Windows worker for permitted Douyin downloads.
  No unauthorized access or browser-session harvesting.
- [zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
  (GPLv3/noncommercial or separate commercial license): **not bundled**.
  Commercial affiliate intent makes wholesale adoption a licensing risk.
  Adopt only general interface ideas, not its source code.
- [JoeanAmier/TikTokDownloader](https://github.com/JoeanAmier/TikTokDownloader)
  (GPL-3.0): useful comparative QA for batch downloads but **not vendored**
  into this MIT project.

Skills are development instructions, not packages to silently embed into
the user's portable EXE. Record upstream licenses and verify each dependency
before shipping.

## November 2026 4.0 skill selection for desktop production

The chosen skills are **developer guidance only**, NOT bundled dependencies in
the user's Windows EXE. This distinction matters because many interface
skills target browsers instead of native Qt.

| Skill/repository | Why it helps | Explicit adoption |
| --- | --- | --- |
| [UI/UX Pro Max v2.15](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) (MIT) | Readable color/text contrast, focus, error feedback, information hierarchy | Apply to current native PySide6/QSS palette, page search and project controls; no React/npm bundle |
| [Impeccable](https://github.com/pbakaus/impeccable) | `audit`, `harden`, `polish`, `adapt`, `onboard` review checklists | Use for empty states, missing files, cancellation confirmation, keyboard navigation; web live tooling not applicable to Qt |
| [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) (MIT) | Reproducible probe → edit → verify, deadlines and output quality contracts | Direct FFmpeg/FFprobe plus tests; no MCP service in app |
| [video-editing-skill](https://github.com/kajisho5/video-editing-skill) (MIT) | Typed, verifiable edit operations, validated source-to-timeline mapping | `EditPreset`, per-source render jobs and 4.0 local project serialization; **not** a claim of multitrack timeline |
| [NSIS](https://nsis.sourceforge.io/) | One-file Windows setup with explicit per-file uninstaller | Compile in CI, install/test/uninstall, preserve user-added files and local app data |
| [F2](https://github.com/Johnserf-Seed/f2) and [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Public Douyin links, isolated worker and conditional extractor fallback | Keep existing worker. No browser cookie harvesting, CAPTCHA bypass, or unreviewed forks |

**Why not add Fluent-Widgets or a new web UI?** PyQt-Fluent-Widgets
licensing and additional weight need separate approval for a commercial
affiliate app. Replacing the native editor with a browser/web runtime would
increase EXE size and risk breaking Qt Multimedia, OCR and offline processing.

Engineering acceptance is tracked in
[PRODUCTION_READINESS_4_0.md](PRODUCTION_READINESS_4_0.md).
