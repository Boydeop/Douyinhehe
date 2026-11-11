"""Production guarantees for local, versioned video projects."""
from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from douyinhehe.project_io import load_project, save_project, preset_from_state
from douyinhehe.studio_engine import MaskRegion


FORMATS = (
    ("9:16 low", 720, 1280), ("9:16 high", 1080, 1920),
    ("16:9", 1280, 720), ("1:1", 720, 720),
)


def state(**overrides):
    data = {
        "size": 0, "fit": 0, "brightness": 0.0, "contrast": 1.0,
        "saturation": 1.0, "trim_start": 0.0, "trim_end": 0.0,
        "mask_type": 0, "masks": (), "cta": "", "source_url": "",
        "subtitle": "", "voice": "",
    }
    data.update(overrides)
    return data


def test_project_roundtrip_per_clip_and_selected(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    path = tmp_path / "video.dhyproj"
    first = state(brightness=.2, trim_start=1.25, trim_end=3.0,
                  masks=(MaskRegion(.1, .7, .8, .1),))
    second = state(size=2, fit=2, brightness=-.15,
                   cta="Kênh được cấp quyền", mask_type=1)
    save_project(path, [(a, first), (b, second)], b)
    clips, selected = load_project(path)
    assert [clip for clip, _ in clips] == [a, b]
    assert selected == b
    assert clips[0][1]["masks"] == first["masks"]
    assert clips[0][1]["trim_start"] == 1.25
    assert clips[1][1]["brightness"] == pytest.approx(-.15)
    assert clips[1][1]["cta"] == "Kênh được cấp quyền"
    # Different settings actually generate distinct FFmpeg presets.
    p1 = preset_from_state(clips[0][1], FORMATS)
    p2 = preset_from_state(clips[1][1], FORMATS)
    assert (p1.width, p1.height, p1.trim_start) == (720, 1280, 1.25)
    assert (p2.width, p2.height, p2.fit) == (1280, 720, "blur")


def test_existing_project_gets_recovery_backup(tmp_path):
    clip = tmp_path / "a.mp4"
    clip.write_bytes(b"a")
    path = tmp_path / "project.dhyproj"
    save_project(path, [(clip, state(brightness=.1))], clip)
    original = path.read_bytes()
    save_project(path, [(clip, state(brightness=.3))], clip)
    assert path.with_suffix(".dhyproj.bak").read_bytes() == original
    assert load_project(path)[0][0][1]["brightness"] == pytest.approx(.3)


def test_project_scrubs_url_tokens_and_never_embeds_media(tmp_path):
    clip = tmp_path / "x.mp4"
    clip.write_bytes(b"unique-media-payload")
    secret = "secret-xyz-session"
    path = tmp_path / "project.dhyproj"
    save_project(path, [(clip, state(source_url=(
        "https://www.douyin.com/video/123?share_token=" + secret)))], clip)
    raw = path.read_text()
    assert secret not in raw
    assert "unique-media-payload" not in raw
    assert "123" in raw


@pytest.mark.parametrize("changed", [
    {"brightness": float("nan")}, {"brightness": float("inf")},
    {"trim_start": 4.0, "trim_end": 2.0},
    {"size": 99}, {"fit": -1}, {"mask_type": 5},
    {"masks": (MaskRegion(.9, .9, .5, .5),)},
])
def test_project_rejects_corrupt_or_unsafe_state(tmp_path, changed):
    clip = tmp_path / "a.mp4"
    clip.write_bytes(b"a")
    with pytest.raises(ValueError):
        save_project(tmp_path / "x.dhyproj", [(clip, state(**changed))], clip)


def test_project_rejects_new_schema_duplicate_and_oversized(tmp_path):
    a = tmp_path / "a.mp4"
    a.write_bytes(b"a")
    path = tmp_path / "x.dhyproj"
    with pytest.raises(ValueError):
        save_project(path, [(a, state()), (a, state())], a)
    path.write_text(json.dumps({"version": 999, "clips": [], "selected": None}))
    with pytest.raises(ValueError, match="Phiên bản"):
        load_project(path)
    path.write_bytes(b"X" * 2_000_001)
    with pytest.raises(ValueError, match="2 MB"):
        load_project(path)


def test_per_clip_mask_style_follows_saved_state():
    edit = state(mask_type=1, masks=(MaskRegion(.1, .6, .8, .12),))
    preset = preset_from_state(edit, FORMATS)
    assert preset.masks[0].mode == "solid"
