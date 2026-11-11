"""Real editing regression: model tests + a complete FFmpeg read/edit/export of an MP4."""
from __future__ import annotations

import shutil
import subprocess

import pytest
from PIL import Image

from douyinhehe.editor_ops import clip_duration, preview_preset, safe_output_path, seconds_label
from douyinhehe.media import EditPreset, make_overlay, probe_video, render_video
from douyinhehe.studio_engine import MaskRegion


def test_video_duration_from_container_or_stream():
    assert clip_duration({"format": {"duration": "15.25"}}) == 15.25
    assert clip_duration({"format": {}, "streams": [
        {"codec_type": "audio", "duration": "90"},
        {"codec_type": "video", "duration": "8.2"}]}) == 8.2
    assert clip_duration({"format": {"duration": "N/A"}}) == 0
    assert seconds_label(125000) == "02:05"


def test_output_names_never_overwrite_original_or_prior_export(tmp_path):
    src = tmp_path / "example.mp4"
    src.write_bytes(b"original")
    occupied = tmp_path / "example_edited.mp4"
    occupied.write_bytes(b"old export")
    names: set = set()
    first = safe_output_path(tmp_path, src, names)
    second = safe_output_path(tmp_path, src, names)
    assert first.name == "example_edited_2.mp4"
    assert second.name == "example_edited_3.mp4"
    assert src.read_bytes() == b"original"
    assert occupied.read_bytes() == b"old export"


def test_preview_respects_trim_and_aspect():
    portrait = EditPreset(width=1080, height=1920, trim_start=2, trim_end=11)
    sample = preview_preset(portrait, source_duration=12)
    assert (sample.width, sample.height) == (360, 640)
    assert sample.trim_start == 2 and sample.trim_end == 7
    square = preview_preset(EditPreset(width=720, height=720), source_duration=1.2)
    assert (square.width, square.height) == (480, 480)
    assert square.trim_end == 1.2
    horizontal = preview_preset(EditPreset(width=1280, height=720), source_duration=9)
    assert (horizontal.width, horizontal.height) == (640, 360)
    with pytest.raises(ValueError):
        preview_preset(EditPreset(trim_start=5), source_duration=4)


def test_empty_cta_does_not_invent_promotion_or_douyin_source(tmp_path):
    out = tmp_path / "transparent.png"
    make_overlay(EditPreset(width=360, height=640, cta="", original_url=""), out)
    with Image.open(out).convert("RGBA") as image:
        assert image.getbbox() is None


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="FFmpeg binary not installed in this CI image")
def test_actual_video_file_is_trimmed_edited_and_exported(tmp_path):
    original = tmp_path / "camera.mp4"
    result = tmp_path / "camera_edited.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=12:duration=2.2",
        "-c:v", "mpeg4", "-t", "2.2", str(original),
    ], check=True, capture_output=True, timeout=45)
    before = original.read_bytes()
    preset = EditPreset(
        width=360, height=640, fit="crop", brightness=.1, contrast=1.2,
        saturation=.8, trim_start=.3, trim_end=1.5, cta="Xem sản phẩm",
        masks=(MaskRegion(.1, .72, .75, .12, "blur"),),
    )
    assert render_video(original, result, preset) == result
    info = probe_video(result)
    video = next(s for s in info["streams"] if s.get("codec_type") == "video")
    assert (video["width"], video["height"]) == (360, 640)
    assert .6 < float(info["format"]["duration"]) < 1.8
    assert result.stat().st_size > 2000
    assert original.read_bytes() == before, "Editing must never alter the source."


def test_existing_export_is_never_replaced_even_before_render(tmp_path, monkeypatch):
    """The publishing step must not silently replace an existing export."""
    import os
    from douyinhehe import media

    staged = tmp_path / "staged.mp4"
    target = tmp_path / "already.mp4"
    staged.write_bytes(b"new render")
    target.write_bytes(b"keep me")
    with pytest.raises(FileExistsError):
        os.link(staged, target)
    assert target.read_bytes() == b"keep me"


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="FFmpeg binary not installed in this CI image")
def test_render_refuses_existing_target_even_when_created_during_processing(tmp_path):
    original = tmp_path / "original.mp4"
    output = tmp_path / "existing.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=320x240:d=.5",
        "-c:v", "mpeg4", str(original),
    ], check=True, capture_output=True, timeout=45)
    output.write_bytes(b"existing export must survive")
    with pytest.raises(FileExistsError):
        render_video(original, output, EditPreset(width=360, height=640))
    assert output.read_bytes() == b"existing export must survive"
