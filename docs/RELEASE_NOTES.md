# Douyinhehe v3.2.0 · Download UX and channel support

- Detect profile URLs and route to separately bundled F2 worker instead of unsupported yt-dlp profile extractor.
- Detect both `/user/id` and `/user/id?vid=...` while preserving user-selected rights confirmation.
- Accessible task-first downloader UI: bigger typography, two-column layout, engine guidance, recent files, busy progress and clear error feedback.
- Network-free tests for auto routing, F2 subprocess, known exceptions and frozen Qt UI.
- F2 remains subject to Douyin's availability and access policy; a successful build does not prove live channel download.
- Packaging and legal notices updated for separately frozen F2 (Apache-2.0).

**Engineering preview.** The new F2 worker and UX are intended to be tested with an authorized Douyin channel before claiming live compatibility.
