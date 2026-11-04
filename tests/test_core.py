import pytest

from douyinhehe.affiliate import Metrics
from douyinhehe.core import LicenseGrant, Store, opportunity_score
from douyinhehe.downloader import parse_douyin_urls


def test_source_license_gate(tmp_path):
    db = Store(tmp_path / "test.db")
    grant = LicenseGrant("https://www.douyin.com/video/123", "Creator", "email-permission-42", True, True)
    sid = db.save_source(grant, "Gia dụng", 80)
    assert db.sources()[0]["id"] == sid
    assert "creator" not in db.sources()[0]
    with pytest.raises(ValueError, match="quyền"):
        db.save_source(LicenseGrant(grant.original_url, "Creator", "evidence", True, False))
    db.save_source(LicenseGrant(grant.original_url, "", "", True, True))


def test_affiliate_data(tmp_path):
    db = Store(tmp_path / "db.sqlite")
    product_id = db.save_product("Giá treo", "Nhà bếp", "https://shop.example/product?ref=123")
    db.record_results(product_id, 100, 5, 25_000)
    assert db.products()[0]["orders"] == 5
    assert Metrics(20_000, 50, 5, 25000).as_dict()["conversion_percent"] == 10
    with pytest.raises(ValueError):
        db.save_product("Fake", "x", "http://insecure.test")
    with pytest.raises(ValueError):
        db.record_results(product_id, 1, 4, 5)


def test_score_and_keywords():
    assert opportunity_score(100, 100, 100, 100, 100) == 100
    assert opportunity_score(0, 0, 0, 0, 0) == 0
    with pytest.raises(ValueError):
        opportunity_score(105, 0, 0, 0, 0)


def test_douyin_host_validator():
    text = "x https://v.douyin.com/abcd/ Y https://www.douyin.com/video/123)"
    assert len(parse_douyin_urls(text)) == 2
    for url in ("https://douyin.com.evil.site/a", "http://douyin.com/video/3", "https://evil.site/x"):
        with pytest.raises(ValueError):
            parse_douyin_urls(url)
