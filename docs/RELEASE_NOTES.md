# Douyinhehe Pro v3.0.0 · Engineering Preview

**Portable Windows x64:** Download `DouyinhehePro-Windows-x64.zip` and `SHA256SUMS.txt`,
verify SHA-256, unpack the entire `DouyinhehePro` directory, and run
`DouyinhehePro.exe`. Keep the `bin` and `_internal` directories alongside it.

## Highlights
- Douyin downloader supports a multiline URL batch and **full profile**
  (`douyin.com/user/...`) mode with an explicit unlimited option and
  persistent `yt-dlp` archive for duplicate avoidance. Profile coverage
  depends on the extractor, available access and Douyin behavior.
- No author, contract or license-expiration fields in the new download, video
  editor and local manifest workflows. New records do not store those fields.
  A **user-confirmed cleanup action** removes legacy sensitive SQLite metadata.
  Older exported provenance JSON files are not automatically removed.
- Mini-editor with YouTube-inspired navigation, frame preview, mouse-drag
  blur/solid subtitle masks, per-video automatic region proposals, trim,
  9:16 reframing, color tuning, SRT, narration, CTA and batch rendering.
- Optional RapidOCR suggests actual regions with recognized Chinese characters.
  **The portable EXE does not include RapidOCR by default.** Without it, the
  automatic feature only suggests a generic lower-third and reports that it
  did not detect text. Always review results.
- CI: Ubuntu/Windows tests, FFmpeg masked-render regression test, packaged
  FFmpeg and a Qt UI smoke test for the frozen Windows EXE.

**Boundaries:** This is a small batch editor, **not** a full CapCut multitrack
editor. License rights must cover commercial reuse, editing and platform
distribution. Attribution obligations remain applicable. Editing or hiding
subtitles does not bypass copyright or originality policies. Douyin access
and social publishing can fail or require account authorization and OAuth.
Cloud posting after shutdown requires a separate online service; it is
not provided by the desktop EXE alone.

Source license: MIT. Bundled Qt, FFmpeg, other dependencies and optional OCR
models have their own redistribution obligations; consult third-party notices.
This engineering preview is not code-signed.
