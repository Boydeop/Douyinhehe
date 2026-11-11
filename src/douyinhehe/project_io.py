"""Versioned, bounded, atomic local video-edit project files.

Projects store only editing parameters and paths to user-owned video files.
They contain no media blobs, API keys, cookies or hidden remote actions.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from .logging_support import redact
from .studio_engine import parse_regions

SCHEMA_VERSION = 1
MAX_BYTES = 2_000_000
MAX_CLIPS = 500
EXTENSION = ".dhyproj"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".m4v", ".webm"}
_RUNTIME_FIELDS = {"output_size", "fit_mode", "mask_mode"}
_FIELDS = {
    "size", "fit", "brightness", "contrast", "saturation", "trim_start",
    "trim_end", "mask_type", "masks", "cta", "source_url", "subtitle", "voice",
}


def _index(value: object, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"Thiết lập {name} không hợp lệ.")
    return value


def _decimal(value: object, minimum: float, maximum: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Thông số {name} không hợp lệ.")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"Thông số {name} ngoài giới hạn.")
    return number


def normalize_state(raw: dict, *, encode: bool) -> dict:
    if not isinstance(raw, dict) or (set(raw) != _FIELDS and
                                         set(raw) != _FIELDS | _RUNTIME_FIELDS):
        raise ValueError("Dự án có cấu trúc thông số chỉnh sửa không hợp lệ.")
    state: dict = {
        "size": _index(raw["size"], 3, "kích thước"),
        "fit": _index(raw["fit"], 2, "kiểu khung"),
        "mask_type": _index(raw["mask_type"], 1, "kiểu che"),
        "brightness": _decimal(raw["brightness"], -.5, .5, "độ sáng"),
        "contrast": _decimal(raw["contrast"], .5, 2, "tương phản"),
        "saturation": _decimal(raw["saturation"], 0, 2, "bão hòa"),
        "trim_start": _decimal(raw["trim_start"], 0, 36000, "điểm đầu"),
        "trim_end": _decimal(raw["trim_end"], 0, 36000, "điểm cuối"),
    }
    if state["trim_end"] and state["trim_end"] <= state["trim_start"]:
        raise ValueError("Điểm cắt kết thúc phải lớn hơn điểm đầu.")
    for name, limit in (("cta", 140), ("source_url", 4096),
                        ("subtitle", 4096), ("voice", 4096)):
        value = raw[name]
        if not isinstance(value, str) or len(value) > limit or "\x00" in value:
            raise ValueError(f"Trường {name} không hợp lệ.")
        # Sensitive URL query parameters must not be persisted in project files.
        state[name] = (redact(value) if name == "source_url" and encode else value)
    regions = parse_regions(raw["masks"])
    state["masks"] = [asdict(region) for region in regions] if encode else regions
    return state


def _absolute_video_path(value: object) -> Path:
    if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value:
        raise ValueError("Đường dẫn clip không hợp lệ.")
    path = Path(value).expanduser()
    if not path.is_absolute() or path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("Dự án chỉ chấp nhận đường dẫn video tuyệt đối.")
    return path.resolve()


def _validate_payload(payload: object) -> tuple[list[tuple[Path, dict]], Path | None]:
    if not isinstance(payload, dict) or set(payload) != {"version", "clips", "selected"}:
        raise ValueError("File dự án không đúng cấu trúc.")
    if payload["version"] != SCHEMA_VERSION:
        raise ValueError("Phiên bản dự án chưa được hỗ trợ.")
    entries = payload["clips"]
    if not isinstance(entries, list) or len(entries) > MAX_CLIPS:
        raise ValueError("Dự án chứa quá nhiều clip.")
    seen: set[Path] = set()
    clips = []
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"path", "state"}:
            raise ValueError("Mục video trong dự án không hợp lệ.")
        path = _absolute_video_path(item["path"])
        if path in seen:
            raise ValueError("Dự án trùng đường dẫn clip.")
        seen.add(path)
        clips.append((path, normalize_state(item["state"], encode=False)))
    selected = payload["selected"]
    if selected is not None:
        selected = _absolute_video_path(selected)
        if selected not in seen:
            raise ValueError("Clip được chọn không nằm trong dự án.")
    return clips, selected


def save_project(target: Path, clips: list[tuple[Path, dict]], selected: Path | None) -> Path:
    destination = Path(target).expanduser().resolve()
    if destination.suffix.lower() != EXTENSION:
        raise ValueError(f"File dự án phải có đuôi {EXTENSION}.")
    if len(clips) > MAX_CLIPS:
        raise ValueError("Vượt quá 500 clip trong dự án.")
    payload = {
        "version": SCHEMA_VERSION,
        "clips": [{"path": str(Path(path).resolve()), "state": normalize_state(state, encode=True)}
                  for path, state in clips],
        "selected": str(Path(selected).resolve()) if selected is not None else None,
    }
    _validate_payload(payload)
    serialized = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(serialized) > MAX_BYTES:
        raise ValueError("Dự án vượt giới hạn 2 MB.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # No half-written project on power loss, with a recovery copy of the old
    # version before replacing it.
    with tempfile.TemporaryDirectory(prefix=".dhyproj-", dir=destination.parent) as root:
        stage = Path(root) / destination.name
        stage.write_bytes(serialized)
        if destination.is_file():
            backup = Path(root) / (destination.name + ".bak")
            shutil.copy2(destination, backup)
            os.replace(backup, destination.with_suffix(destination.suffix + ".bak"))
        os.replace(stage, destination)
    return destination


def load_project(source: Path) -> tuple[list[tuple[Path, dict]], Path | None]:
    path = Path(source).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != EXTENSION:
        raise ValueError(f"Chỉ mở file dự án {EXTENSION} có thật.")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("File dự án vượt giới hạn 2 MB.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("File dự án bị hỏng hoặc không phải JSON hợp lệ.") from exc
    return _validate_payload(payload)


def preset_from_state(state: dict, output_formats: tuple) -> "EditPreset":
    """Construct the exact FFmpeg preset for one saved clip without Qt UI state."""
    from dataclasses import replace
    from .media import EditPreset

    s = normalize_state(state, encode=False)
    if len(output_formats) <= s["size"]:
        raise ValueError("Định dạng đầu ra không được hỗ trợ.")
    _, width, height = output_formats[s["size"]]
    mask_mode = ("blur", "solid")[s["mask_type"]]
    preset = EditPreset(
        width=width, height=height,
        fit=("crop", "pad", "blur")[s["fit"]],
        brightness=s["brightness"], contrast=s["contrast"],
        saturation=s["saturation"], cta=s["cta"].strip(),
        original_url=s["source_url"].strip(),
        subtitle=Path(s["subtitle"]).expanduser() if s["subtitle"].strip() else None,
        narration=Path(s["voice"]).expanduser() if s["voice"].strip() else None,
        masks=tuple(replace(region, mode=mask_mode) for region in s["masks"]),
        trim_start=s["trim_start"], trim_end=s["trim_end"] or None,
    )
    preset.validate()
    return preset
