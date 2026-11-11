# Douyinhehe 3.5 integrated audit — 11 November 2026

## Scope and provenance

Working branch: `integration/douyinhehe-3-5-audit`, derived from the
real-editing workspace PR #7 and integrated with downloader diagnostics PR #6.
The project targets a local Windows PySide6 application, not a hosted
video-editing service. This audit covers static source review, CI checks, and
the packaged Windows smoke test. No end-user interactive or authenticated
Douyin test is implied by CI.

## Areas reviewed

| Area | Implemented and testable | Remaining limitation |
| --- | --- | --- |
| Douyin URLs | HTTPS host validation, videos/short links through isolated F2 one, profiles through F2 post | Website access, expired links, 403/429 and CAPTCHA cannot be solved by offline CI |
| Download result | New MP4 detection; no new media is failure, not success | Duplicate-only downloads can report no new file |
| Diagnostics | User-visible engine errors, export redaction, no plaintext API credentials | Users must inspect logs before sharing; no guarantee every upstream token format is recognized |
| Desktop editor | Local Qt playback, IN/OUT, 9:16/16:9/square, colors, manual masks, OCR frame suggestions | Single-source timeline, not multi-track CapCut; Qt codec support varies |
| Render | FFmpeg staged MP4, ffprobe verification, no source replacement and no overwrite of prior export | No cross-volume hard-link publication; local NTFS recommended |
| OCR | Packaged RapidOCR/ONNX models and frozen self-test | One sampled frame is not continuous subtitle tracking |
| Batch | Multi-clip export, unique output allocation, worker jobs | Same trim/mask parameters need manual per-clip QC |
| Credentials | OS credential store; no API keys saved in project source | Connected providers still require user authorizations |
| Posting | Postiz integration with user-approved settings | Live OAuth, remote scheduling, platform approval not tested |
| Windows | PyInstaller onedir, FFmpeg/ffprobe, F2 worker, Qt Multimedia and OCR smoke checks | Portable folder/ZIP, not a guaranteed single standalone EXE |

## Engineering acceptance

1. GitHub Actions **Python checks** must pass for both Windows and Linux.
2. GitHub Actions **Build Windows desktop EXE** must pass on this *integrated* branch,
   including `--self-test`, `--ocr-self-test`, `--render-self-test`,
   `--ui-smoke-test` and isolated F2 worker `--doctor` when configured.
3. Confirm an actual local MP4 can be played, seeked, masked, previewed and
   exported by a human on Windows. Verify its duration/audio/sync, and that
   the original never changes.
4. Test a licensed Douyin direct link, a valid share link and one profile on
   the user's Windows network. If login/CAPTCHA/403 occurs, show the reason.
5. Confirm subtitle translations and Postiz publishing separately with opted-in
   accounts and any applicable quotas. They are not proved by CI.

## Findings and changes

- **Resolved:** The 3.2 video/short-link route used yt-dlp while profiles
  alone used F2. F2 one/post routing now shares the packaged worker.
- **Resolved:** F2 exit-code 0 without a verified new MP4 was a false success.
- **Resolved:** Old edit screen was a form instead of a playable timeline;
  the Qt editor now produces real FFmpeg previews and exports.
- **Resolved:** Render completion previously used replacement publication and
  could overwrite an output created concurrently. Atomic hard-link publication
  now refuses to replace the existing destination.
- **Resolved:** Separate PRs lacked an integrated verification branch. This
  candidate combines their modules and UI, and re-runs CI.
- **Open:** Real Douyin network verification, Windows interactive seek/audio,
  continuously changing subtitle OCR, multitrack timeline, and live platform OAuth.
- **Open:** Commercial FFmpeg/Qt/PyInstaller/third-party redistribution review
  and user-facing signed single-file packaging.

## Skill/repository selection

See [SKILLS.md](SKILLS.md) for source licensing and adoption decision.
Review `ui-ux-pro-max-skill` for design principles and
`kajisho5/ffmpeg-skill` / `video-editing-skill` for deterministic media QA.
Do not auto-install their agent runtimes into the EXE or copy GPL UI code
into the MIT commercial application.

**Release policy:** Never call a build fully production-ready solely because
CI is green. Do not claim 100% Douyin success or copyright immunity.
