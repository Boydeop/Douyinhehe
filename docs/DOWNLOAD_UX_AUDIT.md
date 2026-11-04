# Douyinhehe Downloader UX and failure audit · 2026-11-04

## Reproduced from screenshot
- The pasted URL begins with `https://www.douyin.com/user/...` and includes a `?vid=` query.
- The previous default selected **multiple video links** and forwarded that profile URL to yt-dlp, which reports "Unsupported URL".
- This is a wrong-engine dispatch, not evidence that the user's URL is malformed.
- Existing UI used small text, very wide single-column forms, dark-on-dark controls, unclear progress state, and showed a modal without actionable guidance.

## Relevant upstreams
- UI UX Pro Max: <https://github.com/nextlevelbuilder/ui-ux-pro-max-skill>, MIT. Applied task-first navigation, visual hierarchy, legible tokens and grouping.
- Anthropic frontend-design: <https://github.com/anthropics/skills/tree/main/skills/frontend-design>. Applied error copy in Vietnamese with action-specific feedback.
- F2: <https://github.com/Johnserf-Seed/f2>, Apache-2.0. F2 documents `dy --mode post --url <Douyin profile> --path <folder> --max-counts N`.
- yt-dlp issue: <https://github.com/yt-dlp/yt-dlp/issues/2120>, documents missing profile extractor.
- PyQt Fluent Widgets (reference only): <https://github.com/zhiyiYo/PyQt-Fluent-Widgets>, GPL-3.0. Not embedded; native PySide6 widgets keep packaging simpler and avoid introducing GPL UI source.

## Changes made
1. Auto-detect `/user/<id>` URLs, ignoring benign query parameters. Route profiles to isolated F2, individual videos to yt-dlp.
2. Improve error states: missing engine, unsupported profile, access failure, timeout, partial batch completion.
3. Redesign download page: side-by-side source/permissions and settings/actions, visible source classification, meaningful progress, and recent downloaded filenames.
4. Increase font and hit targets; retain focus styling and contrast.
5. Add a Qt frozen-app UI smoke check for default auto mode and profile recognition.
6. Add network-free unit tests mocking F2 worker, ensuring profile URLs never hit yt-dlp.

## Limits and release gate
- F2 cannot guarantee access to every Douyin profile; Douyin may return access denial or verification. Never circumvent CAPTCHA or rate limits.
- The separately bundled F2 worker runs without supplied cookies or account secrets.
- Windows build must run **F2 --doctor** and the existing OCR, FFmpeg and Qt smoke tests.
- Passing offline tests does not prove successful downloading from a particular live Douyin profile. Require an authorized live test before claiming this as fixed for all channels.
- No merge/release should occur if mandatory CI fails.
