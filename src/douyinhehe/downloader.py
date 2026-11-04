"""Authorized public Douyin download adapter; do not bypass login, captcha or access checks."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from typing import Callable

from .core import LicenseGrant, Store
from .diagnostics import diagnose_failure, downloader_status

_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_ALLOWED = ("douyin.com", "iesdouyin.com")


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


def download_authorized(url: str, folder: Path, grant: LicenseGrant, store: Store,
                        max_items: int = 30, progress: Callable[[str], None] | None = None) -> list[Path]:
    """Download only with a recorded grant. Network access is performed by yt-dlp.

    Douyin frequently changes access controls. Report failures; no captcha or anti-bot bypass.
    """
    if url not in parse_douyin_urls(url):
        raise ValueError("URL không hợp lệ.")
    grant.validate()
    if grant.original_url != url:
        raise ValueError("Giấy phép phải gắn với đúng URL tải xuống.")
    if not 1 <= max_items <= 200:
        raise ValueError("Số lượng video phải từ 1 đến 200.")
    downloader = downloader_status()
    if not downloader.ready:
        raise RuntimeError(downloader.diagnostic)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    store.save_source(grant)
    outputs: list[Path] = []

    def hook(info: dict) -> None:
        if info.get("status") == "finished":
            file = Path(info.get("filename", ""))
            if file.is_file() and file not in outputs:
                outputs.append(file)
            if progress:
                progress(f"Đã tải: {file.name}")

    options = {
        "outtmpl": str(folder / "%(uploader_id|unknown)s_%(id)s.%(ext)s"),
        "playlistend": max_items,
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
                    "--retries", "2", "--fragment-retries", "2",
                    "--playlist-end", str(max_items),
                    "--paths", str(folder), "--output", "%(uploader_id|unknown)s_%(id)s.%(ext)s",
                    "--print", "after_move:filepath", url]
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
