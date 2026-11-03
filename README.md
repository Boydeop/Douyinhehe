# Douyinhehe Pro · Affiliate Video Studio

Windows desktop studio for **licensed Douyin videos**, Vietnamese subtitle translation and affiliate multi-channel publishing. **Current status: 2.0.0 engineering preview**. No claims of guaranteed views, copyright immunity, or unrestricted automatic posting. Interface is Vietnamese.

## Implemented

| Module | Available now | Limitations |
| --- | --- | --- |
| Niche research | Chinese keyword collections, manually weighted opportunity score, saved sources | No automated Douyin search API; metrics entered manually |
| Douyin downloader | Batch input links, profile/playlist cap, progress, local catalog via `yt-dlp` | Douyin changes frequently; public URL access may fail; no anti-bot bypass |
| Rights & credit | Explicit commercial/editing grant, evidence reference, visible creator overlay, source metadata | User must verify rights to music and third-party material |
| Batch video | 9:16 crop/pad/blur, color grading, CTA, optional SRT, optional voice replacement, MP4 H.264/AAC | Requires FFmpeg with libx264, drawtext and subtitles filter as applicable |
| Mandarin transcription | Optional `faster-whisper` offline | Model weights downloaded separately on first use; CPU may be slow |
| Translation | Google Gemini SDK to translate SRT in batches, local cache, manual Free Tier opt-in | API key and actual Free Tier entitlement required; quota errors stop processing |
| Vietnamese TTS | Offline Windows SAPI via pyttsx3 | Vietnamese SAPI voice must already be installed; not auto-bundled |
| Affiliate | Niche/product/campaign/link library; CTR and conversion calculator | No affiliate platform order API or automatic sales sync |
| Publishing | Postiz Public API: list connected channels, upload video, schedule batch | Postiz API key, connected OAuth channels, provider-specific settings, server/service online required |
| Desktop | PySide6 worker queue, SQLite, OS credential storage, nine feature tabs | Live platform authorizations still need user testing |
| V2 batch pipeline | CSV/JSON manifests with per-video rights, recoverable render jobs, deduplication, provenance sidecars | Only local edits auto-retry; remote publishing stays manual-approval |
| V2 delivery QA | Codec/aspect checks and per-platform CTA/source guidance | Guidelines, not platform approval |

## Quick start (development)

Python 3.12 and FFmpeg / FFprobe on PATH:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[all,dev]"
python -m douyinhehe
```

**Windows `.exe`:** the portable ZIP now includes the GUI executable, `bin/ffmpeg.exe`, `bin/ffprobe.exe`, and third-party notices, and must pass a frozen `--self-test`. Open [Actions → Build Windows desktop EXE](../../actions/workflows/windows-build.yml), download the `DouyinhehePro-Windows-x64` artifact after a successful run, extract the ZIP and launch `DouyinhehePro.exe`. GitHub Actions must be enabled, and the workflow must succeed before an artifact exists. Its ZIP includes FFmpeg and FFprobe (check `THIRD_PARTY.md`). There is not yet an installer or a published GitHub Release.

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
