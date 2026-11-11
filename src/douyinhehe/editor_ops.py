"""Small editor operations that can be unit tested without Qt installed."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .media import EditPreset
from .studio_engine import MaskRegion, parse_regions


def preset_from_editor_state(state: dict) -> EditPreset:
    """Build a validated independent render preset from one clip's Qt snapshot.

    This runs without Qt, so batch exports can freeze each clip's options
    before the worker starts. A missing saved state must be handled by the
    caller, never by accidentally borrowing another clip's values.
    """
    if not isinstance(state, dict):
        raise ValueError("Thiếu cấu hình chỉnh sửa cho clip.")
    size = state["output_size"]
    if (not isinstance(size, (tuple, list)) or len(size) != 2 or
            any(type(n) is not int for n in size)):
        raise ValueError("Khung hình video không hợp lệ.")
    masks = tuple(MaskRegion(region.x, region.y, region.width, region.height,
                             state["mask_mode"]) for region in parse_regions(state["masks"]))
    preset = EditPreset(
        width=size[0], height=size[1], fit=state["fit_mode"],
        brightness=float(state["brightness"]), contrast=float(state["contrast"]),
        saturation=float(state["saturation"]), cta=str(state["cta"]).strip(),
        original_url=str(state["source_url"]).strip(),
        subtitle=Path(state["subtitle"]).expanduser() if state["subtitle"].strip() else None,
        narration=Path(state["voice"]).expanduser() if state["voice"].strip() else None,
        masks=masks, trim_start=float(state["trim_start"]),
        trim_end=float(state["trim_end"]) if state["trim_end"] else None,
    )
    preset.validate()
    return preset


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
