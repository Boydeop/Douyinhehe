"""FFmpeg integration test using synthetic video, skips if FFmpeg not on PATH."""

import shutil
import subprocess

import pytest

from douyinhehe.media import EditPreset, probe_video, render_video


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg unavailable")
def test_real_ffmpeg_render(tmp_path):
    src = tmp_path / "sample.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1:r=12",
                    "-c:v", "mpeg4", "-t", "1", str(src)], check=True, timeout=30)
    target = tmp_path / "edited.mp4"
    preset = EditPreset(width=360, height=640, creator="Creator", original_url="https://douyin.com/video/1",
                        cta="Link trang kênh", fit="pad")
    render_video(src, target, preset)
    result = probe_video(target)
    assert target.stat().st_size > 1000
    assert any(s.get("width") == 360 and s.get("height") == 640 for s in result["streams"])
