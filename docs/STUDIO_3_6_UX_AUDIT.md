# Douyinhehe Studio 3.6: UX and downloader audit (11 Nov 2026)

## Goal

Improve an existing Vietnamese Windows app, not reproduce a web dashboard.
Tasks: import a public Douyin link, download authorized footage, immediately
open it in the local editor, play/trim/mask, preview, and export a verified MP4.

## Sources reviewed and adoption decisions

- [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
  (MIT): design hierarchy, spacing, color/focus guidelines; manually adapted to
  existing native PySide6 widgets rather than embedding the web stack.
- [vosslab/vosslab-skills: pyside6-engineer](https://github.com/vosslab/vosslab-skills)
  (review reference): signal-slot and existing-widget upgrade approach, not a
  dependency. Use Qt documentation to validate actual methods.
- [kajisho5/ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill)
  (MIT): probe/edit/verify, FFmpeg-based preview and export already implemented.
- [zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets):
  visually useful but GPL-3.0/commercial licensing; **not copied or bundled**.
- [yt-dlp/yt-dlp PR #17826](https://github.com/yt-dlp/yt-dlp/pull/17826):
  experimental no-cookie Douyin extraction discussed upstream. No unreviewed
  fork or signature/access-control circumvention embedded automatically.
  Test only released, officially maintained engines and permitted public URLs.
- [Johnserf-Seed/f2](https://github.com/Johnserf-Seed/f2):
  existing separate worker for direct, share and profile URLs; the no-cookie
  workflow never requests the user's browser cookie store.

## Implemented in 3.6 RC

1. Native, MIT-project-friendly QSS color tokens with accessible foreground,
   focus rings, selected navigation items and disabled control states.
2. Uncluttered shell with current activity pill, a quieter developer-log toggle
   and better sidebar hierarchy.
3. Keyboard navigation: Ctrl+1 downloader, Ctrl+2 editor, Ctrl+3 subtitles,
   Ctrl+4 batch, Ctrl+5 publishing; Ctrl+L focuses URL field.
4. Better downloader guidance: public link, no manual cookie import, clear
   acknowledgment of platform access limits.
5. Automatic transfer of newly downloaded MP4 files to the Studio library;
   one-click transition to local editor.
6. Clear editing steps, library typography, action tooltips and named controls.
7. Headless frozen GUI smoke assertions, QSS contract and contrast tests.

## Acceptance tests

- Python checks on both Ubuntu and Windows.
- Windows PyInstaller portable build, OCR/FFmpeg/F2 checks, GUI smoke test.
- Manual: edit an authorized MP4, verify duration/audio/seek/masks and export.
- Manual: try an accessible direct and short Douyin URL on the user's Windows
  network. Log HTTP 403/CAPTCHA/login as blocked, not a successful download.
- Use the packaged folder, not just the entry-point .exe; full portable ZIP
  includes runtime assets. Do not promise a single standalone EXE.

## Limitations

This is not a complete multitrack NLE, and no legitimate client can promise to
download every Douyin URL without account authentication. Copyright permission
remains necessary before modifying/reuploading third-party videos. Public
distribution requires a third-party license review (especially FFmpeg).
