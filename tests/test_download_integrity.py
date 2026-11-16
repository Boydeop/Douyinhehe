"""Downloader integrity: no success for corrupt or out-of-scope media."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from douyinhehe import downloader
from douyinhehe.core import LicenseGrant, Store


VIDEO = "https://www.douyin.com/video/7263619345228582203"


def test_verify_downloaded_files_rejects_corrupt_and_external(tmp_path, monkeypatch):
    root = tmp_path / "downloads"
    root.mkdir()
    good = root / "good.mp4"
    broken = root / "broken.mp4"
    external = tmp_path / "personal.mp4"
    for file in (good, broken, external):
        file.write_bytes(b"fixture" * 400)
    from douyinhehe import media
    def verify(path):
        if Path(path).name == "broken.mp4":
            raise ValueError("unplayable")
        return {"streams": [{"codec_type": "video"}]}
    monkeypatch.setattr(media, "probe_video", verify)
    found = downloader._verify_downloaded_media(
        [good, good, broken, external, root / "missing.mp4"], root)
    assert found == [good]


def test_f2_no_false_success_for_corrupt_mp4(tmp_path, monkeypatch):
    worker = tmp_path / "DouyinF2Worker.exe"
    worker.touch()
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: worker)
    def fake_run(*args, **kwargs):
        (tmp_path / "corrupt.mp4").write_bytes(b"bad" * 600)
        return SimpleNamespace(returncode=0, stdout="complete", stderr="")
    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    from douyinhehe import media
    monkeypatch.setattr(media, "probe_video", lambda path:
                        (_ for _ in ()).throw(ValueError("invalid MP4")))
    with pytest.raises(RuntimeError, match="không ghi video MP4 mới"):
        downloader._download_video_f2(VIDEO, tmp_path, None)


def test_ytdlp_does_not_accept_arbitrary_external_filepath(tmp_path, monkeypatch):
    outside = tmp_path / "external.mp4"
    outside.write_bytes(b"not our download" * 200)
    monkeypatch.setattr(downloader, "f2_worker_executable", lambda: None)
    monkeypatch.setattr(downloader, "downloader_status",
                        lambda: SimpleNamespace(ready=True, executable="yt-dlp.exe"))
    monkeypatch.setattr(downloader.subprocess, "run", lambda *a, **kw:
                        SimpleNamespace(returncode=0, stdout=str(outside) + "\n", stderr=""))
    dest = tmp_path / "downloads"
    with pytest.raises(RuntimeError, match="không tạo video mới"):
        downloader.download_authorized(VIDEO, dest, LicenseGrant(VIDEO, "", "", True, True),
                                       Store(tmp_path / "store.db"))
