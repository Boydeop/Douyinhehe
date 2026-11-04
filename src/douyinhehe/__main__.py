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
    import importlib.util
    if importlib.util.find_spec("PySide6") is not None:
        from .app import MainWindow
        assert callable(MainWindow)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="DouyinhehePro")
    parser.add_argument("--self-test", action="store_true", help="Check packaged dependencies, then exit")
    parser.add_argument("--ui-smoke-test", action="store_true", help="Construct UI without opening a window")
    parser.add_argument("--ocr-self-test", action="store_true", help="Run bundled OCR offline inference test")
    parser.add_argument("--version", action="store_true", help="Print application version")
    parser.add_argument("--doctor", action="store_true", help="Check downloader and local video tools")
    args = parser.parse_args()
    if args.version:
        from . import __version__
        print(__version__)
        return
    if args.self_test:
        raise SystemExit(self_test())
    if args.ocr_self_test:
        from .ocr_support import offline_ocr_smoke_test
        import json
        print(json.dumps(offline_ocr_smoke_test(), ensure_ascii=False))
        return
    if args.ui_smoke_test:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from .app import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        if window.pages.count() != 9 or window.nav.count() != 9:
            raise RuntimeError("UI navigation missing feature pages")
        window.close()
        return
    if args.doctor:
        from .diagnostics import downloader_status
        from .media import find_binary
        import json
        from .ocr_support import check_ocr_assets
        print(json.dumps({"yt_dlp": downloader_status().__dict__,
                          "ocr": check_ocr_assets().__dict__,
                          "ffmpeg": find_binary("ffmpeg"), "ffprobe": find_binary("ffprobe")},
                         ensure_ascii=False, indent=2))
        return
    from .app import launch

    launch()


if __name__ == "__main__":
    main()
