# Third-party libraries and release notices

The Douyinhehe source code is MIT. That does **not** relicense bundled third-party components.

- [PySide6 / Qt](https://www.qt.io/licensing): commonly LGPL-3.0/GPL/commercial depending on modules. Distributors must comply with Qt license notices and relevant obligations, including dynamic linking and replacement rights as applicable.
- [FFmpeg](https://ffmpeg.org/legal.html): FFmpeg may be LGPL or GPL depending on build configuration and external codec libraries such as libx264. Review the exact binary distribution, include its applicable licenses and corresponding source/offer as required before distributing publicly.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp): Unlicense, with bundled component notices where applicable.
- [Pillow](https://github.com/python-pillow/Pillow): HPND, [httpx](https://github.com/encode/httpx): BSD-3-Clause, [google-genai](https://github.com/googleapis/python-genai): Apache-2.0.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): MIT; model weights can have **separate licenses**, check model cards prior to commercial use.
- [keyring](https://github.com/jaraco/keyring): MIT. Other transitive licenses apply.
- Postiz is a **separate connected service** and its self-hosted source is AGPL-3.0. This project does not bundle or redistribute Postiz source code.

GitHub Actions packages FFmpeg from Chocolatey. This pipeline is a test-build foundation, not proof that all licensing conditions for commercial distribution have been met. Before public releases, audit installed packages and provide matching binary licenses/source compliance information.

## Pinned Windows bundle (2.1.0)
- Chocolatey package `ffmpeg` **9.0.2** (`choco install ffmpeg --version=9.0.2`), with actual
  build options recorded in `FFMPEG_BUILDINFO.txt` inside the Windows ZIP.
- FFmpeg 9.0.2 source tarball: <https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz>.
- This may include GPL components such as x264. For commercial/public distribution,
  supply the full corresponding source and third-party license notices required by
  the actual binary build, or replace it with a properly licensed build. Do not
  assume that a link to core FFmpeg sources alone satisfies all GPL obligations.
- yt-dlp.exe optional updater verifies both the release asset SHA-256 and
  `SHA2-256SUMS`, and keeps it outside the frozen application.
