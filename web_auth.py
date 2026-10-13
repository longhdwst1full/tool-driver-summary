"""Single-account HTTP authentication for a private HTTPS reverse proxy."""

from __future__ import annotations

import argparse
import base64
import binascii
from getpass import getpass
from hashlib import scrypt
import os
import secrets


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 12:
        raise ValueError("Mật khẩu cần ít nhất 12 ký tự")
    salt = salt or secrets.token_bytes(16)
    digest = scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, expected_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(expected_hex)
        actual = scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def authorized(header: str | None) -> bool:
    encoded = os.environ.get("WEB_PASSWORD_HASH")
    if not encoded:
        return True
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return False
    return (secrets.compare_digest(username, os.environ.get("WEB_USERNAME", "admin"))
            and verify_password(password, encoded))


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo hash mật khẩu cho Drive Studio")
    parser.add_argument("command", choices=["hash"])
    parser.parse_args()
    password = getpass("Mật khẩu mới (ít nhất 12 ký tự): ")
    confirm = getpass("Nhập lại mật khẩu: ")
    if password != confirm:
        raise SystemExit("Hai mật khẩu không khớp")
    print(hash_password(password))


if __name__ == "__main__":
    main()
