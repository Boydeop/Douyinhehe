from pathlib import Path

import pytest
from PIL import Image

from douyinhehe.media import EditPreset, build_edit_command, make_overlay, probe_video, render_video


def test_overlay_and_command(tmp_path):
    preset = EditPreset(fit="blur", creator="Tác giả A", original_url="https://douyin.com/video/1", cta="Xem sản phẩm ở trang kênh")
    overlay = tmp_path / "ov.png"
    make_overlay(preset, overlay)
    assert Image.open(overlay).size == (1080, 1920)
    cmd = build_edit_command(Path("input.mp4"), Path("output.mp4"), overlay, preset)
    assert "-filter_complex" in cmd
    assert "boxblur" in cmd[cmd.index("-filter_complex") + 1]
    assert "shell" not in cmd
    assert cmd[-1] == "output.mp4"


def test_parameter_validation():
    with pytest.raises(ValueError):
        EditPreset(width=301, creator="a", original_url="url").validate()
    with pytest.raises(ValueError):
        EditPreset(fit="bad", creator="a", original_url="url").validate()
    with pytest.raises(ValueError):
        EditPreset(fit="pad").validate()
