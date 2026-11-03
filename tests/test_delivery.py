from douyinhehe.delivery import DESTINATIONS, credit_text, delivery_preflight


def test_platform_credits_and_preflight(tmp_path, monkeypatch):
    assert len(DESTINATIONS) == 5
    credit = credit_text("Tác giả", "https://www.douyin.com/video/1")
    assert "hoa hồng" in credit.lower()
    import douyinhehe.delivery as module
    monkeypatch.setattr(module, "probe_video", lambda _: {"streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920}],
        "format": {"duration": "29.75"}})
    video = tmp_path / "demo.mp4"
    report = delivery_preflight(video, credit=credit, platform="youtube")
    assert report["warnings"] == []
    assert report["duration_seconds"] == 29.75
    report2 = delivery_preflight(video, credit="", platform="tiktok")
    assert len(report2["warnings"]) == 2
