# Douyinhehe Studio 4.0.0 RC1 · Windows production candidate

## What's new

- **Persistent, local editing projects:** Save/reopen `.dhyproj` with per-clip
  trim, aspect ratio, colors, manually selected masks, CTA, subtitles and
  narration. A `.dhyproj.bak` backup retains the previous file when saving
  over an existing project. Projects do not contain embedded videos or API keys.
- **Correct batch exports:** `Xuất toàn bộ` applies each video's own
  settings instead of silently using the currently selected video's preset.
- **Non-destructive exports:** Windows NTFS/exFAT compatible atomic
  no-overwrite publishing; source clips and previous exports are preserved.
- **Two Windows distributions:** `DouyinhehePro-Setup-x64.exe` is a single
  installer EXE; `DouyinhehePro-Windows-x64.zip` is the portable folder.
  Both have SHA-256 checksums in `SHA256SUMS.txt`.
- **Safer installer removal:** NSIS removes known packaged files, leaving
  user-added files and the application data directory alone.
- **Stricter Windows release pipeline:** automatic tests now wait for the
  actual GUI EXE process exit status and validate clean installation,
  startup, Qt UI and removal. Previous smoke checks could report green even
  when the GUI test raised an exception.
- Maintains the 3.7 native Qt dual-theme layout, UI feature search,
  licensed public-link F2/yt-dlp downloader, bundled RapidOCR and FFmpeg.

## Acceptance and limitations

This is an **unsigned engineering release candidate**, not a claim of
complete live production certification. Use only videos you are authorized to
download, modify and distribute. Public Douyin availability depends on
source/region/network and platform access rules; authentication requirements,
CAPTCHA and 403/429 are not bypassed. Remote Postiz/platform scheduling needs
separately authorized credentials and real end-to-end testing. FFmpeg/Qt/F2
redistribution license obligations, publisher code signing and manual Windows
acceptance must be reviewed before any general commercial production launch.

See `docs/PRODUCTION_READINESS_4_0.md` for checklist, recovery instructions
and the precise production quality gates.
