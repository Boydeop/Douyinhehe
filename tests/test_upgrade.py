"""2.1 contract, security, validation and update regression tests."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from douyinhehe.affiliate_reports import import_report
from douyinhehe.batch import create_local_manifest, read_manifest, enqueue_manifest
from douyinhehe.core import LicenseGrant, Store
from douyinhehe.cta_presets import CTAStyle, load_preset, save_preset
from douyinhehe.diagnostics import diagnose_failure, downloader_status, update_ytdlp
from douyinhehe.glossary import load_glossary, save_glossary, validate_glossary
from douyinhehe.logging_support import export_redacted_logs, redact, write_event
from douyinhehe.subtitle_qc import audit_srt
from douyinhehe.subtitles import translate_srt
from douyinhehe.tts_adapters import get_tts_engine, PiperVoice


def test_rights_expiration_and_evidence_hash(tmp_path):
    evidence = tmp_path / "license.pdf"
    evidence.write_bytes(b"Signed creator approval")
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    future = (date.today() + timedelta(days=20)).isoformat()
    grant = LicenseGrant("local://123", "Owner", "consent-file", True, True,
                         expires_on=future, evidence_file=str(evidence), evidence_sha256=digest)
    grant.validate()
    db = Store(tmp_path / "test.sqlite")
    db.save_source(grant)
    assert "evidence_sha256" not in db.sources()[0]
    evidence.write_bytes(b"modified")
    with pytest.raises(PermissionError, match="SHA-256"):
        grant.validate()
    with pytest.raises(PermissionError, match="hết hạn"):
        LicenseGrant("local://123", "Owner", "licensed", True, True,
                     expires_on=(date.today() - timedelta(days=1)).isoformat()).validate()


def test_database_upgrade_adds_license_columns_without_losing_records(tmp_path):
    import sqlite3
    file = tmp_path / "legacy.sqlite"
    with sqlite3.connect(file) as db:
        db.execute("""CREATE TABLE sources (id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL,
            creator TEXT NOT NULL, evidence TEXT NOT NULL, commercial INTEGER NOT NULL,
            derivative INTEGER NOT NULL, platforms TEXT NOT NULL, niche TEXT NOT NULL,
            score REAL NOT NULL, file_path TEXT NOT NULL, created_at TEXT NOT NULL)""")
        db.execute("INSERT INTO sources VALUES (1,'old','Creator','proof',1,1,'facebook','decor',0,'','old')")
    store = Store(file)
    rows = store.sources()
    assert rows[0]["url"] == "old"
    assert "creator" not in rows[0]


def test_local_import_manifest_expiry_and_queue(tmp_path):
    folder = tmp_path / "my_clips"
    folder.mkdir()
    (folder / "demo.mp4").write_bytes(b"my owned clip")
    manifest = tmp_path / "local.json"
    with pytest.raises(PermissionError):
        create_local_manifest(folder, manifest, creator="Me", evidence="my video", rights_confirmed=False)
    created = create_local_manifest(folder, manifest, creator="Me", evidence="own video", rights_confirmed=True)
    item = read_manifest(created)[0]
    assert item.original_url.startswith("local://")
    assert enqueue_manifest(Store(tmp_path / "jobs.sqlite"), created) == (1, 0)


def test_caption_speed_line_length_and_overlap(tmp_path):
    file = tmp_path / "sub.srt"
    file.write_text("""1
00:00:00,000 --> 00:00:00,600
Câu này có nhiều chữ đến mức người xem không đọc kịp ở trên màn hình

2
00:00:00,500 --> 00:00:02,000
OK
""", encoding="utf-8")
    issues = audit_srt(file)
    assert {issue.kind for issue in issues} >= {"length", "reading_speed", "overlap"}
    assert any(issue.severity == "error" for issue in issues)


def test_glossary_and_cta_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("DOUYINHEHE_HOME", str(tmp_path))
    assert load_glossary("Mỹ phẩm")["防晒"] == "chống nắng"
    save_glossary("Mỹ phẩm", {"防晒": "kem chống nắng"})
    assert load_glossary("Mỹ phẩm") == {"防晒": "kem chống nắng"}
    with pytest.raises(ValueError):
        validate_glossary({"x": 1})
    style = CTAStyle(position="center", background="#123456", foreground="#ffffff", font_size=55)
    save_preset("BrandAlpha", style)
    assert load_preset("BrandAlpha") == style
    with pytest.raises(ValueError):
        CTAStyle(background="red").validate()


def test_gemini_glossary_review_and_cache(tmp_path, monkeypatch):
    import sys
    import types
    src = tmp_path / "chinese.srt"
    dest = tmp_path / "vietnamese.srt"
    src.write_text("1\n00:00:00,000 --> 00:00:01,700\n防晒\n", encoding="utf-8")
    store = Store(tmp_path / "db.sqlite")
    calls = []
    class Client:
        def __init__(self, **kwargs):
            self.models = self
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text=json.dumps(["kem chống nắng"], ensure_ascii=False))
        def close(self):
            pass
    google = types.ModuleType("google")
    google.__path__ = []
    fake = types.ModuleType("google.genai")
    fake.Client = Client
    google.genai = fake
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", fake)
    args = dict(api_key="test", model_name="gemini-test", confirmed_free_tier=True,
                glossary={"防晒": "kem chống nắng"}, context="mỹ phẩm", review=True)
    translate_srt(src, dest, store, **args)
    assert len(calls) == 2
    assert "glossary" in calls[0]["contents"]
    assert "hậu kiểm" in calls[1]["contents"]
    translate_srt(src, dest, store, **args)
    assert len(calls) == 2
    translate_srt(src, dest, store, **(args | {"review": False}))
    assert len(calls) == 3


def test_affiliate_csv_aggregate_by_video_and_campaign(tmp_path):
    file = tmp_path / "affiliate.csv"
    with file.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=["campaign", "video_id", "platform", "views",
                                               "clicks", "orders", "commission"])
        writer.writeheader()
        writer.writerow(dict(campaign="summer", video_id="v01", platform="tiktok",
                             views=1000, clicks=100, orders=10, commission=50000))
        writer.writerow(dict(campaign="summer", video_id="v01", platform="tiktok",
                             views=500, clicks=20, orders=2, commission=10000))
        writer.writerow(dict(campaign="summer", video_id="v02", platform="youtube",
                             views=2000, clicks=5, orders=1, commission=3000))
    records = import_report(file)
    assert len(records) == 2
    assert records[0]["orders"] == 12
    assert records[0]["commission"] == 60000
    assert records[0]["cvr_percent"] == 10


def test_diagnostics_vietnamese_and_redacted_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("DOUYINHEHE_HOME", str(tmp_path))
    assert "403" in diagnose_failure("HTTP Error 403 Forbidden")
    assert "CAPTCHA" in diagnose_failure("Captcha required")
    assert "[REDACTED" in redact("api_key=secrettokenof12345")
    write_event("render", "Authorization: Bearer ABCDEFGHIJKLMNOP")
    exported = export_redacted_logs(tmp_path / "log.jsonl")
    assert "ABCDEFGHIJKLMNOP" not in exported.read_text(encoding="utf-8")
    with pytest.raises(PermissionError):
        update_ytdlp()


def test_updater_checksum_mismatch_never_installs(tmp_path, monkeypatch):
    import douyinhehe.diagnostics as d
    monkeypatch.setenv("DOUYINHEHE_HOME", str(tmp_path))
    monkeypatch.setattr(d.sys, "platform", "win32")
    tag = "2026.10.26"
    expected = "a" * 64
    base = f"https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/"
    release = {"tag_name": tag, "assets": [
        {"name": "yt-dlp.exe", "digest": "sha256:" + expected,
         "browser_download_url": base + "yt-dlp.exe"},
        {"name": "SHA2-256SUMS", "browser_download_url": base + "SHA2-256SUMS"},
    ]}
    def fake_read(url, limit):
        if url.endswith("/latest"):
            return json.dumps(release).encode()
        if url.endswith("SHA2-256SUMS"):
            return (expected + "  yt-dlp.exe\n").encode()
        return b"not an actual executable"
    monkeypatch.setattr(d, "_read_bounded", fake_read)
    with pytest.raises(ValueError, match="Checksum"):
        update_ytdlp(confirmed=True)
    assert not (tmp_path / "Douyinhehe" / "tools" / "yt-dlp.exe").exists()


def test_tts_piper_requires_valid_paths(tmp_path):
    engine = get_tts_engine("piper", piper_exe=tmp_path / "piper.exe", piper_model=tmp_path / "vi.onnx")
    assert isinstance(engine, PiperVoice)
    with pytest.raises(ValueError):
        engine.synthesize("Xin chào", tmp_path / "out.wav")
    with pytest.raises(ValueError):
        get_tts_engine("paid-cloud")
