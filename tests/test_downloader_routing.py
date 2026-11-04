"""Downloader routing regression: profile URLs should NEVER be sent to yt-dlp."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from douyinhehe import downloader
from douyinhehe.core import LicenseGrant, Store


PROFILE = ("https://www.douyin.com/user/MS4wLjABAAAANkJHCqd5rcBVcjF2mpD6cOMq2bxm"
           "l_IQHY516NMaKE?vid=7263619345228582203")
VIDEO = "https://www.douyin.com/video/7263619345228582203"


def test_auto_route_profile_video_and_query():
    assert downloader.classify_douyin_url(PROFILE) == "channel"
    assert downloader.classify_douyin_url(VIDEO) == "batch"
    assert downloader.is_channel_url(PROFILE)


def test_selected_video_from_profile():
    assert downloader.selected_video_from_profile(PROFILE) == (
        "https://www.douyin.com/video/7263619345228582203")
    assert downloader.selected_video_from_profile(VIDEO) is None
    assert downloader.selected_video_from_profile(
        "https://www.douyin.com/user/ABC?vid=letters") is None


def test_profile_requires_f2_not_ytdlp(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: None)
    monkeypatch.setattr(downloader, "downloader_status",
                        lambda: (_ for _ in ()).throw(AssertionError("yt-dlp must not be used")))
    store = Store(tmp_path / "db.sqlite")
    grant = LicenseGrant(PROFILE, "", "", True, True)
    with pytest.raises(RuntimeError, match="F2"):
        downloader.download_authorized(PROFILE, tmp_path / "videos", grant, store, 30, mode="auto")


def test_profile_manual_video_mode_rejected(tmp_path):
    with pytest.raises(ValueError, match="URL hồ sơ"):
        downloader.download_authorized(
            PROFILE, tmp_path, LicenseGrant(PROFILE, "", "", True, True),
            Store(tmp_path / "db.sqlite"), 30, mode="batch")


def test_f2_worker_outputs_are_discovered(tmp_path, monkeypatch):
    root = tmp_path / "videos"
    root.mkdir()
    fake = tmp_path / "DouyinF2Worker.exe"
    fake.write_bytes(b"worker fixture")
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: fake)
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        subfolder = root / "post" / "creator"
        subfolder.mkdir(parents=True)
        (subfolder / "clip.mp4").write_bytes(b"new video fixture")
        return SimpleNamespace(returncode=0, stdout="done", stderr="")
    monkeypatch.setattr(downloader.subprocess, "run", run)
    output = downloader._download_channel_f2(PROFILE, root, 17, None)
    assert len(output) == 1
    assert output[0].name == "clip.mp4"
    assert "--max-counts" in calls[0]
    assert calls[0][-1] == "17"


def test_f2_failures_are_not_silent(tmp_path, monkeypatch):
    f = tmp_path / "worker"
    f.touch()
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: f)
    monkeypatch.setattr(downloader.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=1, stderr="403 Forbidden", stdout=""))
    with pytest.raises(RuntimeError, match="403"):
        downloader._download_channel_f2(PROFILE, tmp_path, 20, None)
