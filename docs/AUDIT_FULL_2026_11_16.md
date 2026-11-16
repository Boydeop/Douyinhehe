# Douyinhehe 3.8.1 RC1 — full-repository reliability audit (2026-11-16)

**Repository:** [Boydeop/Douyinhehe](https://github.com/Boydeop/Douyinhehe)
**Baseline reviewed:** `main` at `c245f84e55d3e99c6cd6da7247a6981af7ec43b7`.
**Scope:** all file paths inventoried; code-level examination of the downloader, batch licensing/queue, SQLite persistence, FFmpeg renderer, editor state and UI, Postiz adapter, updater, logging, Windows build scripts, and existing test coverage. Supporting OCR, subtitle, TTS, affiliate and theme modules also received static-pattern checks.
**Methods:** source inspection, code pattern search, deterministic regression tests, real FFmpeg integration test, CI syntax/type/smoke checks. **This is not a penetration test, a license/legal opinion or a successful real-world Douyin download certification.**

## 🔴 1. Critical/high-impact bugs

| ID | Cause and location on baseline | User impact | Resolution in 3.8.1 |
|---|---|---|---|
| C-01 | `src/douyinhehe/batch.py`: `read_manifest()` ignored `expires_on`; `create_local_manifest()` accepted but discarded it; `BatchItem.payload()` stripped the date; `core.py` privacy scrub removed the queued date. | A render enqueued under a limited-time grant could still run after the grant expired. | **Fixed**: preserve the non-secret expiry date in queued jobs and validate again during `run_queue`. Never retain private creator/evidence files in the job payload. |
| C-02 | `src/douyinhehe/media.py`, `build_edit_command()`: FFmpeg `-shortest` ended the exported clip when the optional voice track (or original sound) ended before video. | Unintentionally truncated MP4 and loss of footage. | **Fixed**: use audio `apad` before `-shortest`, preserving full video duration, with an integration regression using short synthetic narration. |
| C-03 | `src/douyinhehe/downloader.py`: F2 returned changed MP4 paths based only on extension + size; yt-dlp accepted any existent path it printed, without checking the selected destination or actual decodable video. | Corrupted media or an unrelated file could be shown as a successfully downloaded video. | **Fixed**: resolve and scope paths to download root, enforce minimum file size/known video extensions and run FFprobe video-stream verification before recording success. |
| C-04 | `src/douyinhehe/batch.py`, `run_queue()`: provenance sidecar stored the original full Douyin URL with query parameters. | Share-token or session-like query values could leak into a JSON file adjacent to the exported video. | **Fixed**: use the same query/fragment-dropping metadata sanitizer as exported MP4. |

The app's `LicenseGrant` is still a **user self-attestation** gate: the software cannot independently confirm copyright ownership or a creator's consent. Download eligibility, login walls, CAPTCHA and private videos are controlled by Douyin and cannot be guaranteed without cookies.

## 🟡 2. Performance improvements and open opportunities

| Finding | File | Status |
|---|---|---|
| UI log widget grew without a block limit during lengthy download/batch sessions. | `app.py` | **Fixed**: cap at 1,000 blocks; rotated log remains on disk. |
| Validating downloaded media requires one FFprobe invocation per new file; correct but slower for enormous channel imports. | `downloader.py` | **Accepted trade-off** for data integrity. Future: process a trusted worker-produced manifest, bounded parallel verification (2–4 processes), and cache keyed by path/size/mtime. |
| F2 compares recursive MP4 snapshots before and after downloads. Work scales with all historic MP4s, not just new ones. | `downloader.py` | **Open optimization**: worker-produced output manifest or monitored isolated subdirectory, without losing changed-file detection. |
| Preview and export each re-encode video via x264 `medium`. | `media.py` | **Open optimization**: separate `veryfast` preview preset, optional user-selected quality, and measured hardware-acceleration path with CPU fallback. |
| Clip metadata may be probed multiple times when users switch clips. | `editor_workspace.py` | **Open optimization**: cache FFprobe metadata by canonical path, size and modification time. |

## 🟢 3. Refactor / maintainability plan

1. **Separate the GUI from service code.** `app.py` (~1,100 lines) and `editor_workspace.py` (~760 lines) mix widget construction, data validation, job orchestration and business logic. Split into Qt page/controller modules and typed headless services, preserving the existing CLI and smoke contracts.
2. **Unify downloader providers.** Convert F2/yt-dlp into implementations of a small adapter interface with structured results (`files`, `diagnostics`, `access_denied`, `unsupported`) and a single verification step. Replace the current textual exception classification progressively.
3. **Add explicit database migrations and DTOs.** Keep a schema version, and centralize expiration/attribution rules. Do not persist sensitive license documents or account credentials.
4. **Make background jobs cancelable.** `subprocess.run` currently waits for the command to finish; future improvement is `Popen` with bounded tail logs, cancellation and termination of process trees. This is not marked implemented.
5. **Strengthen UI tests.** Add keyboard, resize, drag-and-drop and multiclips exercises on a real Windows desktop. Headless CI alone does not validate the perceived UI design.
6. **Pin/audit build dependencies.** Continue producing SHA-256 manifests; run dependency advisory checks, inspect FFmpeg/Qt license obligations, and sign the production binary if it is distributed commercially.

## 🛠️ 4. Actual code changes

- `src/douyinhehe/batch.py`, `core.py`: license expiry preserved, checked at execution; metadata sanitized.
- `src/douyinhehe/media.py`: audio padding, resource guard for oversized output frames (4K UHD max).
- `src/douyinhehe/downloader.py`: verified playable video inside target folder, linear deduplication.
- `src/douyinhehe/app.py`: bound UI log history.
- Tests added: `tests/test_production_audit.py`, `tests/test_download_integrity.py`; old synthetic downloader fixtures adjusted to explicitly mock the external validator.
- `pyproject.toml`, `src/douyinhehe/__init__.py`, `windows-build.yml`: version `3.8.1rc1`, plus matching release notes.

## 5. Release acceptance and known gaps

- **Required automatic gates:** Python compile, Ruff critical errors, mypy typed subset and pytest on Ubuntu/Windows; real FFmpeg render integration on Linux; bundled Windows OCR inference, FFmpeg masked render, EXE self-test, downloader doctor and Qt offscreen smoke; ZIP artifact with SHA-256.
- **Manual acceptance still required before calling stable production:** real public/authorized Douyin video & profile samples; 403/429/CAPTCHA behaviors; GUI mouse/keyboard tests on an ordinary Windows computer; publishing with approved Postiz integrations; commercial redistribution licenses, code signing, roll-back restore and malware screening.
- **Out of scope for this bugfix release:** a full multitrack CapCut-level timeline, bypassing restricted Douyin access, automatic credential/cookie theft, official platform account permissions.
- **Artifact location:** [GitHub Actions / Windows EXE workflow](https://github.com/Boydeop/Douyinhehe/actions/workflows/windows-build.yml). Find a successful run for the PR or merge commit, download `DouyinhehePro-Windows-x64`, extract the archive and open `DouyinhehePro.exe`. The EXE is onedir, not standalone.
- **Status:** release candidate, not a guarantee of bug-free or legally authorized production use.

The report distinguishes **fixed code** from **unimplemented optimization/refactor proposals**. No CI result is asserted until the corresponding GitHub Actions run actually completes.
