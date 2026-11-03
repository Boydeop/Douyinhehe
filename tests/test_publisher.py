import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from douyinhehe.publisher import PostizClient, validate_postiz_url


def test_postiz_schedule_and_upload(tmp_path):
    actions = []

    def handler(request):
        actions.append((request.method, request.url.path))
        if request.url.path.endswith("/integrations"):
            return httpx.Response(200, json=[{"id": "ig123", "identifier": "instagram"}])
        if request.url.path.endswith("/upload"):
            assert b"file" in request.content
            return httpx.Response(200, json={"id": "file123", "path": "https://uploads.postiz.com/a.mp4"})
        assert request.url.path.endswith("/posts")
        payload = json.loads(request.content)
        assert payload["type"] == "schedule"
        assert payload["posts"][0]["value"][0]["image"][0]["id"] == "file123"
        return httpx.Response(200, json={"id": "scheduled123"})

    media = tmp_path / "video.mp4"
    media.write_bytes(b"fake-video")
    with PostizClient("secret", transport=httpx.MockTransport(handler)) as client:
        assert len(client.integrations()) == 1
        done = client.schedule(media, datetime.now(timezone.utc) + timedelta(days=1),
                               [{"id": "ig123", "provider": "instagram", "settings": {"__type": "instagram"}}],
                               "Nguồn: tác giả Douyin")
        assert done["target_count"] == 1
    assert len(actions) == 3


def test_provider_validation(tmp_path):
    with pytest.raises(ValueError):
        validate_postiz_url("http://api.postiz.com")
    with pytest.raises(ValueError):
        PostizClient(" ")
    (tmp_path / "x.mp4").write_bytes(b"test")
    with pytest.raises(ValueError):
        with PostizClient("abc", transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client:
            client.schedule(tmp_path / "x.mp4", datetime.now(timezone.utc) + timedelta(days=1),
                            [{"id": "a", "provider": "tiktok", "settings": {}}], "Nguồn A")
