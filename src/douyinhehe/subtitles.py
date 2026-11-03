"""Transcript, SRT and Gemini translation with explicit free-tier user opt-in."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .core import Store

_SRT_TIME = re.compile(r"\d\d:\d\d:\d\d,\d{3}\s*-->\s*\d\d:\d\d:\d\d,\d{3}")


@dataclass(frozen=True)
class Caption:
    start_end: str
    text: str


def parse_srt(value: str) -> list[Caption]:
    entries: list[Caption] = []
    for block in re.split(r"\n\s*\n", value.strip().replace("\r\n", "\n")):
        lines = [x for x in block.split("\n") if x.strip()]
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        if len(lines) < 2 or not _SRT_TIME.fullmatch(lines[0].strip()):
            raise ValueError("Sai định dạng SRT tại: " + block[:80])
        entries.append(Caption(lines[0].strip(), "\n".join(lines[1:]).strip()))
    return entries


def write_srt(captions: list[Caption], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(f"{i}\n{c.start_end}\n{c.text}" for i, c in enumerate(captions, 1)) + "\n",
                    encoding="utf-8")


def transcribe_to_srt(source: Path, target: Path, *, model_name: str = "small",
                      device: str = "cpu") -> Path:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Thiếu faster-whisper; cài extra [asr].") from exc
    model = WhisperModel(model_name, device=device, compute_type="int8" if device == "cpu" else "float16")
    segments, _ = model.transcribe(str(source), language="zh", vad_filter=True, beam_size=5)

    def tc(sec: float) -> str:
        milliseconds = round(sec * 1000)
        hh, remain = divmod(milliseconds, 3600_000)
        mm, remain = divmod(remain, 60_000)
        ss, ms = divmod(remain, 1000)
        return f"{hh:02}:{mm:02}:{ss:02},{ms:03}"

    captions = [Caption(f"{tc(s.start)} --> {tc(s.end)}", s.text.strip()) for s in segments if s.text.strip()]
    if not captions:
        raise ValueError("Không nhận dạng được lời nói tiếng Trung.")
    write_srt(captions, Path(target))
    return Path(target)


def translate_srt(source: Path, target: Path, store: Store, *, api_key: str,
                  model_name: str, confirmed_free_tier: bool) -> Path:
    """Sends text only to Gemini. No paid fallback, no model auto-switching."""
    if not confirmed_free_tier:
        raise PermissionError("Bạn phải xác nhận API project đang ở Free Tier trước khi gọi Gemini.")
    if not api_key.strip() or not model_name.strip():
        raise ValueError("Cần Gemini API key và model cụ thể.")
    entries = parse_srt(Path(source).read_text(encoding="utf-8-sig"))
    if not entries:
        raise ValueError("SRT rỗng.")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("Thiếu google-genai; cài extra [gemini].") from exc
    output: list[Caption] = []
    client = genai.Client(api_key=api_key)
    try:
        for index in range(0, len(entries), 16):
            batch = entries[index:index + 16]
            key = hashlib.sha256(json.dumps({"m": model_name, "lines": [c.text for c in batch]},
                                                ensure_ascii=False).encode("utf-8")).hexdigest()
            cached = store.cache_get(key)
            if cached:
                translated = json.loads(cached)
            else:
                prompt = ("Dịch các câu thoại tiếng Trung sau sang tiếng Việt tự nhiên, rõ ràng cho phụ đề sản phẩm. "
                          "Không thêm lời quảng cáo, không thay đổi tên sản phẩm, không thêm nội dung. "
                          "Trả về MỘT JSON array các chuỗi tiếng Việt, đúng thứ tự, đúng số lượng.\n"
                          + json.dumps([c.text for c in batch], ensure_ascii=False))
                try:
                    response = client.models.generate_content(model=model_name, contents=prompt)
                except Exception as exc:
                    # Never automatically choose a different model or paid tier.
                    raise RuntimeError("Gemini lỗi/hết quota. Đã dừng, không tự đổi model hoặc sử dụng bản trả phí. "
                                       + type(exc).__name__) from exc
                raw = (response.text or "").strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
                translated = json.loads(raw)
                if not isinstance(translated, list) or len(translated) != len(batch) or not all(
                    isinstance(x, str) and x.strip() for x in translated
                ):
                    raise ValueError("Gemini trả dữ liệu phụ đề không đúng cấu trúc, đã dừng.")
                store.cache_set(key, json.dumps(translated, ensure_ascii=False))
            output.extend(Caption(c.start_end, tr.strip()) for c, tr in zip(batch, translated))
    finally:
        client.close()
    write_srt(output, Path(target))
    return Path(target)


def text_to_voice(text: str, target: Path, *, voice_id: str = "") -> Path:
    """Offline Windows SAPI TTS; requires a Vietnamese voice installed by the user."""
    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError("Thiếu pyttsx3; cài extra [tts].") from exc
    if not text.strip():
        raise ValueError("Không có nội dung để đọc.")
    engine = pyttsx3.init()
    if voice_id:
        voices = {voice.id: voice for voice in engine.getProperty("voices")}
        if voice_id not in voices:
            raise ValueError("Không tìm thấy giọng đã chọn.")
        engine.setProperty("voice", voice_id)
    else:
        voices = list(engine.getProperty("voices"))
        vietnamese = [v for v in voices if "vi" in str(getattr(v, "languages", "")).lower() or
                      "vietnam" in v.name.lower()]
        if not vietnamese:
            raise RuntimeError("Windows chưa cài giọng đọc tiếng Việt. Không tự chọn giọng sai ngôn ngữ.")
        engine.setProperty("voice", vietnamese[0].id)
    target.parent.mkdir(parents=True, exist_ok=True)
    engine.save_to_file(text, str(target))
    engine.runAndWait()
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError("TTS không tạo được file âm thanh.")
    return target
