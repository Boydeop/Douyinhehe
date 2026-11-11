"""Small editor operations that can be unit tested without Qt installed."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .media import EditPreset


def clip_duration(info: dict) -> float:
    """Duration may come from the container format or an individual video stream."""
    values = [info.get("format", {}).get("duration")]
    values.extend(s.get("duration") for s in info.get("streams", ()) if s.get("codec_type") == "video")
    for value in values:
        try:
            duration = float(value)
            if 0 < duration < 86400:
                return duration
        except (TypeError, ValueError):
            pass
    return 0.0


def safe_output_path(folder: Path, source: Path, reserved: set[Path] | None = None) -> Path:
    """Allocate a name without overwriting the source, exports or concurrent selections."""
    folder, source = Path(folder).resolve(), Path(source).resolve()
    reserved = reserved if reserved is not None else set()
    for index in range(1, 10001):
        suffix = "_edited" if index == 1 else f"_edited_{index}"
        target = folder / (source.stem + suffix + ".mp4")
        if target != source and target not in reserved and not target.exists():
            reserved.add(target)
            return target
    raise RuntimeError("Thư mục xuất đã có quá nhiều tên trùng.")


def preview_preset(preset: EditPreset, *, source_duration: float = 0.0) -> EditPreset:
    """A preview is at most five seconds and uses reduced spatial resolution."""
    start = preset.trim_start
    end = start + 5.0
    if preset.trim_end is not None:
        end = min(end, preset.trim_end)
    if source_duration:
        end = min(end, source_duration)
    if end - start < 0.12:
        raise ValueError("Điểm cắt vượt thời lượng video; không thể tạo xem trước.")
    if preset.width > preset.height:
        size = (640, 360)
    elif preset.width == preset.height:
        size = (480, 480)
    else:
        size = (360, 640)
    return replace(preset, width=size[0], height=size[1], trim_end=end)


def seconds_label(milliseconds: int) -> str:
    secs = max(0, int(milliseconds) // 1000)
    return f"{secs // 60:02d}:{secs % 60:02d}"
