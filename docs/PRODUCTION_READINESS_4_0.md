# Douyinhehe 4.0: production-readiness audit

Date: 11 November 2026. Target: local Windows 64-bit creator studio for **authorized**
Douyin footage. Source baseline: 3.7.0rc1 on main. Branch:
`feat/studio-4-0-production-candidate`.

## Release artifacts and integrity

- `DouyinhehePro-Setup-x64.exe`: **single-file Windows installer** built
  with NSIS, installing the packaged Qt/FFmpeg/F2/OCR onedir folder.
  The installed application itself is not a single binary.
- `DouyinhehePro-Windows-x64.zip`: portable application folder for
  users who prefer no installer.
- `SHA256SUMS.txt`: SHA-256 for **both** installer and portable ZIP.
  Verify file hashes before launching downloaded binaries.
- The installer requires no administrator privileges and uses the user's
  LocalAppData/Programs directory. It creates a Start Menu shortcut.
- The uninstaller is compiled from a package-file manifest. It removes only
  packaged files and directories that become empty, without recursively
  deleting user-added files in the install directory.
- SQLite, API keys, source media, downloaded videos and project files stored
  in `user_data_dir()` are **not deleted on uninstall**.
- Signing the publisher EXE with a trusted code-signing certificate is
  still an external release task; SHA-256 is an integrity check, not a
  replacement for signing or SmartScreen reputation.

## Production hardening delivered

| Area | Engineering change | Test |
| --- | --- | --- |
| Data durability | Explicit versioned `.dhyproj` project save/load, atomic writes and previous-version `.bak` | Unit tests for roundtrip, backup, corruption, limits |
| Editing correctness | Per-clip trim, color, masks, subtitle, CTA and voice applied in `Xuất toàn bộ` | Deterministic FFmpeg preset tests and packaged render smoke |
| Security | Strict project validation, no secrets, embedded media or automatic network calls in project files | Oversized/invalid data and token redaction tests |
| Output safety | Windows `os.rename` provides atomic **no-overwrite** semantics on NTFS/exFAT; POSIX uses no-replace `os.link` | Unit tests plus real Windows packaged render |
| Installer | One-file NSIS setup with explicit uninstall manifest and app-data separation | Clean install, `--self-test`, frozen GUI smoke, uninstall |
| Windows dependencies | FFmpeg/FFprobe binaries, Qt Multimedia, RapidOCR models, F2 worker | Bundled asset checks + offline inference/render/F2 doctor |
| Downloader | Public-link F2 one/post, yt-dlp conditional fallback, offline diagnostic | Mocked regressions; live platform test **not** available in CI |

## Remaining blocking acceptance tests for a stable *production* label

These need human-verified results before claiming full live production support:

1. **Real Windows UAT:** Start on Windows 10/11, open a clean project,
   import two authorized clips with different durations, video codecs and
   audio tracks; set different trim/masks/CTA; save, close, reopen and batch
   export. Compare **each** output against its clip-specific preset.
2. **Network UAT:** On the user's connection, try an authorized public direct
   Douyin video, a short share URL and public profile. Confirm F2/yt-dlp
   behavior, permissions, login/403/429/CAPTCHA states, retry and log hygiene.
   No downloader can guarantee access to private/blocked posts without
   authentication or platform permission. Do not evade these controls.
3. **Publishing UAT:** Validate Postiz credentials, OAuth grants and actual
   scheduling on each authorized platform account. Do **not** assume API
   integration equals successful remote publication.
4. **Code-signing:** Sign the installer/EXE with a real publisher cert and
   verify the signature, or distribute explicitly labeled unsigned builds.
5. **Licensing:** Audit the exact FFmpeg `-buildconf` and LGPL/GPL
   obligations, Qt/PySide6 redistribution, F2 transitive dependencies,
   model weights and any service provider agreements. Include corresponding
   notices and sources where required.
6. **Support/recovery:** Confirm low-disk, offline network, antivirus,
   cloud-synced folders, non-NTFS volumes, non-ASCII paths, interrupted
   renders and restore from `.dhyproj.bak`.

## Skill/repository choices

- **UI/UX Pro Max** and **Impeccable**: design/token, accessibility and error
  states, manually adapted to native Qt. No web runtime or GPL widgets bundled.
- **ffmpeg-skill** and **video-editing-skill**: deterministic media probing,
  rendering and verification, not a claim that a full CapCut multi-track
  timeline exists.
- **F2** (isolated worker) and **yt-dlp** (verified official release):
  public-source extraction with explicit failure states, no cookies provided.
- **NSIS**: zlib-compressed native Windows installer. NSIS's core uses
  zlib/libpng terms permitting commercial use. GPL video codecs and other
  bundled dependencies have separate obligations.

## Scope exclusions

This release does not implement a full nonlinear multi-track editing engine,
pixel-perfect CapCut parity, dynamic OCR tracking of moving subtitles,
unlimited Douyin download, bypasses of platform access controls, guaranteed
copyright freedom after crop/color changes, unattended social account OAuth,
or automatic financial transactions.

**Release policy:** CI green authorizes merging a reproducible release
candidate to main. It does not authorize labeling the build as perfect,
commercially compliant, signed, or universally functional. A stable GitHub
Release should follow the human UAT and legal/supply-chain checks above.
