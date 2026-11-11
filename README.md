# Douyinhehe Pro · Affiliate Video Studio

Windows desktop studio for **licensed Douyin videos**, Vietnamese subtitle translation and affiliate multi-channel publishing. **Current status: 3.6.0 RC1 design refresh preview (public-link downloader, video editor, offline OCR)**. No claims of guaranteed views, copyright immunity, or unrestricted automatic posting. Interface is Vietnamese.

## Integrated 3.5 release candidate (November 2026)

This branch combines the previously separate downloader PR #6 and playable
editor PR #7. F2 is attempted for direct video and official share links,
as well as channel profiles. yt-dlp is a conditional fallback only. Failed
downloads are not counted as successful, and sanitized diagnostics are
available in the download screen. Exports are staged and published without
overwriting existing files. The desktop editor supports local playback,
seeking, IN/OUT trim, OCR suggestions on selected frames, masks, 5-second
render previews, and real FFmpeg output.

**Acceptance gate:** CI on the integrated branch, Windows portable self-tests,
and a manual Windows acceptance pass with authorized Douyin links and a
representative licensed local MP4. Automated tests cannot guarantee live
Douyin access or commercial distribution rights. See
[the integration audit](docs/INTEGRATION_AUDIT_2026_11.md).

## 3.6 RC1 desktop UX refresh

The Windows studio is redesigned with a consistent dark/light native Qt design
system, higher-contrast controls, compact workspace header, keyboard quick
navigation (`Ctrl+K` then Enter), task icons, persistent theme preference,
one-click local video import and collapsible diagnostics. It keeps nine existing
functional pages and the real FFmpeg video editor, with clear empty-library
states. The downloader adds explicit clipboard paste, clear and open-download-
folder actions with honest **public/no manually supplied cookies** guidance.

This does **not** guarantee Douyin downloads without authentication. Public
videos may be accessible to F2 or yt-dlp on some networks; login-only,
CAPTCHA, HTTP 403/429 and region-restricted resources must not be bypassed.
The downloader never asks the user to export private browser cookies. Live
network behavior must be tested on a permitted Douyin video.

Design references: UI/UX Pro Max, Anthropic Frontend Design and Impeccable.
Their guidance informed native PySide6 components; the project does not embed
GPL-licensed QFluentWidgets or any web-only runtime. See
[UX redesign and acceptance plan](docs/UX_REDESIGN_V3_6.md).

**Status:** 3.6.0rc1 is an engineering preview pending integrated Windows
CI, live allowed-link checks and local interactive Windows verification.
Portable ZIP is still required because FFmpeg, F2, Qt plugins and OCR weights
are packaged alongside the app.

## Implemented

| Module | Available now | Limitations |
| --- | --- | --- |
| Niche research | Chinese keyword collections, manually weighted opportunity score, saved sources | No automated Douyin search API; metrics entered manually |
| Douyin downloader | Multiple links and full profile mode, local archive to avoid duplicates | Entire-channel coverage depends on Douyin/yt-dlp; no access bypass |
| Privacy-first rights confirmation | Confirmation without storing author names/contracts/expiry in new jobs | Old local records can be scrubbed with Settings action; permissions still required |
| Video editor | Play MP4/MOV/MKV, scrub, set trim points, mask text, 9:16/16:9/square color presets, real 5-second render preview and verified MP4 export, single/batch | Media playback codec compatibility depends on Qt Multimedia/Windows; this is not a multi-track CapCut timeline |
| Mandarin transcription | Optional `faster-whisper` offline | Model weights downloaded separately on first use; CPU may be slow |
| Translation | Google Gemini SDK to translate SRT in batches, local cache, manual Free Tier opt-in | API key and actual Free Tier entitlement required; quota errors stop processing |
| Vietnamese TTS | Offline Windows SAPI via pyttsx3 | Vietnamese SAPI voice must already be installed; not auto-bundled |
| Affiliate | Niche/product/campaign/link library; CTR and conversion calculator | No affiliate platform order API or automatic sales sync |
| Publishing | Postiz Public API: list connected channels, upload video, schedule batch | Postiz API key, connected OAuth channels, provider-specific settings, server/service online required |
| Desktop | PySide6 worker queue, SQLite, OS credential storage, nine feature tabs | Live platform authorizations still need user testing |
| V2 batch pipeline | CSV/JSON manifests with per-video rights, recoverable render jobs, deduplication, provenance sidecars | Only local edits auto-retry; remote publishing stays manual-approval |
| V2 delivery QA | Codec/aspect checks and per-platform CTA/source guidance | Guidelines, not platform approval |

## Real video editor in v3.4 RC1

The Studio page now includes local clip import, native Qt Multimedia video playback,
seek/timeline, IN/OUT trim, crop/pad/background blur and color controls, a draggable
mask canvas with optional Chinese OCR, CTA/SRT/narration, a **real rendered 5-second
preview**, and single/batch H.264 MP4 export. FFmpeg and FFprobe validate video
outputs, and source files are not overwritten. Empty CTA/source input no longer
adds unexpected text overlays.

This preview is distributed for testing; GitHub Actions checks that a synthetic
video can be cut, rendered and played through the packaged component startup.
Interactive testing on Windows with real camera footage and audio is still needed.
Read [Studio v3.4 preview workflow](docs/VIDEO_EDITOR_WORKSPACE.md).

## Douyin downloader and UI in v3.2

The desktop now detects Douyin profile links like `https://www.douyin.com/user/<sec_user_id>?vid=...` and routes them to an isolated **F2** channel downloader. Individual video URLs still use yt-dlp. The new Windows portable bundle includes `bin/DouyinF2Worker.exe` built separately from the main application to keep dependencies isolated. The app now opens in the redesigned Download screen with a two-column workflow, clear source/engine status, readable typography, progress feedback and a list of recent files.

F2's presence is verified offline with `DouyinF2Worker.exe --doctor`. This does **not** prove that any particular Douyin profile can be downloaded in real time. If Douyin requires login or rejects access, the app reports the error and does not attempt to bypass protection. See [download UX audit](docs/DOWNLOAD_UX_AUDIT.md). The Windows build in a pull request is experimental until it passes full CI and is published as a Release.

## Offline Chinese OCR (included in Windows v3.1)

The portable Windows build includes RapidOCR, ONNX Runtime and the actual ONNX
model files. **No API key or manual model installation is required**.
The Studio previews OCR-detected Chinese captions as editable boxes, while
manual masking remains available. A single representative frame does not
reliably cover every changing subtitle, so review the video before publishing.
No generic blind mask is applied when OCR is missing or detects no text.

To verify a downloaded portable folder: `DouyinhehePro.exe --ocr-self-test` and `DouyinhehePro.exe --render-self-test`.
See [OCR guide](docs/OCR_OFFLINE.md). This package does not require online model
inference. Model licenses and packaging notices are in `docs/THIRD_PARTY.md`.

## Quick start (development)

Python 3.12 and FFmpeg / FFprobe on PATH:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[all,dev]"
python -m douyinhehe
```

**Windows `.exe`:** the portable ZIP now includes the GUI executable, `bin/ffmpeg.exe`, `bin/ffprobe.exe`, and third-party notices, and must pass a frozen `--self-test`. Open [Actions → Build Windows desktop EXE](../../actions/workflows/windows-build.yml), download the `DouyinhehePro-Windows-x64` artifact after a successful run, extract the ZIP and launch `DouyinhehePro.exe`. GitHub Actions must be enabled, and the workflow must succeed before an artifact exists. Its ZIP includes FFmpeg and FFprobe (check `THIRD_PARTY.md`). The Studio 3.0 Windows engineering-preview build is published under GitHub Releases (v3.0.0).

**Build locally:** `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`. The output executable is `dist/DouyinhehePro/DouyinhehePro.exe`. Local builds require FFmpeg in PATH unless copied to the `bin/` directory.

## V2 batch queue (commercially licensed videos only)

Copy [`examples/manifest-example.csv`](examples/manifest-example.csv) to your local drive and replace example values. Open **08 Batch Queue**, import CSV or JSON, select output directory, and run queued local renders. Invalid/missing permissions are rejected before importing. Successes create `.mp4` and `.provenance.json`. The system deduplicates identical jobs, supports manual retry and an explicit interrupted-render recovery action. No cloud uploads happen in this queue.

**Release validation:** Build CI validates the true FFmpeg/FFprobe binary, then runs the executable with `--self-test`, which exits without the GUI. The portable `.exe` is not claimed to work until the current GitHub Actions run succeeds.

## Safe workflow

1. Choose a niche and research Chinese keywords; review candidate videos manually.
2. Keep written permission showing **commercial use, modification and multi-platform distribution**. Do not assume credit alone grants permission. Save grant evidence and original author.
3. Paste Douyin HTTPS URLs and download only licensed items. Skip URLs requiring unauthorized access; the app does not solve CAPTCHA or access controls.
4. Render batch videos locally, with creator credit, optional Vietnamese SRT and product CTA. Trim/crop/color edits do not remove copyright ownership or guarantee platform originality requirements.
5. Configure Gemini only with a project you have confirmed eligible for Free Tier. Calls never auto-upgrade or auto-select paid models; rate-limited calls stop without falling back.
6. Save products/campaigns, then review each target platform's affiliate disclosures and descriptions.
7. Connect channels in Postiz, confirm each provider's settings and upload/schedule. The **online Postiz service** executes future posts, not the Windows PC after shutdown.

## Postiz settings JSON

The app fetches integration IDs from your Postiz account and prepares editable JSON such as:

```json
[{"id":"id-from-your-postiz","provider":"youtube","settings":{"__type":"youtube"}}]
```

Some platforms require additional provider settings, consent, creator visibility or verification. Consult [Postiz Public API](https://docs.postiz.com/public-api/introduction) and fill in platform-specific settings. The app **does not** invent settings or claim successful posting until Postiz acknowledges the request. API keys go to Windows Credential Manager through `keyring` and are not stored in Git.

## Engineering notes

- All video manipulation is offline FFmpeg; only downloading, Gemini calls and Postiz publishing need network.
- API keys are never stored in SQLite; do not upload grants or personal media to GitHub.
- SQLite and working files default to `%APPDATA%/Douyinhehe` on Windows.
- Check [ARCHITECTURE](docs/ARCHITECTURE.md), [V2_NOTES](docs/V2_NOTES.md), [SKILLS](docs/SKILLS.md), [ROADMAP](docs/ROADMAP.md) and [THIRD PARTY](docs/THIRD_PARTY.md).
- Run `python -m pytest -q` for tests.

## Scope & quality policy

This is a reproducible engineering MVP, **not yet a production-proven automation suite**. TikTok, Instagram, YouTube and Meta may require developer app reviews and support different content features. Profile and Group publishing is not assumed available from official APIs. A single `.exe` cannot perform remote scheduling after PC shutdown without a connected online publisher.


## Release v2.1.0

[Windows releases](https://github.com/Boydeop/Douyinhehe/releases) include
`DouyinhehePro-Windows-x64.zip` and `SHA256SUMS.txt` (not a single standalone .exe).
Run `DouyinhehePro.exe --self-test` or `--doctor` in a Windows terminal to inspect
bundled FFmpeg/ffprobe and your yt-dlp installation. All update checks are initiated
by the user. Read [release notes](docs/RELEASE_NOTES.md) and
[third-party notices](docs/THIRD_PARTY.md) before distribution.

- `Kiểm tra yt-dlp`: reports downloader version and localized access errors.
- `Cập nhật yt-dlp`: official verified GitHub executable, installed in user data
  instead of trying to mutate a frozen Python package.
- `Kiểm tra phụ đề`: character counts, reading speed and a 5-second preview.
- `Dịch & giọng`: glossary + context + optional paid-quota-consuming second-pass
  **Free Tier-confirmed** Gemini review; optional local Piper voice model.
- `Batch Queue`: supports `expires_on`, `evidence_file`, `evidence_sha256` and
  local `local://` video manifests for users' own recorded footage.
- `Affiliate`: normalized CSV with `campaign,video_id,platform,views,clicks,orders,commission`.
- `Batch Editor`: saved local CTA styles, branded color/text position/size.
- `Cài đặt`: export rotating, redacted JSONL diagnostic log.

These are engineering features with CI coverage. Real-world service access,
authorization, translation accuracy, GUI accessibility and signed installer
require separate user acceptance testing.


## Studio 3.0 (development branch)

The v3 mini-editor has a YouTube-style left navigation, a portrait preview with
mouse-drawn blur/solid masks, optional RapidOCR Chinese text suggestions, 9:16
crop/pad/blur, color/CTA/SRT controls, trim bounds, and batch rendering. Without
optional OCR, the auto button **only proposes a generic lower-third** and shows
a clear warning; it cannot assert that Chinese text was detected. The app does
not request author names, evidence files or expiry dates in new workflows.

`morluto/rea` is a reverse-engineering and packaged-executable inspection skill,
not a video editor. Use REA to audit the compiled EXE, not to process media.
The editing design draws on `kajisho5/ffmpeg-skill` and `video-editing-skill`.
Masking licensed video does not override copyright terms or originality rules.
