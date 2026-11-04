"""Persistent, user-controlled caption and affiliate call-to-action styles."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .core import user_data_dir


@dataclass(frozen=True)
class CTAStyle:
    position: str = "bottom"  # bottom or center
    background: str = "#101827"
    foreground: str = "#FFFFFF"
    font_size: int = 40

    def validate(self) -> None:
        if self.position not in {"bottom", "center"} or not 18 <= self.font_size <= 90:
            raise ValueError("Vị trí/kích thước CTA không hợp lệ.")
        for color in (self.background, self.foreground):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("Màu CTA phải ở dạng #RRGGBB.")


def preset_file(name: str) -> Path:
    if not re.fullmatch(r"[\w À-ỹ-]{1,50}", name):
        raise ValueError("Tên preset không hợp lệ.")
    return user_data_dir() / "cta_presets" / f"{name}.json"


def save_preset(name: str, style: CTAStyle) -> Path:
    style.validate()
    path = preset_file(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".tmp")
    part.write_text(json.dumps(asdict(style), ensure_ascii=False, indent=2), encoding="utf-8")
    part.replace(path)
    return path


def load_preset(name: str) -> CTAStyle:
    payload = json.loads(preset_file(name).read_text(encoding="utf-8"))
    style = CTAStyle(**payload)
    style.validate()
    return style
