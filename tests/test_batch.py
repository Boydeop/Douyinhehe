"""Regression tests for v2 explicit-rights queue, restarts and provenance."""

import csv
import json

import pytest

from douyinhehe.batch import BatchItem, enqueue_manifest, read_manifest, run_queue
from douyinhehe.core import Store


def make_manifest(tmp_path, *, authorized=True):
    clip = tmp_path / "item.mp4"
    clip.write_bytes(b"example movie placeholder")
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "original_url", "creator", "evidence",
                                                    "commercial", "derivative", "cta", "niche"])
        writer.writeheader()
        writer.writerow({"file": "item.mp4", "original_url": "https://www.douyin.com/video/123",
                         "creator": "Original Creator", "evidence": "licensed-contract-1",
                         "commercial": "true" if authorized else "false", "derivative": "true",
                         "niche": "Nhà bếp", "cta": "Link ở hồ sơ"})
    return manifest


def test_manifest_rights_and_dedup(tmp_path):
    manifest = make_manifest(tmp_path)
    items = read_manifest(manifest)
    assert len(items) == 1
    assert items[0].file == tmp_path / "item.mp4"
    store = Store(tmp_path / "storage.db")
    assert enqueue_manifest(store, manifest) == (1, 0)
    assert enqueue_manifest(store, manifest) == (0, 1)
    assert store.render_counts() == {"pending": 1}
    assert store.claim_next_render()["status"] == "pending"
    assert store.render_counts()["running"] == 1
    assert store.recover_interrupted_renders() == 1
    assert store.render_counts()["pending"] == 1


def test_missing_commercial_right_blocks_before_job_created(tmp_path):
    manifest = make_manifest(tmp_path, authorized=False)
    store = Store(tmp_path / "storage.db")
    with pytest.raises(ValueError, match="Dòng 1"):
        enqueue_manifest(store, manifest)
    assert store.render_counts() == {}


def test_queue_failed_then_retry_then_provenance(tmp_path, monkeypatch):
    import douyinhehe.batch as batch

    manifest = make_manifest(tmp_path)
    store = Store(tmp_path / "store.db")
    enqueue_manifest(store, manifest)
    out = tmp_path / "exports"

    def failure(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(batch, "render_video", failure)
    assert run_queue(store, out)["failed"] == 1
    assert store.render_counts() == {"failed": 1}
    assert store.retry_failed_renders() == 1

    def fake_render(src, dest, preset, progress=None):
        assert preset.creator == "Original Creator"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"synthetic rendered video")
        return dest

    monkeypatch.setattr(batch, "render_video", fake_render)
    monkeypatch.setattr(batch, "probe_video", lambda _: {"streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920}]})
    report = run_queue(store, out)
    assert report == {"done": 1, "failed": 0, "pending": 0}
    saved = list(out.glob("*.provenance.json"))
    assert len(saved) == 1
    evidence = json.loads(saved[0].read_text(encoding="utf-8"))
    assert evidence["source_url"] == "https://www.douyin.com/video/123"
    assert len(evidence["source_sha256"]) == 64
    assert evidence["creator"] == "Original Creator"
    assert store.render_counts() == {"done": 1}


def test_json_manifest_and_path_validation(tmp_path):
    clip = tmp_path / "video.mp4"
    clip.write_bytes(b"x")
    row = {"file": "video.mp4", "original_url": "https://www.douyin.com/video/1",
           "creator": "Uploader", "evidence": "License", "commercial": True, "derivative": True}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([row]), encoding="utf-8")
    assert read_manifest(manifest)[0].file == clip
    row["original_url"] = "http://evil.test/video/1"
    manifest.write_text(json.dumps([row]), encoding="utf-8")
    with pytest.raises(ValueError, match="Dòng 1"):
        read_manifest(manifest)
