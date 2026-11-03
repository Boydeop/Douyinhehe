import json
import sys
import types
from pathlib import Path

import pytest

from douyinhehe.core import Store
from douyinhehe.subtitles import Caption, parse_srt, write_srt, translate_srt


SRT = "1\n00:00:00,100 --> 00:00:01,500\n你好\n\n2\n00:00:01,500 --> 00:00:03,100\n这个好用\n"


def test_srt_roundtrip(tmp_path):
    parsed = parse_srt(SRT)
    assert parsed[1].text == "这个好用"
    path = tmp_path / "out.srt"
    write_srt(parsed, path)
    assert parse_srt(path.read_text(encoding="utf-8")) == parsed
    with pytest.raises(ValueError):
        parse_srt("1\ninvalid\ntext")


def test_gemini_opt_in_and_translation_cache(tmp_path, monkeypatch):
    src = tmp_path / "zh.srt"
    src.write_text(SRT, encoding="utf-8")
    db = Store(tmp_path / "db.sqlite")
    dest = tmp_path / "vi.srt"
    with pytest.raises(PermissionError):
        translate_srt(src, dest, db, api_key="fake", model_name="gemini-test", confirmed_free_tier=False)
    count = {"runs": 0}

    class Client:
        def __init__(self, **kw):
            assert kw["api_key"] == "fake"
            self.models = self
        def generate_content(self, **kw):
            count["runs"] += 1
            return types.SimpleNamespace(text=json.dumps(["Xin chào", "Món này hữu ích"], ensure_ascii=False))
        def close(self):
            pass

    google = types.ModuleType("google")
    google.__path__ = []
    fake = types.ModuleType("google.genai")
    fake.Client = Client
    google.genai = fake
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", fake)
    translate_srt(src, dest, db, api_key="fake", model_name="gemini-test", confirmed_free_tier=True)
    assert "Xin chào" in dest.read_text(encoding="utf-8")
    translate_srt(src, dest, db, api_key="fake", model_name="gemini-test", confirmed_free_tier=True)
    assert count["runs"] == 1
