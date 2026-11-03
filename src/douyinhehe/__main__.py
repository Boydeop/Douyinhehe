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
    args = parser.parse_args()
    if args.self_test:
        raise SystemExit(self_test())
    from .app import launch

    launch()


if __name__ == "__main__":
    main()
