# Douyinhehe Pro 2.0 engineering release notes

## New
- Recoverable SQLite local render queue with explicit CSV/JSON manifests; each source has an individual commercial/derivative license assertion, original URL, creator and grant evidence reference.
- Hash-based duplicate job prevention, atomic job claims, explicit retry of failed jobs, opt-in recovery after interruption. Interrupted local jobs may be resumed, but remote postings are NEVER automatically replayed.
- Atomic output rendering. If FFmpeg fails or validation fails, an earlier valid target remains intact.
- Per-export `.provenance.json` sidecars preserve author/source, rights evidence reference, and SHA-256 hashes of input/output. This metadata does not assert legal ownership or prove a grant.
- Delivery checks for five destinations, aspect ratio/codec recommendations and source/affiliate disclosure guidance, without making publication eligibility claims.
- Two desktop tabs: `08 Batch Queue` and `09 Kiểm tra video`.
- Frozen-app `--self-test` checks packaged FFmpeg and FFprobe and writable local database, without opening Qt.
- Windows workflow no longer copies Chocolatey shim executables. It copies executable files from the installed FFmpeg package directory and verifies both commands before the ZIP is made.

## Still dependent on external approval and infrastructure
- Douyin metadata/media access can fail after site updates. No CAPTCHA avoidance.
- Google Gemini must be used with the user's own Free Tier-eligible project and an explicit opt-in; no cost guarantee.
- Meta/TikTok/YouTube/Instagram/Threads publish rights depend on provider OAuth, account type, app review and Postiz-specific configuration; Postiz runs separately and requires a live server to continue posting after Windows shuts down.
- Attribution and permission are separate. Color shifts and crops do not nullify original copyright or originality/reused-content policies.

## Manifest use
Copy `examples/manifest-example.csv`, replace the example path, creator, source URL and license evidence with your own. Use relative file paths rooted at the manifest folder or absolute local paths. Set `commercial=true` and `derivative=true` only when verified. A row without rights is rejected before queue insertion. Each changed preset/manifest row becomes a different job key.
