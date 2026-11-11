"""Ensure Windows uninstaller never recursively deletes user-created files."""
from scripts.generate_uninstall_manifest import generate


def test_generated_uninstall_script_targets_only_package_files(tmp_path):
    root = tmp_path / "dist" / "DouyinhehePro"
    (root / "bin").mkdir(parents=True)
    (root / "DouyinhehePro.exe").write_bytes(b"app")
    (root / "bin" / "ffmpeg.exe").write_bytes(b"ffmpeg")
    output = tmp_path / "manifest.nsh"
    generate(root, output)
    source = output.read_text("utf-8")
    assert 'Delete "$INSTDIR\\DouyinhehePro.exe"' in source
    assert 'Delete "$INSTDIR\\bin\\ffmpeg.exe"' in source
    assert 'RMDir "$INSTDIR\\bin"' in source
    assert "RMDir /r" not in source


def test_manifest_rejects_malformed_package_path(tmp_path):
    import pytest

    root = tmp_path / "dist"
    root.mkdir()
    with pytest.raises(ValueError, match="Thiếu thư mục"):
        generate(root, tmp_path / "manifest.nsh")
