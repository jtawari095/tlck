from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .exceptions import VaultError

_PBKDF2_ITERATIONS = 600_000


def generate_salt() -> bytes:
    return os.urandom(32)


def derive_key(*, password: str, salt: bytes) -> bytes:
    """Derive a Fernet-compatible key from a password and salt using PBKDF2-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def encrypt(*, data: str, key: bytes) -> str:
    return Fernet(key).encrypt(data.encode()).decode()


def decrypt(*, data: str, key: bytes) -> str:
    try:
        return Fernet(key).decrypt(data.encode()).decode()
    except InvalidToken as e:
        raise VaultError("Decryption failed — corrupted data or wrong key") from e
