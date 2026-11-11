"""Offline geometry and FFmpeg filters for video masks. No watermark/copyright bypass."""
from __future__ import annotations
import json
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass(frozen=True)
class MaskRegion:
    x: float
    y: float
    width: float
    height: float
    mode: str = "blur"

    def validate(self):
        vals = (self.x, self.y, self.width, self.height)
        if any(not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in vals):
            raise ValueError("Tọa độ vùng che cần nằm trong [0,1].")
        if self.width < .005 or self.height < .005 or self.x + self.width > 1.00001 or self.y + self.height > 1.00001:
            raise ValueError("Vùng che quá nhỏ hoặc nằm ngoài khung.")
        if self.mode not in {"blur", "solid"}:
            raise ValueError("Kiểu che phải là blur hoặc solid.")

def parse_regions(value):
    if not value:
        return ()
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, (list, tuple)) or len(value) > 12:
        raise ValueError("Mỗi video chỉ hỗ trợ tối đa 12 vùng che.")
    regions = tuple(v if isinstance(v, MaskRegion) else MaskRegion(**v) for v in value)
    for region in regions:
        region.validate()
    return regions

def regions_to_json(regions):
    return json.dumps([asdict(r) for r in parse_regions(tuple(regions))], ensure_ascii=False)

def mask_filter_chain(start: str, regions, width: int, height: int):
    """Return ffmpeg filtergraph segment and last output label."""
    if width < 32 or height < 32 or width % 2 or height % 2:
        raise ValueError("Khung video phải có kích thước chẵn.")
    chain, previous = [], start
    for i, region in enumerate(parse_regions(regions)):
        x = max(0, min(width - 4, int(region.x * width) // 2 * 2))
        y = max(0, min(height - 4, int(region.y * height) // 2 * 2))
        w = max(4, min(width - x, int(region.width * width) // 2 * 2))
        h = max(4, min(height - y, int(region.height * height) // 2 * 2))
        next_name = f"mask{i}"
        if region.mode == "solid":
            chain.append(f"[{previous}]drawbox=x={x}:y={y}:w={w}:h={h}:color=black@0.92:t=fill[{next_name}]")
        else:
            chain.append(f"[{previous}]split=2[base{i}][crop{i}]")
            radius = max(1, min(12, (w - 2) // 2, (h - 2) // 2))
            chain.append(f"[crop{i}]crop={w}:{h}:{x}:{y},boxblur={radius}:1[patch{i}]")
            chain.append(f"[base{i}][patch{i}]overlay={x}:{y}:shortest=1[{next_name}]")
        previous = next_name
    return ";".join(chain), previous

def default_caption_region():
    """Fallback proposal, NOT an OCR detection."""
    return (MaskRegion(.08, .74, .84, .16),)

def suggest_chinese_regions(frame: Path):
    """Detect Chinese text using bundled RapidOCR. Never silently mask a guessed area."""
    from .ocr_support import detect_chinese_boxes

    found = detect_chinese_boxes(Path(frame))
    regions = parse_regions([MaskRegion(*rect) for rect in found])
    if regions:
        return regions, f"OCR offline tìm thấy {len(regions)} vùng có chữ Trung; kiểm tra trước khi xuất."
    return (), "OCR offline không thấy chữ Trung trong khung này; không tự che nhầm vùng khác."

def extract_preview_frame(video: Path, image: Path, *, seconds: float = 1.0, fit: str = "crop",
                          width: int = 360, height: int = 640):
    from .media import find_binary, probe_video
    video = Path(video).resolve()
    if not video.is_file() or not 0 <= seconds <= 36000:
        raise ValueError("File/mốc thời gian không hợp lệ.")
    if fit not in {"crop", "pad", "blur"}:
        raise ValueError("Kiểu khung không hợp lệ.")
    probe_video(video)
    image = Path(image).resolve()
    image.parent.mkdir(parents=True, exist_ok=True)
    if fit == "crop":
        vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    elif fit == "pad":
        vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    else:
        # Keep the mask editor's displayed coordinates consistent with the
        # blurred-background output produced by build_edit_command().
        vf = (f"split=2[bg][fg];[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
              f"crop={width}:{height},boxblur=18:1[blur];"
              f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[front];"
              "[blur][front]overlay=(W-w)/2:(H-h)/2")
    cmd = [find_binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-ss", str(seconds),
           "-i", str(video), "-frames:v", "1", "-vf", vf, "-an", str(image)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=45, check=False)
    if p.returncode or not image.is_file():
        raise RuntimeError("Không đọc được khung hình: " + p.stderr[-350:])
    if image.stat().st_size > 15_000_000:
        image.unlink(missing_ok=True)
        raise ValueError("Khung xem trước vượt giới hạn.")
    return image
