"""Authorized public Douyin download adapter; do not bypass login, captcha or access checks."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from typing import Callable

from .core import LicenseGrant, Store
from .diagnostics import diagnose_failure, downloader_status

_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_ALLOWED = ("douyin.com", "iesdouyin.com")


def is_channel_url(url: str) -> bool:
    """Channel mode must be explicitly scoped to a Douyin user page."""
    try:
        if parse_douyin_urls(url) != [url]:
            return False
        return bool(re.fullmatch(r"/user/[^/]+/?", urlsplit(url).path))
    except ValueError:
        return False



def parse_douyin_urls(text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in _URL.findall(text):
        url = match.rstrip(".,);，。！？!?]")
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        if (parts.scheme != "https" or parts.username or parts.password or parts.port or
            not any(host == allowed or host.endswith("." + allowed) for allowed in _ALLOWED)):
            raise ValueError(f"URL không thuộc Douyin HTTPS: {url}")
        if url not in seen:
            seen.add(url)
            result.append(url)
    if not result:
        raise ValueError("Không tìm thấy URL Douyin HTTPS hợp lệ.")
    return result


def selected_video_from_profile(url: str) -> str | None:
    """Convert the explicit ?vid= selection into a direct video URL."""
    if not is_channel_url(url):
        return None
    matches = parse_qs(urlsplit(url).query).get("vid", [])
    if len(matches) != 1 or not re.fullmatch(r"[0-9]{12,24}", matches[0]):
        return None
    return "https://www.douyin.com/video/" + matches[0]


def classify_douyin_url(url: str) -> str:
    """Profile URL must not silently fall through to yt-dlp's unsupported generic extractor."""
    if parse_douyin_urls(url) != [url]:
        raise ValueError("Chỉ chọn một URL Douyin hợp lệ.")
    return "channel" if is_channel_url(url) else "batch"


def f2_worker_executable() -> Path | None:
    from .core import user_data_dir
    name = "DouyinF2Worker.exe" if sys.platform == "win32" else "DouyinF2Worker"
    for folder in (Path(sys.executable).resolve().parent / "bin", user_data_dir() / "tools"):
        path = folder / name
        if path.is_file():
            return path
    return None


def _download_channel_f2(url: str, folder: Path, max_items: int,
                         progress: Callable[[str], None] | None) -> list[Path]:
    worker = f2_worker_executable()
    if worker is None:
        raise RuntimeError("Thiếu engine F2 để tải nguyên kênh. Hãy sử dụng bản Windows có DouyinF2Worker.exe trong thư mục bin.")
    previous = {p.resolve(): (p.stat().st_size, p.stat().st_mtime_ns)
                for p in folder.rglob("*.mp4") if p.is_file()}
    args = [str(worker), "--mode", "post", "--url", url,
            "--path", str(folder.resolve()), "--max-counts", str(max_items)]
    if progress:
        progress("Phát hiện URL hồ sơ. Đang tải bằng engine F2 chuyên dụng...")
    try:
        result = subprocess.run(args, cwd=str(folder), capture_output=True, text=True,
                                errors="replace", timeout=3600, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("F2 không phản hồi trong 60 phút. Kiểm tra kết nối Douyin.") from exc
    if result.returncode != 0:
        from .logging_support import redact
        message = redact((result.stderr or result.stdout)[-700:])
        raise RuntimeError("F2 không tải được trang này. " + diagnose_failure(message) + " " + message)
    downloaded = []
    for file in folder.rglob("*.mp4"):
        if not file.is_file():
            continue
        stat = file.stat()
        if previous.get(file.resolve()) != (stat.st_size, stat.st_mtime_ns):
            downloaded.append(file)
    if progress:
        progress(f"F2 hoàn tất: {len(downloaded)} file video mới.")
    return sorted(downloaded)


def download_authorized(url: str, folder: Path, grant: LicenseGrant, store: Store,
                        max_items: int = 30, progress: Callable[[str], None] | None = None,
                        *, mode: str = "auto") -> list[Path]:
    """Download only with a recorded grant. Network access is performed by yt-dlp.

    Douyin frequently changes access controls. Report failures; no captcha or anti-bot bypass.
    """
    if url not in parse_douyin_urls(url):
        raise ValueError("URL không hợp lệ.")
    grant.validate()
    if grant.original_url != url:
        raise ValueError("Giấy phép phải gắn với đúng URL tải xuống.")
    if mode not in {"auto", "batch", "channel"}:
        raise ValueError("Chế độ tải không hợp lệ.")
    if mode == "auto":
        mode = classify_douyin_url(url)
    if mode == "batch" and is_channel_url(url):
        raise ValueError("Đây là URL hồ sơ Douyin. Chọn Tự nhận diện hoặc Nguyên kênh để dùng F2.")
    if mode == "channel" and not is_channel_url(url):
        raise ValueError("Nguyên kênh yêu cầu URL có dạng douyin.com/user/...")
    if not 0 <= max_items <= 5000 or (mode == "batch" and max_items == 0):
        raise ValueError("Giới hạn tải phải từ 1 đến 5000, hoặc 0 cho toàn kênh.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    store.save_source(grant)
    if mode == "channel":
        result = _download_channel_f2(url, folder, max_items, progress)
        for file in result:
            store.update_download(url, file)
        return result

    downloader = downloader_status()
    if not downloader.ready:
        raise RuntimeError(downloader.diagnostic)
    outputs: list[Path] = []

    def hook(info: dict) -> None:
        if info.get("status") == "finished":
            file = Path(info.get("filename", ""))
            if file.is_file() and file not in outputs:
                outputs.append(file)
            if progress:
                progress(f"Đã tải: {file.name}")

    options = {
        "outtmpl": str(folder / "%(id)s.%(ext)s"),
        "download_archive": str(folder / ".douyinhehe-downloaded.txt"),
        "playlistend": max_items if max_items else None,
        "noplaylist": mode != "channel",
        "ignoreerrors": False,
        "retries": 2,
        "fragment_retries": 2,
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }
    if progress:
        progress(f"Bắt đầu tải {url} (tối đa {max_items} video)")
    try:
        if downloader.executable:
            args = [downloader.executable, "--ignore-config", "--no-progress", "--no-warnings",
                    "--no-overwrites", "--retries", "2", "--fragment-retries", "2",
                    "--download-archive", str(folder / ".douyinhehe-downloaded.txt"),
                    "--yes-playlist" if mode == "channel" else "--no-playlist",
                    "--paths", str(folder), "--output", "%(id)s.%(ext)s",
                    "--print", "after_move:filepath"]
            if max_items:
                args += ["--playlist-end", str(max_items)]
            args.append(url)
            result = subprocess.run(args, capture_output=True, text=True, timeout=3600, check=False)
            if result.returncode:
                raise RuntimeError(result.stderr[-1500:] or result.stdout[-1500:])
            outputs = [Path(x.strip()) for x in result.stdout.splitlines()
                       if Path(x.strip()).is_file() and Path(x.strip()) not in outputs]
        else:
            import yt_dlp
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
    except Exception as exc:
        raise RuntimeError(diagnose_failure(exc)) from exc
    for file in outputs:
        store.update_download(url, file)
    return outputs
