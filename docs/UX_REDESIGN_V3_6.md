# Douyinhehe Studio 3.6: desktop UX audit and acceptance

## Design direction

An offline-first **production workspace**, not an imitation web dashboard or
a long settings form. Retain native PySide6 and predictable Windows behavior.

### Source skills and adoption decisions

| Source | Applied principle | Adoption |
| --- | --- | --- |
| [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | hierarchy, focus, contrast and touch targets | Principles only; design tokens implemented in `ui_theme.py` |
| [Anthropic Frontend Design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | visual hierarchy, distinctive purpose-built layout | Adapted to native desktop widgets, not React source |
| [Impeccable](https://github.com/pbakaus/impeccable) | critique, reduced clutter, accessible states, helpful error messages | Manual design checklist and UX copy |
| [PyQtDarkTheme](https://github.com/5yutan5/PyQtDarkTheme) | palette and consistent light/dark widgets | Compared only; no new dependency, package release supports Python <3.12 |
| [PySide6 Fluent Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) | Fluent visual reference | Not bundled; GPL/commercial license requirements conflict with unreviewed distribution |
| [F2](https://github.com/Johnserf-Seed/f2), [yt-dlp](https://github.com/yt-dlp/yt-dlp) | independent downloader engines | Existing isolated worker and conditional fallback; no authentication bypass |

GitHub stars do not replace code review or licensing checks. Skills guide
engineering decisions and are not automatically installed into the EXE.

## Design changes shipped in 3.6 RC1

- New native Qt dark/light palette with consistent tokens across all nine screens.
  Background surfaces, inputs, tab panels, focus states and primary CTA styles
  share a measured hierarchy; theme persists across sessions using QSettings.
- Keyboard quick navigation (`Ctrl+K`, enter a screen name), dynamic screen
  title/description, icons and quick video import.
- More breathing room, clearer sidebar, collapsible technical logs, status
  footer and no new web runtime or heavyweight widget dependency.
- Explicit paste/clear/open-folder actions on Douyin download screen;
  user-facing public-access guidance with no request for exported cookies.
- Editor library count and empty-state affordances. Actions are disabled
  when no clip is selected or while a render is running.
- Preserves all existing workflow pages, offline OCR, FFmpeg render, Postiz,
  Gemini opt-in and OS credential storage.

## Critical limitations

- F2/yt-dlp can download **some** public links without manually provided
  cookies. No engine guarantees access to private videos, logged-in feeds,
  content behind verification/403/429, region restrictions or expired URLs.
- A Qt video player is not a multitrack NLE. No claim of complete CapCut
  equivalence, motion-aware OCR for all frames, or automatic copyright clearance.
- The Windows app is a portable directory ZIP, not one standalone EXE.
  The executable relies on bundled FFmpeg, Qt plugins, F2 and OCR model assets.
- Windows CI verifies headless widgets/media and the packaged runtime, but
  does not prove interactive playback and downloads on the user's own PC.

## Quality gates

1. Unit tests including two theme contrast tests, invalid-theme rejection,
   source safety checks and video render coverage.
2. Frozen Windows GUI smoke: 9 screens, existing downloader, media library
   empty state, searchable navigation and dark/light switch roundtrip.
3. Frozen Windows `--self-test`, `--ocr-self-test`, `--render-self-test`,
   F2 worker `--doctor`, packaged FFmpeg/FFprobe probes and ZIP checksum.
4. Manual acceptance on a regular Windows machine: font contrast, DPI
   100%-150%, 1050px minimum width, keyboard navigation, video import,
   audio seek, trim, mask OCR, real MP4 export and no overwrite.
5. Authorized live Douyin direct/short/profile links; inspect redacted error
   logs when access is refused. Never call 403/CAPTCHA a guaranteed fix.

### Next iteration, explicitly not yet shipped

- Collapsible/resizable sidebar at narrow window sizes.
- Per-clip timeline tracks, multi-cut and crossfade transitions.
- Bounded and resumable download queue with pause/cancel.
- Intelligent moving-subtitle detection, with per-frame editing preview.
- Optional commercially licensed Fluent widget pack only after license review.

## Important Windows startup regression found by UX capture

The first 3.6 UX capture failed because `build_settings()` still referenced
`MainWindow.on_ocr_check`, a callback dropped during the earlier editor
replacement. The prior frozen `--windowed` UI smoke appeared to pass despite
a Python traceback. A successful Windows build does **not** establish a
usable GUI when the exit status is unreliable.

Fixes: restore an asynchronous offline OCR inference check handler, add a
static regression test for all referenced `on_*` callbacks, require a
success-marker file from the frozen `--ui-smoke-test`, and capture actual
native Qt screens as a separate Windows Actions artifact. Do not merge before
all of these gates pass.
