"""Structured, rotating local event log with secret-safe export."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .core import user_data_dir

_LOG_MAX_BYTES = 2 * 1024 * 1024
_PATTERNS = (
    (re.compile(r"(?im)(?:cookie|set-cookie)\\s*:\\s*[^\\r\\n]+"), "[REDACTED_COOKIE_HEADER]"),
    (re.compile(r"(?i)((?:msToken|sessionid|sid_tt|ttwid|a_bogus|x-bogus)\\s*[:=]\\s*)[^\\s&,;]{5,}"), r"\\1[REDACTED]"),
    (re.compile(r"AIza[0-9A-Za-z_-]{20,}"), "[REDACTED_GEMINI_KEY]"),
    (re.compile(r"(?i)(bearer\s+)[0-9a-z_.~+/-]{8,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*)[\"']?[^\s,;\"']{5,}"), r"\1[REDACTED]"),
)


def redact(message: str, secrets: tuple[str, ...] = ()) -> str:
    sanitized = str(message)
    for secret in secrets:
        if len(secret) >= 5:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    for pattern, replacement in _PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def log_path() -> Path:
    return user_data_dir() / "logs" / "events.jsonl"


def write_event(event: str, message: str) -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > _LOG_MAX_BYTES:
        rotated = path.with_suffix(".previous.jsonl")
        rotated.unlink(missing_ok=True)
        path.replace(rotated)
    entry = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "event": redact(event)[:60], "message": redact(message)[:1200]}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def export_redacted_logs(target: Path) -> Path:
    if target.suffix.lower() != ".jsonl":
        raise ValueError("Đường dẫn xuất log phải kết thúc bằng .jsonl")
    target.parent.mkdir(parents=True, exist_ok=True)
    original = log_path()
    if target.resolve() == original.resolve():
        raise ValueError("Không được ghi đè nhật ký gốc khi xuất log.")
    if not original.exists():
        raise FileNotFoundError("Chưa có log để xuất.")
    # Re-scrub all existing log entries, including entries from older app versions.
    with original.open("r", encoding="utf-8") as src, target.open("w", encoding="utf-8") as dst:
        for line in src:
            dst.write(redact(line))
    return target
