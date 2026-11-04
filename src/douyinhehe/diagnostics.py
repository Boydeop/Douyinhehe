"""User-approved yt-dlp executable updates and Vietnamese, offline-first diagnostics.

Never mutate the frozen Python executable. Fetch only yt-dlp's official, HTTPS
release assets; confirm SHA-256 before atomic installation in user app data.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .core import user_data_dir

RELEASE_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
RELEASE_HOSTS = {"api.github.com", "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
DOWNLOAD_CAP = 120 * 1024 * 1024


@dataclass(frozen=True)
class DownloaderStatus:
    ready: bool
    version: str
    origin: str
    diagnostic: str
    executable: str = ""


def external_ytdlp() -> Path | None:
    """Only a previously verified, locally installed standalone downloader."""
    if sys.platform != "win32":
        return None
    file = user_data_dir() / "tools" / "yt-dlp.exe"
    return file if file.is_file() else None


def downloader_status() -> DownloaderStatus:
    executable = external_ytdlp()
    if executable:
        try:
            result = subprocess.run([str(executable), "--version"], capture_output=True,
                                    text=True, check=False, timeout=12)
            version = result.stdout.strip()
            if result.returncode == 0 and re.fullmatch(r"\d{4}\.\d{2}\.\d{2}(?:\.\d+)?", version):
                return DownloaderStatus(True, version, "yt-dlp.exe cập nhật riêng",
                                        "Sẵn sàng. Việc tải còn tùy quyền truy cập của Douyin.", str(executable))
        except (OSError, subprocess.TimeoutExpired):
            pass
        return DownloaderStatus(False, "", "yt-dlp.exe cập nhật riêng",
                                "File yt-dlp đã tải không chạy được. Hãy cài lại từ nguồn chính thức.", str(executable))
    try:
        version = importlib.metadata.version("yt-dlp")
        import yt_dlp  # noqa: F401
    except (ImportError, importlib.metadata.PackageNotFoundError):
        return DownloaderStatus(False, "", "chưa cài", "Không có yt-dlp. Có thể dùng bản cập nhật chính thức trên Windows.")
    return DownloaderStatus(True, version, "Python package đi kèm", "yt-dlp đã sẵn sàng (không đảm bảo mọi URL tải được).")


def diagnose_failure(error: BaseException | str) -> str:
    raw = str(error).lower()
    if "unsupported url" in raw or "no suitable extractor" in raw:
        return "Liên kết chưa được yt-dlp hỗ trợ. Kiểm tra URL Douyin và phiên bản yt-dlp."
    if "403" in raw or "forbidden" in raw:
        return "Douyin từ chối truy cập (403). Kiểm tra quyền tải, không thử vượt giới hạn truy cập."
    if "429" in raw or "rate limit" in raw or "too many requests" in raw:
        return "Douyin đang giới hạn yêu cầu (429). Dừng tải, thử lại sau theo chính sách nền tảng."
    if "captcha" in raw or "login" in raw or "sign in" in raw:
        return "Douyin yêu cầu xác minh hoặc đăng nhập. Ứng dụng không vượt CAPTCHA hay xác minh."
    if "timed out" in raw or "timeout" in raw:
        return "Kết nối hết thời gian chờ. Hãy kiểm tra mạng và thử lại."
    if "certificate" in raw or "ssl" in raw:
        return "Lỗi chứng chỉ HTTPS. Kiểm tra ngày giờ hệ thống và kết nối mạng."
    return "Không tải được video. Kiểm tra giấy phép, URL và xem nhật ký đã che thông tin nhạy cảm."


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _assert_trusted_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _assert_trusted_https(url: str) -> None:
    u = urlsplit(url)
    if u.scheme != "https" or u.hostname not in RELEASE_HOSTS or u.username or u.password or u.port:
        raise ValueError("Nguồn cập nhật không thuộc GitHub HTTPS chính thức.")


def _open(url: str):
    _assert_trusted_https(url)
    request = urllib.request.Request(url, headers={"User-Agent": "Douyinhehe-DownloaderUpdate/2.1", "Accept": "application/vnd.github+json"})
    return urllib.request.build_opener(_CheckedRedirect()).open(request, timeout=30)


def _read_bounded(url: str, limit: int) -> bytes:
    with _open(url) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Tệp cập nhật vượt dung lượng an toàn.")
    return data


def update_ytdlp(*, confirmed: bool = False) -> DownloaderStatus:
    """Explicitly invoked update. Verify release asset digest AND SHA2-256SUMS."""
    if not confirmed:
        raise PermissionError("Cần người dùng xác nhận trước khi tải/cập nhật yt-dlp.")
    if sys.platform != "win32":
        raise OSError("Cập nhật yt-dlp.exe chỉ hỗ trợ ứng dụng Windows.")
    release = json.loads(_read_bounded(RELEASE_API, 1024 * 1024))
    tag = release.get("tag_name", "")
    if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}(?:\.\d+)?", tag):
        raise ValueError("Phiên bản yt-dlp từ GitHub không hợp lệ.")
    assets = {a.get("name"): a for a in release.get("assets", [])}
    exe = assets.get("yt-dlp.exe")
    sums = assets.get("SHA2-256SUMS")
    if not exe or not sums:
        raise RuntimeError("GitHub Release không có đủ file yt-dlp.exe và SHA2-256SUMS.")
    digest = str(exe.get("digest") or "").lower()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise RuntimeError("GitHub không cung cấp SHA-256 của file phát hành; từ chối cập nhật.")
    base = f"https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/"
    if exe.get("browser_download_url") != base + "yt-dlp.exe" or sums.get("browser_download_url") != base + "SHA2-256SUMS":
        raise ValueError("Đường dẫn tài sản không trùng GitHub Release chính thức.")
    checksum_text = _read_bounded(base + "SHA2-256SUMS", 128 * 1024).decode("utf-8")
    expected = None
    for line in checksum_text.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?yt-dlp\.exe", line.strip())
        if match:
            expected = match.group(1).lower()
            break
    if not expected or digest != "sha256:" + expected:
        raise ValueError("Checksum trong release và GitHub API không khớp.")
    folder = user_data_dir() / "tools"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / "yt-dlp.exe"
    with tempfile.TemporaryDirectory(prefix="yt-dlp-update-", dir=str(folder)) as temp:
        staged = Path(temp) / "yt-dlp.exe"
        content = _read_bounded(base + "yt-dlp.exe", DOWNLOAD_CAP)
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Checksum file yt-dlp.exe không đúng. Không cài đặt.")
        staged.write_bytes(content)
        checked = subprocess.run([str(staged), "--version"], capture_output=True,
                                 text=True, timeout=25, check=False)
        if checked.returncode or checked.stdout.strip() != tag:
            raise RuntimeError("yt-dlp.exe vừa tải không vượt qua kiểm tra phiên bản.")
        # Atomic replace: leave the existing verified file intact until the new one is ready.
        os.replace(staged, dest)
    return downloader_status()
