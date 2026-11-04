"""Replaceable local text-to-speech engines (SAPI/pyttsx3 and Piper)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class TTSEngine(Protocol):
    def synthesize(self, text: str, target: Path) -> Path: ...


@dataclass
class SystemVoice:
    voice_id: str = ""

    def synthesize(self, text: str, target: Path) -> Path:
        from .subtitles import text_to_voice
        return text_to_voice(text, target, voice_id=self.voice_id)


@dataclass
class PiperVoice:
    executable: Path
    model: Path

    def synthesize(self, text: str, target: Path) -> Path:
        if not text.strip() or not self.executable.is_file() or not self.model.is_file():
            raise ValueError("Piper cần văn bản, tệp piper.exe và model giọng đọc hợp lệ.")
        if target.suffix.lower() != ".wav":
            raise ValueError("Piper chỉ xuất giọng đọc WAV.")
        target.parent.mkdir(parents=True, exist_ok=True)
        command = [str(self.executable), "--model", str(self.model), "--output_file", str(target)]
        proc = subprocess.run(command, input=text, text=True, capture_output=True, timeout=180, check=False)
        if proc.returncode or not target.is_file() or target.stat().st_size == 0:
            target.unlink(missing_ok=True)
            raise RuntimeError("Piper không tạo được giọng đọc: " + proc.stderr[-600:])
        return target


def get_tts_engine(name: str, *, voice_id: str = "", piper_exe: Path | None = None,
                   piper_model: Path | None = None) -> TTSEngine:
    if name == "system":
        return SystemVoice(voice_id)
    if name == "piper" and piper_exe and piper_model:
        return PiperVoice(piper_exe, piper_model)
    raise ValueError("Engine TTS chưa được cấu hình. Không tự động chuyển sang API trả phí.")
