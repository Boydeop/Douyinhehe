"""API keys stored in the OS credential manager, never in the repository or SQLite."""

from __future__ import annotations

SERVICE = "DouyinhehePro"


def save_secret(name: str, value: str) -> None:
    import keyring

    if not name or not value.strip():
        raise ValueError("Cần tên và giá trị khóa.")
    keyring.set_password(SERVICE, name, value.strip())


def get_secret(name: str) -> str:
    import keyring

    return keyring.get_password(SERVICE, name) or ""


def delete_secret(name: str) -> None:
    import keyring

    try:
        keyring.delete_password(SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass
