"""Subtitle readability checks and five-second local preview, with no cloud calls."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .media import _subtitle_filter, find_binary, probe_video
from .subtitles import Caption, parse_srt

_STAMP = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")


@dataclass(frozen=True)
class CaptionIssue:
    item: int
    kind: str
    detail: str
    severity: str = "warning"


def _ms(value: str) -> int:
    result = _STAMP.fullmatch(value)
    if not result:
        raise ValueError("Mốc thời gian phụ đề không đúng định dạng SRT.")
    hours, mins, secs, millis = map(int, result.groups())
    if mins >= 60 or secs >= 60:
        raise ValueError("Phụ đề có thời gian ngoài giới hạn.")
    return ((hours * 60 + mins) * 60 + secs) * 1000 + millis


def audit_captions(captions: list[Caption], *, max_chars: int = 42, max_cps: float = 20) -> list[CaptionIssue]:
    if not (10 <= max_chars <= 100 and 5 <= max_cps <= 50):
        raise ValueError("Giới hạn phụ đề không hợp lệ.")
    issues = []
    previous_end = 0
    for i, c in enumerate(captions, 1):
        stamps = re.split(r"\s*-->\s*", c.start_end)
        if len(stamps) != 2:
            raise ValueError("Phụ đề thiếu khoảng thời gian.")
        start, end = map(_ms, stamps)
        if end <= start:
            issues.append(CaptionIssue(i, "time", "Thời gian kết thúc phải lớn hơn bắt đầu.", "error"))
            continue
        if start < previous_end:
            issues.append(CaptionIssue(i, "overlap", "Phụ đề trùng khoảng thời gian.", "error"))
        previous_end = max(previous_end, end)
        lines = c.text.splitlines()
        if len(lines) > 2:
            issues.append(CaptionIssue(i, "lines", "Nên dùng tối đa 2 dòng mỗi caption."))
        for j, line in enumerate(lines, 1):
            if len(line.strip()) > max_chars:
                issues.append(CaptionIssue(i, "length", f"Dòng {j} dài {len(line.strip())} ký tự (giới hạn {max_chars})."))
        cps = sum(len(line.strip()) for line in lines) / ((end - start) / 1000)
        if cps > max_cps:
            issues.append(CaptionIssue(i, "reading_speed", f"Tốc độ đọc {cps:.1f} ký tự/giây (giới hạn {max_cps:g})."))
    return issues


def audit_srt(path: Path, *, max_chars: int = 42, max_cps: float = 20) -> list[CaptionIssue]:
    return audit_captions(parse_srt(Path(path).read_text(encoding="utf-8-sig")), max_chars=max_chars, max_cps=max_cps)


def preview_five_seconds(video: Path, subtitle: Path, dest: Path, *, start: float = 0) -> Path:
    """Create a <=5 sec clip for manual review, inside a user-selected output folder."""
    if start < 0:
        raise ValueError("Không được xem trước ở thời điểm âm.")
    issues = audit_srt(subtitle)
    if any(i.severity == "error" for i in issues):
        raise ValueError("Phụ đề có lỗi thời gian, cần sửa trước khi xem trước.")
    probe_video(video)
    target = Path(dest).resolve()
    if target in (Path(video).resolve(), Path(subtitle).resolve()):
        raise ValueError("File preview không được ghi đè nguồn.")
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [find_binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-ss", str(start),
           "-i", str(video), "-t", "5", "-vf", _subtitle_filter(subtitle),
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "25", "-c:a", "aac", str(target)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if result.returncode:
        target.unlink(missing_ok=True)
        raise RuntimeError("Không thể render xem trước: " + (result.stderr or "")[-700:])
    probe_video(target)
    return target
