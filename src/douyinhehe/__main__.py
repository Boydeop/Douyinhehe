"""Desktop entry point and headless checks for the frozen Windows release."""

from __future__ import annotations

import argparse
import subprocess


def self_test() -> int:
    """Verify frozen app imports, bundled tools, and a writable local Store."""
    from .core import Store, user_data_dir
    from .media import find_binary

    for name in ("ffmpeg", "ffprobe"):
        exe = find_binary(name)
        proc = subprocess.run([exe, "-version"], capture_output=True, timeout=15, check=False)
        if proc.returncode:
            raise RuntimeError(f"{name} failed in the portable application")
    Store(user_data_dir() / "diagnostics.sqlite3")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="DouyinhehePro")
    parser.add_argument("--self-test", action="store_true", help="Check packaged dependencies, then exit")
    parser.add_argument("--version", action="store_true", help="Print application version")
    parser.add_argument("--doctor", action="store_true", help="Check downloader and local video tools")
    args = parser.parse_args()
    if args.version:
        from . import __version__
        print(__version__)
        return
    if args.self_test:
        raise SystemExit(self_test())
    if args.doctor:
        from .diagnostics import downloader_status
        from .media import find_binary
        import json
        print(json.dumps({"yt_dlp": downloader_status().__dict__,
                          "ffmpeg": find_binary("ffmpeg"), "ffprobe": find_binary("ffprobe")},
                         ensure_ascii=False, indent=2))
        return
    from .app import launch

    launch()


if __name__ == "__main__":
    main()
