"""Bundled, offline Chinese-text OCR using RapidOCR + ONNX Runtime.

Models are shipped within the rapidocr Python package. No external API or
implicit model download is used by this module; never call result.vis().
"""
from __future__ import annotations

import importlib.util
import math
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_INFER_LOCK = threading.Lock()


class OCRUnavailable(RuntimeError):
    """RapidOCR, native inference engine, or bundled model assets are absent."""


@dataclass(frozen=True)
class OCRStatus:
    ready: bool
    models: int
    message: str


def check_ocr_assets() -> OCRStatus:
    """Check packaged OCR artifacts without starting inference or making network calls."""
    rapidocr_spec = importlib.util.find_spec("rapidocr")
    runtime_spec = importlib.util.find_spec("onnxruntime")
    if rapidocr_spec is None or rapidocr_spec.origin is None or runtime_spec is None:
        return OCRStatus(False, 0, "Thiếu RapidOCR/ONNX Runtime. Hãy dùng bản EXE đóng kèm OCR.")
    model_dir = Path(rapidocr_spec.origin).resolve().parent / "models"
    files = list(model_dir.rglob("*.onnx")) if model_dir.is_dir() else []
    if len(files) < 3:
        return OCRStatus(False, len(files), "Thiếu model OCR offline (detection/classification/recognition).")
    return OCRStatus(True, len(files), f"OCR offline sẵn sàng: {len(files)} model ONNX đóng kèm.")


@lru_cache(maxsize=1)
def _engine():
    status = check_ocr_assets()
    if not status.ready:
        raise OCRUnavailable(status.message)
    try:
        from rapidocr import RapidOCR
        return RapidOCR()
    except Exception as exc:
        raise OCRUnavailable(f"Không khởi tạo được OCR offline: {type(exc).__name__}: {exc}") from exc


def detect_chinese_boxes(frame: Path, *, min_confidence: float = 0.55) -> list[tuple[float, float, float, float]]:
    """Return normalized padded boxes containing Chinese characters on one frame.

    These are proposals for local editing, not a claim that all subtitles
    throughout the video were located. Every crop should be previewed.
    """
    from PIL import Image

    path = Path(frame)
    if not path.is_file():
        raise FileNotFoundError(path)
    if not 0 <= min_confidence <= 1:
        raise ValueError("Ngưỡng tin cậy OCR phải nằm trong khoảng 0..1.")
    with Image.open(path) as source:
        img = source.convert("RGB")
        width, height = img.size
    with _INFER_LOCK:
        result = _engine()(img)
    if result is None or getattr(result, "boxes", None) is None:
        return []
    boxes = result.boxes
    texts = getattr(result, "txts", None) or ()
    scores = getattr(result, "scores", None) or ()
    found: list[tuple[float, float, float, float]] = []
    for corners, value, confidence in zip(boxes, texts, scores):
        if not _CJK.search(str(value)):
            continue
        try:
            score = float(confidence)
            if not math.isfinite(score) or score < min_confidence:
                continue
            xs = [float(pt[0]) for pt in corners]
            ys = [float(pt[1]) for pt in corners]
            if len(xs) != 4 or any(not math.isfinite(n) for n in xs + ys):
                continue
            left = max(0., min(xs) / width - 10. / width)
            right = min(1., max(xs) / width + 10. / width)
            top = max(0., min(ys) / height - 7. / height)
            bottom = min(1., max(ys) / height + 7. / height)
            if right - left >= .005 and bottom - top >= .005:
                found.append((left, top, right - left, bottom - top))
        except (TypeError, ValueError, IndexError):
            continue
    return found[:12]


def offline_ocr_smoke_test() -> dict[str, str | int]:
    """Load bundled model files and run one real inference without network."""
    from PIL import Image, ImageDraw, ImageFont

    status = check_ocr_assets()
    if not status.ready:
        raise OCRUnavailable(status.message)
    canvas = Image.new("RGB", (960, 240), "white")
    font = None
    for file in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf",
                 "C:/Windows/Fonts/simsun.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"):
        if Path(file).is_file():
            font = ImageFont.truetype(file, 98)
            break
    if font is None:
        raise OCRUnavailable("Không tìm thấy font CJK để kiểm tra OCR trên hệ thống build.")
    ImageDraw.Draw(canvas).text((30, 46), "厨房收纳 家居好物", fill="black", font=font)
    with _INFER_LOCK:
        result = _engine()(canvas)
    words = tuple(getattr(result, "txts", None) or ())
    if not words:
        raise OCRUnavailable("Model OCR đã chạy nhưng không nhận diện được ảnh chữ Trung thử nghiệm.")
    return {"models": status.models, "recognized_lines": len(words), "status": "offline-inference-ok"}
