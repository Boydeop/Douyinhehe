"""Produce a least-destructive NSIS uninstall manifest from the packaged folder.

Uninstaller removes only binaries installed by this build; user-added files and
local app data are never recursively deleted. Run after PyInstaller packaging.
"""
from __future__ import annotations

import sys
from pathlib import Path


def generate(source: Path, dest: Path) -> None:
    folder = source.resolve()
    if not folder.is_dir() or not (folder / "DouyinhehePro.exe").is_file():
        raise ValueError("Thiếu thư mục ứng dụng đã đóng gói.")
    files = sorted(path.relative_to(folder) for path in folder.rglob("*") if path.is_file())
    dirs = sorted((path.relative_to(folder) for path in folder.rglob("*") if path.is_dir()),
                  key=lambda item: (len(item.parts), str(item)), reverse=True)
    if len(files) > 50000:
        raise ValueError("Số lượng tệp đóng gói bất thường.")
    lines = ["; Auto-generated, remove only package-owned files and directories."]
    for path in files:
        relative = str(path).replace("/", "\\")
        if any(char in relative for char in ('"', '$', '\n', '\r')):
            raise ValueError("Đường dẫn đóng gói không an toàn cho NSIS.")
        lines.append(f'  Delete "$INSTDIR\\{relative}"')
    for path in dirs:
        relative = str(path).replace("/", "\\")
        lines.append(f'  RMDir "$INSTDIR\\{relative}"')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: generate_uninstall_manifest.py SOURCE_DIR OUT.nsh")
    generate(Path(sys.argv[1]), Path(sys.argv[2]))
