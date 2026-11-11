"""Local deterministic FFmpeg editor with source-credit overlays and validation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from .studio_engine import MaskRegion, parse_regions, mask_filter_chain


def find_binary(name: str) -> str:
    filename = name + (".exe" if sys.platform == "win32" else "")
    # PyInstaller onedir EXE lives in dist/DouyinhehePro, whereas its
    # _internal module tree may live elsewhere. The portable bin directory
    # must be beside the executable, not inside the unpacked Python modules.
    roots = [Path(sys.executable).resolve().parent]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS))
    for root in roots:
        candidate = root / "bin" / filename
        if candidate.is_file():
            return str(candidate)
    resolved = shutil.which(name)
    if resolved:
        return resolved
    raise FileNotFoundError(f"Thiếu {name}. Cài FFmpeg hoặc dùng bản phát hành đi kèm FFmpeg.")


def probe_video(path: Path, ffprobe: str | None = None) -> dict:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    cmd = [ffprobe or find_binary("ffprobe"), "-v", "error", "-show_format", "-show_streams",
           "-of", "json", str(source)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45, check=False)
    if proc.returncode:
        raise RuntimeError((proc.stderr or "ffprobe thất bại")[:1000])
    data = json.loads(proc.stdout)
    if not any(s.get("codec_type") == "video" for s in data.get("streams", [])):
        raise ValueError("Tệp không có luồng hình ảnh.")
    return data


@dataclass(frozen=True)
class EditPreset:
    width: int = 1080
    height: int = 1920
    fit: str = "crop"  # crop, pad, blur
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    cta: str = ""
    creator: str = ""
    original_url: str = ""
    subtitle: Path | None = None
    narration: Path | None = None
    cta_position: str = "bottom"
    cta_background: str = "#101827"
    cta_foreground: str = "#FFFFFF"
    cta_font_size: int = 40
    masks: tuple[MaskRegion, ...] = ()
    trim_start: float = 0.0
    trim_end: float | None = None

    def validate(self) -> None:
        if self.width < 256 or self.height < 256 or self.width % 2 or self.height % 2:
            raise ValueError("Kích thước video phải là số chẵn và từ 256px.")
        if self.fit not in {"crop", "pad", "blur"}:
            raise ValueError("Kiểu căn khung không hợp lệ.")
        if not -0.5 <= self.brightness <= 0.5 or not 0.5 <= self.contrast <= 2.0:
            raise ValueError("Thông số sáng/tương phản vượt giới hạn.")
        if not 0 <= self.saturation <= 2.0:
            raise ValueError("Độ bão hòa màu vượt giới hạn.")
        if len(self.cta) > 140 or len(self.creator) > 140:
            raise ValueError("CTA/tên tác giả quá dài.")
        parse_regions(self.masks)
        if not 0 <= self.trim_start <= 36000:
            raise ValueError("Mốc bắt đầu phải trong 0 đến 36000 giây.")
        if self.trim_end is not None and not self.trim_start < self.trim_end <= 36000:
            raise ValueError("Mốc kết thúc cần lớn hơn mốc bắt đầu.")
        if self.subtitle and not self.subtitle.is_file():
            raise FileNotFoundError(self.subtitle)
        if self.narration and not self.narration.is_file():
            raise FileNotFoundError(self.narration)
        from .cta_presets import CTAStyle
        CTAStyle(self.cta_position, self.cta_background, self.cta_foreground, self.cta_font_size).validate()


def _font(size: int):
    from PIL import ImageFont

    options = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/msyh.ttc",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"]
    for option in options:
        try:
            return ImageFont.truetype(option, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def make_overlay(preset: EditPreset, target: Path) -> None:
    """Transparent overlay with CTA, visible author attribution, and safe text wrapping."""
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (preset.width, preset.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad = int(preset.width * 0.05)
    headline = preset.cta.strip()
    if headline:
        max_chars = max(20, preset.width // 28)
        lines = []
        words = headline.split()
        current = ""
        for word in words:
            if current and len(current + " " + word) > max_chars:
                lines.append(current)
                current = word
            else:
                current = (current + " " + word).strip()
        if current:
            lines.append(current)
        lines = lines[:3]
        top = int(preset.height * (.40 if preset.cta_position == "center" else .74))
        step = int(preset.cta_font_size * 1.75)
        bottom = min(preset.height - pad, top + step * len(lines) + 95)
        rgb_bg = tuple(bytes.fromhex(preset.cta_background[1:]))
        rgb_fg = tuple(bytes.fromhex(preset.cta_foreground[1:]))
        draw.rounded_rectangle((pad, top, preset.width - pad, bottom), radius=24, fill=(*rgb_bg, 180))
        for index, line in enumerate(lines):
            draw.text((pad + 20, top + 12 + index * step), line, fill=(*rgb_fg, 255),
                      font=_font(preset.cta_font_size))
    # Never fabricate a Douyin credit on personal/local clips.
    if preset.original_url:
        source = ("Video tự quay" if preset.original_url.startswith("local://")
                  else "Nguồn: Douyin" if "douyin.com" in preset.original_url else "Nguồn: Video")
        draw.rounded_rectangle((pad, pad, preset.width - pad, pad + 64),
                               radius=12, fill=(0, 0, 0, 160))
        draw.text((pad + 12, pad + 9), source, fill=(255, 255, 255, 255), font=_font(29))
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)


def _subtitle_filter(path: Path) -> str:
    """Escape path for ffmpeg filtergraph, including drive colon on Windows."""
    # ffmpeg's filtergraph parser consumes one escape layer; protect ':' and '\\'.
    raw = str(path.resolve()).replace("\\", "/")
    escaped = raw.replace("'", "\\\\'").replace(":", "\\\\:").replace(",", "\\,")
    return f"subtitles=filename='{escaped}'"


def build_edit_command(source: Path, output: Path, overlay: Path, preset: EditPreset,
                       ffmpeg: str = "ffmpeg") -> list[str]:
    preset.validate()
    w, h = preset.width, preset.height
    if preset.fit == "crop":
        video = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[v0]"
    elif preset.fit == "pad":
        video = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black[v0]"
    else:
        video = (f"[0:v]split=2[bg][fg];[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
                 f"crop={w}:{h},boxblur=18:1[blur];[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[front];"
                 "[blur][front]overlay=(W-w)/2:(H-h)/2[v0]")
    look = (f"[v0]eq=brightness={preset.brightness}:contrast={preset.contrast}:"
            f"saturation={preset.saturation}[v1]")
    chain = f"{video};{look}"
    subtitle_node = "v1"
    masks, masked_node = mask_filter_chain("v1", preset.masks, w, h)
    if masks:
        chain += ";" + masks
        subtitle_node = masked_node
    if preset.subtitle:
        chain += f";[{subtitle_node}]{_subtitle_filter(preset.subtitle)}[vs]"
        subtitle_node = "vs"
    chain += f";[{subtitle_node}][1:v]overlay=0:0:format=auto:shortest=1,format=yuv420p[vout]"
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y"]
    if preset.trim_start:
        cmd += ["-ss", str(preset.trim_start)]
    cmd += ["-i", str(source), "-loop", "1", "-i", str(overlay)]
    if preset.narration:
        cmd += ["-i", str(preset.narration)]
    cmd += ["-filter_complex", chain, "-map", "[vout]"]
    cmd += ["-map", "2:a:0"] if preset.narration else ["-map", "0:a?"]
    if preset.trim_end is not None:
        cmd += ["-t", str(preset.trim_end - preset.trim_start)]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
            "-r", "30", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart",
            "-shortest", "-metadata", f"comment=Source: {preset.original_url or 'local'}",
            str(output)]
    return cmd


def render_video(source: Path, target: Path, preset: EditPreset,
                 progress: Callable[[str], None] | None = None) -> Path:
    preset.validate()
    source = Path(source).resolve()
    target = Path(target).resolve()
    if source == target:
        raise ValueError("Không được ghi đè video nguồn.")
    probe_video(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomic output: FFmpeg failures must NEVER destroy an earlier valid render.
    # Temp output stays on the same filesystem so os.replace is atomic.
    with tempfile.TemporaryDirectory(prefix=".douyinhehe-", dir=target.parent) as temp:
        overlay = Path(temp) / "credit.png"
        staged = Path(temp) / "render.mp4"
        make_overlay(preset, overlay)
        command = build_edit_command(source, staged, overlay, preset, find_binary("ffmpeg"))
        if progress:
            progress(f"Render: {source.name}")
        proc = subprocess.run(command, capture_output=True, text=True, timeout=7200, check=False)
        if proc.returncode:
            raise RuntimeError(f"FFmpeg thất bại: {proc.stderr[-2000:]}")
        probe_video(staged)
        if staged.stat().st_size < 1024:
            raise RuntimeError("FFmpeg tạo file rỗng hoặc không hợp lệ.")
        os.replace(staged, target)
    if progress:
        progress(f"Xuất thành công: {target.name}")
    return target
