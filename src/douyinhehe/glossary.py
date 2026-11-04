"""Per-niche Chinese-Vietnamese terms, deterministically validated and versioned."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .core import user_data_dir

DEFAULT_GLOSSARIES = {
    "Gia dụng": {"收纳": "sắp xếp và lưu trữ", "折叠": "gấp gọn", "防滑": "chống trượt", "厨房": "nhà bếp"},
    "Mỹ phẩm": {"遮瑕": "che khuyết điểm", "保湿": "dưỡng ẩm", "防晒": "chống nắng", "卸妆": "tẩy trang"},
    "Nhà bếp": {"保鲜": "bảo quản tươi", "沥水": "để ráo nước", "砧板": "thớt"},
}


def validate_glossary(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or len(value) > 100:
        raise ValueError("Glossary phải là JSON object, tối đa 100 thuật ngữ.")
    output = {}
    for source, target in value.items():
        if (not isinstance(source, str) or not isinstance(target, str)
                or not 1 <= len(source.strip()) <= 80 or not 1 <= len(target.strip()) <= 120):
            raise ValueError("Mỗi thuật ngữ phải có cặp văn bản Trung - Việt hợp lệ.")
        output[source.strip()] = target.strip()
    return dict(sorted(output.items()))


def glossary_path(niche: str) -> Path:
    if not re.fullmatch(r"[\w À-ỹ-]{1,60}", niche):
        raise ValueError("Tên ngách không hợp lệ.")
    return user_data_dir() / "glossaries" / (niche + ".json")


def load_glossary(niche: str) -> dict[str, str]:
    path = glossary_path(niche)
    if path.exists():
        return validate_glossary(json.loads(path.read_text(encoding="utf-8")))
    return validate_glossary(DEFAULT_GLOSSARIES.get(niche, {}))


def save_glossary(niche: str, value: dict[str, str]) -> Path:
    terms = validate_glossary(value)
    path = glossary_path(niche)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(terms, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path
