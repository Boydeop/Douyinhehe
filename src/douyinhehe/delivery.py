"""Conservative video preflight and per-platform attribution suggestions.

Not a platform approval oracle. Social platforms change acceptance policies;
this code only checks media invariants and supplies human-facing guidance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .media import probe_video


@dataclass(frozen=True)
class Destination:
    name: str
    label: str
    cta_hint: str
    oauth_required: bool = True


DESTINATIONS: dict[str, Destination] = {
    "facebook": Destination("facebook", "Facebook Reels", "Link sản phẩm trên Page / nội dung được phép"),
    "tiktok": Destination("tiktok", "TikTok", "Link ở vị trí được hỗ trợ theo tài khoản"),
    "youtube": Destination("youtube", "YouTube Shorts", "Xem link sản phẩm trên trang kênh"),
    "instagram": Destination("instagram", "Instagram Reels", "Xem link trong bio / tính năng sản phẩm nếu có"),
    "threads": Destination("threads", "Threads", "Link trên bài đăng hoặc hồ sơ nếu được hỗ trợ"),
}


def credit_text(creator: str, original_url: str, *, affiliate: bool = True) -> str:
    if not creator.strip() or not original_url.strip():
        raise ValueError("Phải có tác giả và URL gốc để ghi nguồn.")
    disclosure = "\nLiên kết sản phẩm có thể mang lại hoa hồng cho kênh." if affiliate else ""
    return f"Nguồn video (sử dụng theo giấy phép): {creator.strip()}\nVideo gốc: {original_url.strip()}{disclosure}"


def delivery_preflight(path: Path, *, credit: str, platform: str = "youtube") -> dict:
    """Inspect technical fitness, not copyright ownership or API eligibility."""
    if platform not in DESTINATIONS:
        raise ValueError("Nền tảng đích không được hỗ trợ.")
    meta = probe_video(path)
    videos = [s for s in meta["streams"] if s.get("codec_type") == "video"]
    stream = videos[0]
    width, height = int(stream.get("width") or 0), int(stream.get("height") or 0)
    codec = str(stream.get("codec_name") or "")
    warnings = []
    if width < 720 or height < 1280:
        warnings.append("Độ phân giải thấp hơn mức 720 × 1280 khuyến nghị cho video dọc.")
    if width >= height:
        warnings.append("Video không theo chiều dọc; nên kiểm tra crop/pad 9:16.")
    if width * 16 != height * 9:
        warnings.append("Khung hình khác 9:16; xem lại vùng an toàn cho CTA/phụ đề.")
    if codec != "h264":
        warnings.append("Đề xuất xuất MP4 H.264 để tăng tính tương thích.")
    if "nguồn" not in credit.lower() and "source" not in credit.lower():
        warnings.append("Mô tả chưa ghi rõ nguồn tác giả.")
    if "hoa hồng" not in credit.lower() and "affiliate" not in credit.lower():
        warnings.append("Kiểm tra yêu cầu công khai tiếp thị liên kết của nền tảng.")
    return {
        "platform": platform, "label": DESTINATIONS[platform].label,
        "width": width, "height": height, "video_codec": codec,
        "duration_seconds": float(meta.get("format", {}).get("duration") or 0),
        "warnings": warnings,
        "cta_hint": DESTINATIONS[platform].cta_hint,
        "note": "Chỉ kiểm tra file và gợi ý CTA; không bảo đảm quyền đăng hay được phân phối.",
    }
