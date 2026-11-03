import sys
from pathlib import Path

from douyinhehe.media import find_binary


def test_frozen_binary_prefers_portable_bin(tmp_path, monkeypatch):
    fake_exe = tmp_path / "DouyinhehePro.exe"
    fake_exe.touch()
    bundled = tmp_path / "bin"
    bundled.mkdir()
    ff = bundled / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe")
    ff.touch()
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert Path(find_binary("ffprobe")) == ff


def test_entrypoint_core_selftest(monkeypatch, tmp_path):
    import douyinhehe.__main__ as entry
    import douyinhehe.media as media
    monkeypatch.setattr(media, "find_binary", lambda _: "ffprobe")
    class Result:
        returncode = 0
    monkeypatch.setattr(entry.subprocess, "run", lambda *a, **k: Result())
    monkeypatch.setenv("DOUYINHEHE_HOME", str(tmp_path))
    assert entry.self_test() == 0
    assert (tmp_path / "Douyinhehe" / "diagnostics.sqlite3").is_file()
