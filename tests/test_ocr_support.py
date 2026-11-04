"""Tests for true offline inference, model packaging and OCR safety gates."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from douyinhehe import ocr_support as ocr
from douyinhehe.studio_engine import suggest_chinese_regions


def test_missing_ocr_never_masquerades_as_detection(tmp_path, monkeypatch):
    frame = tmp_path / "frame.png"
    Image.new("RGB", (360, 640), "white").save(frame)
    def unavailable(_frame, **kwargs):
        raise ocr.OCRUnavailable("Thiếu model OCR")
    monkeypatch.setattr(ocr, "detect_chinese_boxes", unavailable)
    with pytest.raises(ocr.OCRUnavailable, match="Thiếu model OCR"):
        suggest_chinese_regions(frame)


def test_detect_uses_real_result_contract_and_cached_engine(tmp_path, monkeypatch):
    frame = tmp_path / "zh.png"
    Image.new("RGB", (480, 640), "white").save(frame)
    calls = {"init": 0, "run": 0}
    class FakeRapidOCR:
        def __init__(self):
            calls["init"] += 1
        def __call__(self, image):
            calls["run"] += 1
            assert image.size == (480, 640)
            return SimpleNamespace(boxes=[
                [[20, 200], [230, 200], [230, 260], [20, 260]],
                [[10, 300], [230, 300], [230, 350], [10, 350]],
                [[10, 400], [200, 400], [200, 430], [10, 430]],
            ], txts=("厨房收纳", "English", "中国"), scores=(.96, .98, .21))
    fake = types.ModuleType("rapidocr")
    fake.RapidOCR = FakeRapidOCR
    monkeypatch.setitem(sys.modules, "rapidocr", fake)
    monkeypatch.setattr(ocr, "check_ocr_assets", lambda: ocr.OCRStatus(True, 3, "ok"))
    ocr._engine.cache_clear()
    try:
        regions, reason = suggest_chinese_regions(frame)
        assert len(regions) == 1
        assert regions[0].x >= 0 and regions[0].y >= 0
        assert "OCR" in reason
        suggest_chinese_regions(frame)
        assert calls == {"init": 1, "run": 2}
    finally:
        ocr._engine.cache_clear()


def test_ocr_empty_and_bad_confidence(tmp_path, monkeypatch):
    frame = tmp_path / "blank.png"
    Image.new("RGB", (300, 300), "white").save(frame)
    class Stub:
        def __call__(self, image):
            return SimpleNamespace(boxes=None, txts=None, scores=None)
    monkeypatch.setattr(ocr, "_engine", lambda: Stub())
    assert ocr.detect_chinese_boxes(frame) == []
    with pytest.raises(ValueError, match="Ngưỡng tin cậy"):
        ocr.detect_chinese_boxes(frame, min_confidence=1.2)


def test_check_assets_reports_missing_modules(monkeypatch):
    monkeypatch.setattr(ocr.importlib.util, "find_spec", lambda _name: None)
    status = ocr.check_ocr_assets()
    assert not status.ready and status.models == 0
    assert "Thiếu" in status.message
