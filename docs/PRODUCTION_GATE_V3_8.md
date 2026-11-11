# Douyinhehe Studio 3.8 RC1 — production release gate
Date: 2026-11-11. This document is included in the Windows portable ZIP.

## Engineering quality completed in 3.8

- Independent, frozen edit presets per clip for **batch exports**. The previous
  behavior silently reused the active clip's trim, masking, CTA and color on
  other clips. Selected clips keep their own in-memory settings; never copy
  masks or a trim range from another video unintentionally.
- MP4 `comment` metadata is restricted to the public Douyin hostname/path,
  stripping query, fragment, account credentials and session tokens.
- Render outputs remain source-safe, staged, validated by ffprobe and published
  without overwriting an existing export.
- Unit tests cover independent per-clip presets and metadata secret redaction.
- Windows build emits `BUILD_MANIFEST.json` with SHA-256 hashes and sizes of
  the application, bundled FFmpeg/FFprobe and F2 worker. The ZIP includes a
  portable SHA256SUMS file for transport verification.
- Runtime remains local Windows x64 portable **onedir**. Do not move its
  main EXE out of the extracted folder.

## Required automated checks

1. Python checks Windows + Linux: Ruff critical, MyPy scoped contracts, unit
   tests, and synthetic FFmpeg integration.
2. Windows PyInstaller build with pinned FFmpeg tools, frozen RapidOCR models,
   F2 worker and Qt Multimedia libraries.
3. Windows packaged checks: `--self-test`, `--doctor`,
   `--ocr-self-test`, `--render-self-test`, `--ui-smoke-test`,
   `DouyinF2Worker.exe --doctor`.
4. ZIP creation, SHA-256 checksum and inventory. A build is not approved until
   all of these pass on the same commit, and a green SHA-256 manifest exists.

## Mandatory external acceptance before PUBLIC production / v3.8.0 stable

- [ ] Test direct Douyin public URL, official share link, and an authorized
      public channel on the target Windows network. Record sanitized logs for
      failures. Account login, rate limits and CAPTCHA must not be bypassed.
- [ ] Manually verify two authorized MP4 clips of different durations:
      play, seek, edit each separately, switch A/B/A, mask, trim, render both,
      and verify each output visually and with ffprobe. Verify originals and
      previously exported MP4s are intact.
- [ ] Check Windows media playback codecs on a clean Windows 10/11 x64 system,
      a second device or VM, including offscreen/HiDPI rendering and missing
      model errors. Check antivirus SmartScreen behavior and file signing.
- [ ] Verify correct distribution rights and fulfill LGPL/GPL obligations for
      the *actual* bundled FFmpeg 9.0.2 build (may include GPL libx264), Qt/
      PySide6, RapidOCR model weights, and transitive dependencies. This is
      **not** satisfied by simply referencing FFmpeg source on a webpage.
      See `THIRD_PARTY.md` and https://www.qt.io/development/open-source-lgpl-obligations.
- [ ] Test real Postiz OAuth and uploads only with explicitly authorized social
      accounts. Do not advertise fully automated posting without real tests.
- [ ] Approve distribution and create a tagged stable release with matching
      published binaries, licenses, source availability and checksums.
- [ ] Verify rollback: preserve current 3.7 portable ZIP and user SQLite data,
      and test startup with the old data copy. Do not delete or overwrite data.

## Production limitations / explicit non-goals

- This build does not guarantee all Douyin URLs work without cookies. F2
  and yt-dlp cannot promise access to private, login-protected or CAPTCHA
  gated material.
- Not a full multi-track CapCut replacement: advanced transitions, timeline
  keyframes, time-dependent OCR mask tracking and resumable network download
  queue remain unimplemented and must not be advertised as present.
- No signed installer, verified auto-update agent or in-app rollback is
  included. The Windows artifact is an **engineering release candidate** until
  the external gates above are verified.
- Copyright and distribution rights for source media remain the user's
  responsibility. Cropping, color edits or music replacement do not erase
  the original content's rights.

## Installation and recovery

1. Download `DouyinhehePro-Windows-x64` from the green GitHub Actions run.
2. Verify `SHA256SUMS.txt` against the nested ZIP before extraction.
3. Extract the complete `DouyinhehePro` folder to a local NTFS volume.
   Execute `DouyinhehePro.exe` inside that folder. Do not move only the EXE.
4. The built-in downloader check under Tải Douyin reports **local engine**
   readiness without cookies. It does not prove live Douyin availability.
5. Export sanitized diagnostic logs for troubleshooting; inspect the exported
   log before sharing because upstream error messages can vary.
6. Backup the user data folder before switching from 3.7. If any problem
   occurs, use the previous portable ZIP with the saved data backup.

**Release decision: RC build permitted after green CI; public production
distribution is blocked until every applicable external checkbox is verified.**
