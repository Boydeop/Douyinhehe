"""FFmpeg mask geometry, optional OCR fallback, privacy and full-channel routing."""
import json
import pytest
from PIL import Image
from douyinhehe.studio_engine import MaskRegion, parse_regions, regions_to_json, mask_filter_chain, suggest_chinese_regions
from douyinhehe.core import LicenseGrant, Store
from douyinhehe.downloader import is_channel_url

def test_mask_roundtrip_and_reject_bad_boxes():
    box = MaskRegion(.1,.65,.8,.15)
    assert parse_regions(regions_to_json([box])) == (box,)
    with pytest.raises(ValueError):
        parse_regions([{"x":.9,"y":0,"width":.2,"height":.1}])
    with pytest.raises(ValueError):
        parse_regions([box] * 13)

def test_mask_ffmpeg_filters():
    graph, node = mask_filter_chain("v1",[MaskRegion(.1,.6,.8,.2),MaskRegion(.1,.1,.3,.1,"solid")],360,640)
    assert "boxblur" in graph and "drawbox" in graph and node=="mask1"

def test_ocr_only_claims_detected_text(tmp_path, monkeypatch):
    import douyinhehe.ocr_support as ocr
    image=tmp_path/"test.png"
    Image.new("RGB",(360,640),"black").save(image)
    monkeypatch.setattr(ocr, "detect_chinese_boxes", lambda _path: [])
    regions,message=suggest_chinese_regions(image)
    assert regions == () and "không thấy" in message

def test_channel_url_validation():
    assert is_channel_url("https://www.douyin.com/user/MS4wLjABCD")
    assert not is_channel_url("https://www.douyin.com/video/123")
    assert not is_channel_url("https://douyin.com.bad.tld/user/a")

def test_private_grant_not_persisted(tmp_path):
    s=Store(tmp_path/"db.sqlite")
    g=LicenseGrant("https://www.douyin.com/video/123","private person","private contract",True,True)
    s.save_source(g)
    assert "creator" not in s.sources()[0] and "evidence" not in s.sources()[0]
    with s._connect() as db:
        row=db.execute("select creator,evidence from sources").fetchone()
        assert row["creator"]==row["evidence"]==""


def test_blur_preview_matches_rendered_background(tmp_path):
    """Blur-fit frame must not silently show black padded bars."""
    import shutil
    import subprocess
    from douyinhehe.studio_engine import extract_preview_frame

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("FFmpeg and FFprobe required")
    clip = tmp_path / "wide.mp4"
    frame = tmp_path / "blur.png"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=yellow:s=320x240:d=1",
        "-c:v", "mpeg4", str(clip),
    ], check=True, capture_output=True, timeout=45)
    extract_preview_frame(clip, frame, fit="blur", seconds=.1, width=360, height=640)
    with Image.open(frame).convert("RGB") as image:
        r, g, b = image.getpixel((10, 10))
        assert r > 130 and g > 130 and b < 130, (
            "Blur background should fill the frame, not display black bars."
        )
