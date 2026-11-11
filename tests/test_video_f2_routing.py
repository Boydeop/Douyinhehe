"""Regressions for the two URL shapes that failed in the user's v3.2 screenshots."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from douyinhehe import downloader
from douyinhehe.core import LicenseGrant, Store


VIDEO = "https://www.douyin.com/video/7263619345228582203"
SHORT = "https://v.douyin.com/BNgn4jhGBXk/"


@pytest.mark.parametrize("url", [VIDEO, SHORT])
def test_single_video_and_short_link_use_f2_not_ytdlp(tmp_path, monkeypatch, url):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"dummy")
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: tmp_path / "worker.exe")
    monkeypatch.setattr(downloader, "_download_video_f2", lambda *args: [video])
    monkeypatch.setattr(downloader, "downloader_status",
                        lambda: (_ for _ in ()).throw(AssertionError("Wrong engine: yt-dlp")))
    store = Store(tmp_path / "data.sqlite")
    got = downloader.download_authorized(
        url, tmp_path / "media", LicenseGrant(url, "", "", True, True),
        store, 15, mode="auto"
    )
    assert got == [video]


def test_worker_allows_official_short_and_video_urls():
    from scripts.f2_worker import validate_source_url
    validate_source_url(SHORT, "one")
    validate_source_url(VIDEO, "one")
    validate_source_url("https://www.douyin.com/user/MS4w", "post")
    with pytest.raises(ValueError):
        validate_source_url("https://douyin.com.evil.example/a", "one")
    with pytest.raises(ValueError):
        validate_source_url(SHORT, "post")


def test_f2_single_video_mode_does_not_hide_no_file(tmp_path, monkeypatch):
    worker = tmp_path / "DouyinF2Worker.exe"
    worker.touch()
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: worker)
    monkeypatch.setattr(
        downloader.subprocess, "run",
        lambda cmd, **kwargs: SimpleNamespace(returncode=0, stderr="", stdout="finish"),
    )
    with pytest.raises(RuntimeError, match="không ghi video MP4 mới"):
        downloader._download_video_f2(SHORT, tmp_path, None)


def test_f2_access_denied_does_not_fallback_to_ytdlp(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: tmp_path / "worker.exe")
    def deny(*args):
        raise RuntimeError("F2 (one): HTTP 403 Forbidden")
    monkeypatch.setattr(downloader, "_download_video_f2", deny)
    monkeypatch.setattr(downloader, "downloader_status",
                        lambda: (_ for _ in ()).throw(AssertionError("403 must not fallback")))
    with pytest.raises(RuntimeError, match="403"):
        downloader.download_authorized(
            VIDEO, tmp_path / "media", LicenseGrant(VIDEO, "", "", True, True),
            Store(tmp_path / "data.sqlite"), mode="auto"
        )


def test_f2_unsupported_url_tries_ytdlp(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: tmp_path / "worker.exe")
    def unsupported(*args):
        raise RuntimeError("F2: unsupported URL")
    monkeypatch.setattr(downloader, "_download_video_f2", unsupported)
    monkeypatch.setattr(downloader, "downloader_status",
                        lambda: SimpleNamespace(ready=True, executable="yt-dlp.exe"))
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"sample")
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout=str(media) + "\n", stderr="")
    monkeypatch.setattr(downloader.subprocess, "run", run)
    downloaded = downloader.download_authorized(
        VIDEO, tmp_path / "media", LicenseGrant(VIDEO, "", "", True, True),
        Store(tmp_path / "data.sqlite"), mode="auto")
    assert downloaded == [media]
    assert calls and calls[0][0] == "yt-dlp.exe"


def test_ytdlp_exit_zero_without_video_is_not_success(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: None)
    monkeypatch.setattr(downloader, "downloader_status",
                        lambda: SimpleNamespace(ready=True, executable="yt-dlp.exe"))
    monkeypatch.setattr(
        downloader.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    with pytest.raises(RuntimeError, match="không tạo video mới"):
        downloader.download_authorized(
            VIDEO, tmp_path / "downloads",
            LicenseGrant(VIDEO, "", "", True, True), Store(tmp_path / "store.sqlite"),
        )


def test_f2_zero_byte_mp4_is_not_success(tmp_path, monkeypatch):
    worker = tmp_path / "DouyinF2Worker.exe"
    worker.touch()
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: worker)

    def fake_run(cmd, **kwargs):
        (tmp_path / "broken.mp4").write_bytes(b"")
        return SimpleNamespace(returncode=0, stdout="done", stderr="")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="không ghi video MP4 mới"):
        downloader._download_video_f2(VIDEO, tmp_path, None)
