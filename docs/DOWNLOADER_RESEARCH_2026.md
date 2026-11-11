# Douyin downloader audit · 04 Nov 2026

## Reproduced user reports

- A direct Douyin video URL (`https://www.douyin.com/video/<id>`) failed in v3.2.
- A public share short link (`https://v.douyin.com/<token>/`) failed in v3.2.
- UI counted the failed task as "completed", and surfaced a generic error instead of the downloader's actual exit reason.
- Root cause inside our application: videos and short links were routed only to yt-dlp; F2 was reserved for profile feeds. This is confirmed by the v3.2 `download_authorized` branch and is separate from potential Douyin-side access restrictions.

## Repositories checked on GitHub

| Repository | License | Strength | Constraint |
|---|---|---|---|
| [Johnserf-Seed/f2](https://github.com/Johnserf-Seed/f2) | Apache-2.0 | Python CLI has `one` and `post` modes for Douyin; works with an isolated EXE worker | Latest official PyPI release is 0.0.1.7 (Dec 2024), and Douyin access can change |
| [jiji262/douyin-downloader](https://github.com/jiji262/douyin-downloader) | MIT | Rich batch archiving, dedup, download integrity, Playwright fallback | README explicitly reports Douyin security verification currently blocks CLI video downloads |
| [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) | Apache-2.0 | Large self-hosted API with download queues, sessions, status | Requires a server / database and exposes a larger security/maintenance surface |
| [JoeanAmier/TikTokDownloader](https://github.com/JoeanAmier/TikTokDownloader) | GPL-3.0 | Mature batch download and metadata tooling | GPL obligations and separate architecture; do not copy into the MIT desktop |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | Broad generic media extractor | Douyin 403/fresh-cookie errors documented, e.g. upstream issue #9667 |
| [qianzhu123/douyin-downloader](https://github.com/qianzhu123/douyin-downloader) | MIT per README | Playwright-based short/direct link handling | Very small, relatively unverified repository; browser install required; not selected for automatic bundling |

## Immediate changes in v3.3 development branch

1. Use F2 `one` for videos or `v.douyin.com` share URLs, and F2 `post` for profile feeds.
2. Use yt-dlp only if F2 is unavailable or explicitly reports unsupported URL; do not use fallback when access is denied, CAPTCHA/login is required, or the service rate-limits.
3. Detect downloaded MP4 files on disk; an exit code of zero with no new files is not treated as success.
4. Preserve the sanitized upstream diagnostic in UI and logs, including backend and status category.
5. Redact cookies, session tokens and API credentials from exported logs.
6. Add mock-based regression tests for the exact URL types seen in the user's screenshots.

## Acceptance criteria before main/release

- Python tests on Windows + Ubuntu, plus Windows packaged app smoke tests.
- Confirm the packaged F2 worker actually imports and runs the Douyin CLI and the app can recognize direct/short/profile URL shapes.
- Use a real video and short link **the user is authorized to download**, test on Windows with access available to that user, and inspect the sanitized diagnostic when blocked.
- No guarantee of successful downloads if Douyin restricts access, a share link has expired, or the user lacks permission.
- No automatic CAPTCHA solving, signature forgery, login bypass, private-cookie harvesting, or repeated request loops.

## Operational checklist for affected users

1. Open the URL in a normal browser and verify it actually plays with the user's current authorized access.
2. Try the new Windows artifact with the link, then use **Xuất nhật ký chẩn đoán** in the Download page.
3. The log should identify `F2 (one)`, `F2 (post)`, or `yt-dlp`, whether any MP4 files appeared and the actual access error.
4. Do not paste passwords, cookies, or login session identifiers into issue reports.
