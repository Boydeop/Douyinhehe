"""Postiz publisher: real upload/scheduling using documented public API."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def validate_postiz_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Postiz API URL phải dùng HTTPS và không chứa tài khoản, query hoặc fragment.")
    return url


def schedule_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Thời gian lên lịch cần múi giờ xác định.")
    if value <= datetime.now(timezone.utc):
        raise ValueError("Lịch đăng phải trong tương lai.")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class PostizClient:
    def __init__(self, api_key: str, base_url: str = "https://api.postiz.com", *, transport=None):
        if not api_key.strip():
            raise ValueError("Cần API key của Postiz.")
        self.base_url = validate_postiz_url(base_url)
        self.client = httpx.Client(base_url=self.base_url, timeout=120,
                                   headers={"Authorization": api_key.strip()},
                                   follow_redirects=False, transport=transport)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.client.close()

    def integrations(self) -> list[dict]:
        resp = self.client.get("/public/v1/integrations")
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("integrations", "data"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        raise ValueError("Postiz trả định dạng danh sách tích hợp không xác định.")

    def upload(self, video_path: Path) -> dict:
        file = Path(video_path)
        if not file.is_file() or file.suffix.lower() not in {".mp4", ".mov"}:
            raise ValueError("Chỉ được tải lên file video MP4/MOV có thật.")
        with file.open("rb") as stream:
            response = self.client.post("/public/v1/upload", files={"file": (file.name, stream, "video/mp4")})
        response.raise_for_status()
        media = response.json()
        if not isinstance(media, dict) or not media.get("id") or not media.get("path"):
            raise ValueError("Postiz không trả về id/path của video đã upload.")
        return {"id": media["id"], "path": media["path"]}

    def schedule(self, video_path: Path, scheduled: datetime, integrations: list[dict],
                 caption: str) -> dict:
        """A single user-approved batch request. Provider-specific settings remain explicit."""
        if not integrations:
            raise ValueError("Phải chọn ít nhất một kênh đích.")
        if not caption.strip():
            raise ValueError("Cần mô tả bài đăng (bao gồm nguồn tác giả).")
        when = schedule_timestamp(scheduled)
        if not Path(video_path).is_file():
            raise FileNotFoundError(video_path)
        posts = []
        seen = set()
        for entry in integrations:
            integration_id = entry.get("id")
            provider = entry.get("provider")
            settings = entry.get("settings")
            if not integration_id or not isinstance(provider, str) or not provider.strip():
                raise ValueError("Thiếu integration id hoặc provider.")
            if not isinstance(settings, dict):
                raise ValueError("Cần cấu hình provider từ Postiz; không tự đoán quyền/API.")
            if integration_id in seen:
                continue
            seen.add(integration_id)
            if settings.get("__type") != provider:
                raise ValueError("settings.__type phải trùng provider.")
            posts.append({"integration": {"id": integration_id},
                          "value": [{"content": caption.strip(), "image": []}],
                          "settings": settings})
        media = self.upload(video_path)
        for post in posts:
            post["value"][0]["image"] = [media]
        payload = {"type": "schedule", "date": when, "shortLink": False, "tags": [], "posts": posts}
        response = self.client.post("/public/v1/posts", json=payload, timeout=90)
        response.raise_for_status()
        body = response.json()
        return {"response": body, "scheduled_at": when, "target_count": len(posts)}
