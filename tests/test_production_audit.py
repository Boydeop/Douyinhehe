"""Production audit regressions: rights, privacy, and FFmpeg audio duration."""
import json
import shutil
import subprocess
from datetime import date, timedelta

import pytest

from douyinhehe.batch import create_local_manifest, enqueue_manifest, read_manifest, run_queue
from douyinhehe.core import Store
from douyinhehe.media import EditPreset, build_edit_command, probe_video, render_video


def _future(days):
    return (date.today() + timedelta(days=days)).isoformat()


def test_manifest_expiry_survives_queue_and_is_checked_at_render(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"owned test clip")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{
        "file": "clip.mp4", "original_url": "local://owned",
        "commercial": True, "derivative": True, "expires_on": _future(2),
    }]), encoding="utf-8")
    item = read_manifest(manifest)[0]
    assert item.expires_on == _future(2)
    store = Store(tmp_path / "jobs.sqlite")
    assert enqueue_manifest(store, manifest) == (1, 0)
    record = store.render_jobs()[0]
    payload = json.loads(record["payload"])
    assert payload["expires_on"] == _future(2)
    payload["expires_on"] = _future(-1)
    with store._connect() as con:
        con.execute("UPDATE render_jobs SET payload=? WHERE id=?", (json.dumps(payload), record["id"]))
    import douyinhehe.batch as batch
    monkeypatch.setattr(batch, "render_video", lambda *args, **kw:
                        pytest.fail("Expired license must fail before FFmpeg"))
    result = run_queue(store, tmp_path / "exports")
    assert result["failed"] == 1
    assert "hết hạn" in store.render_jobs()[0]["error"]


def test_local_import_enforces_expiry(tmp_path):
    clips = tmp_path / "clips"
    clips.mkdir()
    (clips / "owned.mp4").write_bytes(b"self shot")
    manifest = tmp_path / "manifest.json"
    with pytest.raises(PermissionError, match="hết hạn"):
        create_local_manifest(clips, manifest, rights_confirmed=True, expires_on=_future(-1))
    assert not manifest.exists()
    create_local_manifest(clips, manifest, rights_confirmed=True, expires_on=_future(10))
    assert read_manifest(manifest)[0].expires_on == _future(10)


def test_provenance_drops_query_credentials(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    original = "https://www.douyin.com/video/123?access_token=supersecret987654"
    manifest = tmp_path / "input.json"
    manifest.write_text(json.dumps([{
        "file": str(clip), "original_url": original,
        "commercial": True, "derivative": True,
    }]), encoding="utf-8")
    store = Store(tmp_path / "db.sqlite")
    enqueue_manifest(store, manifest)
    import douyinhehe.batch as batch
    monkeypatch.setattr(batch, "render_video", lambda source, target, preset, progress:
                        target.write_bytes(b"valid fixture"))
    monkeypatch.setattr(batch, "probe_video", lambda path: {"streams": [{"codec_type": "video"}]})
    result = run_queue(store, tmp_path / "exports")
    assert result["done"] == 1
    sidecar = next((tmp_path / "exports").glob("*.provenance.json")).read_text(encoding="utf-8")
    assert "supersecret" not in sidecar
    assert "https://www.douyin.com/video/123" in sidecar


def test_edit_command_pads_short_audio():
    cmd = build_edit_command(
        __import__("pathlib").Path("source.mp4"), __import__("pathlib").Path("out.mp4"),
        __import__("pathlib").Path("overlay.png"), EditPreset(narration=None))
    assert cmd[cmd.index("-af") + 1] == "apad"
    assert "-shortest" in cmd


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg binaries unavailable")
def test_short_narration_does_not_cut_video(tmp_path):
    source, voice, dest = (tmp_path / n for n in ("src.mp4", "voice.wav", "out.mp4"))
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=blue:s=256x256:r=12:d=2", "-c:v", "mpeg4",
                    str(source)], check=True, timeout=30)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=0.4", str(voice)],
                   check=True, timeout=30)
    render_video(source, dest, EditPreset(width=256, height=256, narration=voice))
    assert float(probe_video(dest)["format"]["duration"]) >= 1.8
