# Douyinhehe Studio 3.8 RC1 — production hardening

Changes:
- Fix batch export applying the active clip's trim/masks/colors/CTA to other clips.
- Freeze and validate an independent FFmpeg preset for every source video.
- Remove session query strings, share tokens and URL credentials from MP4 metadata.
- Add deterministic regression tests for per-clip presets and private metadata.
- Include hashed Windows component inventory and a production-readiness gate.

Quality gate: Python checks on Windows/Ubuntu and frozen Windows EXE smoke.
Live Douyin, interactive Windows playback, provider OAuth, code signing and actual
Qt/FFmpeg commercial-redistribution licensing must be verified before a public
stable release. This is a *release candidate*, not a completed production release.

See docs/PRODUCTION_GATE_V3_8.md.

# Douyinhehe v3.2.0 · Download UX and channel support

- Detect profile URLs and route to separately bundled F2 worker instead of unsupported yt-dlp profile extractor.
- Detect both `/user/id` and `/user/id?vid=...` while preserving user-selected rights confirmation.
- Accessible task-first downloader UI: bigger typography, two-column layout, engine guidance, recent files, busy progress and clear error feedback.
- Network-free tests for auto routing, F2 subprocess, known exceptions and frozen Qt UI.
- F2 remains subject to Douyin's availability and access policy; a successful build does not prove live channel download.
- Packaging and legal notices updated for separately frozen F2 (Apache-2.0).

**Engineering preview.** The new F2 worker and UX are intended to be tested with an authorized Douyin channel before claiming live compatibility.
