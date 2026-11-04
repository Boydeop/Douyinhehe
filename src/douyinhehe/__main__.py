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


def packaged_render_smoke_test() -> int:
    """Render a real synthetic masked clip through the bundled FFmpeg/Pillow."""
    import subprocess
    import tempfile
    from pathlib import Path
    from .media import EditPreset, find_binary, render_video, probe_video
    from .studio_engine import MaskRegion

    with tempfile.TemporaryDirectory(prefix="douyinhehe-studio-smoke-") as root:
        folder = Path(root)
        source, output = folder / "original.mp4", folder / "edited.mp4"
        proc = subprocess.run(
            [find_binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-f", "lavfi", "-i", "color=c=blue:s=360x640:r=12:d=1",
             "-t", "1", "-c:v", "mpeg4", str(source)],
            capture_output=True, timeout=40, check=False,
        )
        if proc.returncode:
            raise RuntimeError("Không tạo được video kiểm thử FFmpeg.")
        preset = EditPreset(width=360, height=640, fit="pad", creator="",
                            original_url="local://test", cta="",
                            masks=(MaskRegion(.1, .7, .8, .12, "blur"),))
        render_video(source, output, preset)
        info = probe_video(output)
        if output.stat().st_size < 1024 or not any(
            s.get("codec_type") == "video" and s.get("width") == 360 and s.get("height") == 640
            for s in info.get("streams", ())
        ):
            raise RuntimeError("Render kiểm thử không cho ra video hợp lệ.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="DouyinhehePro")
    parser.add_argument("--self-test", action="store_true", help="Check packaged dependencies, then exit")
    parser.add_argument("--ui-smoke-test", action="store_true", help="Construct UI without opening a window")
    parser.add_argument("--ocr-self-test", action="store_true", help="Run bundled OCR offline inference test")
    parser.add_argument("--render-self-test", action="store_true", help="Render one synthetic clip using bundled FFmpeg")
    parser.add_argument("--version", action="store_true", help="Print application version")
    parser.add_argument("--doctor", action="store_true", help="Check downloader and local video tools")
    args = parser.parse_args()
    if args.version:
        from . import __version__
        print(__version__)
        return
    if args.self_test:
        raise SystemExit(self_test())
    if args.render_self_test:
        raise SystemExit(packaged_render_smoke_test())
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
        if window.down_mode.currentData() != "auto":
            raise RuntimeError("Downloader default must detect Douyin URL type")
        window.download_urls.setPlainText("https://www.douyin.com/user/MS4wLjABCD?vid=123")
        if "kênh" not in window.down_detect.text().lower():
            raise RuntimeError("Downloader UI did not recognize a profile URL")
        if not window.down_button.isEnabled():
            raise RuntimeError("Download action is not available")
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
                         ensure_ascii=True, indent=2))
        return
    from .app import launch

    launch()


if __name__ == "__main__":
    main()
