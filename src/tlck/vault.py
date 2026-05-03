from __future__ import annotations

from collections.abc import Generator
import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .crypto import decrypt, derive_key, encrypt, generate_salt
from .exceptions import ItemNotFoundError, VaultError, WrongPasswordError
from .models import ITEM_CLASS_MAP, BaseItem, Category

logger = logging.getLogger(__name__)

_VERIFICATION_PLAINTEXT = "tlck-vault-v1"


class Vault:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._key: bytes | None = None
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vault_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id             TEXT PRIMARY KEY,
                    category       TEXT NOT NULL,
                    name           TEXT NOT NULL,
                    encrypted_data TEXT NOT NULL,
                    created_at     TEXT NOT NULL,
                    updated_at     TEXT NOT NULL
                )
            """)

    @property
    def is_initialized(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM vault_meta WHERE key = 'salt'"
            ).fetchone()
        return row is not None

    @property
    def is_unlocked(self) -> bool:
        return self._key is not None

    def setup(self, *, password: str) -> None:
        """Initialize the vault with a new master password. Call only once."""
        if self.is_initialized:
            raise VaultError("Vault is already initialized")
        salt = generate_salt()
        key = derive_key(password=password, salt=salt)
        verification_token = encrypt(data=_VERIFICATION_PLAINTEXT, key=key)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO vault_meta (key, value) VALUES ('salt', ?)",
                (salt.hex(),),
            )
            conn.execute(
                "INSERT INTO vault_meta (key, value) VALUES ('verification_token', ?)",
                (verification_token,),
            )
        self._key = key
        logger.info("Vault initialized")

    def unlock(self, *, password: str) -> None:
        """Unlock the vault. Raises WrongPasswordError on bad password."""
        with self._connect() as conn:
            salt_row = conn.execute(
                "SELECT value FROM vault_meta WHERE key = 'salt'"
            ).fetchone()
            if not salt_row:
                raise VaultError("Vault is not initialized")
            token_row = conn.execute(
                "SELECT value FROM vault_meta WHERE key = 'verification_token'"
            ).fetchone()

        salt = bytes.fromhex(salt_row["value"])
        key = derive_key(password=password, salt=salt)
        try:
            plaintext = decrypt(data=token_row["value"], key=key)
        except VaultError as e:
            raise WrongPasswordError("Incorrect master password") from e

        if plaintext != _VERIFICATION_PLAINTEXT:
            raise WrongPasswordError("Incorrect master password")

        self._key = key
        logger.info("Vault unlocked")

    def lock(self) -> None:
        self._key = None

    def _require_unlocked(self) -> bytes:
        if self._key is None:
            raise VaultError("Vault is locked")
        return self._key

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_item(self, *, category: Category, item: BaseItem) -> None:
        key = self._require_unlocked()
        encrypted = encrypt(data=json.dumps(asdict(item)), key=key)
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO items
                   (id, category, name, encrypted_data, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    item.id,
                    category.value,
                    item.name,
                    encrypted,
                    item.created_at,
                    item.updated_at,
                ),
            )
        logger.debug("Added item %s to %s", item.id, category)

    def update_item(self, *, category: Category, item: BaseItem) -> None:
        key = self._require_unlocked()
        item.updated_at = datetime.now(timezone.utc).isoformat()
        encrypted = encrypt(data=json.dumps(asdict(item)), key=key)
        with self._connect() as conn:
            result = conn.execute(
                """UPDATE items
                   SET name = ?, encrypted_data = ?, updated_at = ?
                   WHERE id = ? AND category = ?""",
                (item.name, encrypted, item.updated_at, item.id, category.value),
            )
        if result.rowcount == 0:
            raise ItemNotFoundError(f"Item {item.id!r} not found in {category}")
        logger.debug("Updated item %s in %s", item.id, category)

    def delete_item(self, *, item_id: str) -> None:
        self._require_unlocked()
        with self._connect() as conn:
            result = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        if result.rowcount == 0:
            raise ItemNotFoundError(f"Item {item_id!r} not found")
        logger.debug("Deleted item %s", item_id)

    def list_items(self, *, category: Category) -> list[BaseItem]:
        key = self._require_unlocked()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT encrypted_data FROM items WHERE category = ? ORDER BY name COLLATE NOCASE",
                (category.value,),
            ).fetchall()

        item_class = ITEM_CLASS_MAP[category]
        result: list[BaseItem] = []
        for row in rows:
            data = json.loads(decrypt(data=row["encrypted_data"], key=key))
            result.append(item_class(**data))
        return result

    def counts(self) -> dict[Category, int]:
        """Return item count per category. Does not require the vault to be unlocked."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM items GROUP BY category"
            ).fetchall()
        counts: dict[Category, int] = {cat: 0 for cat in Category}
        for row in rows:
            try:
                counts[Category(row["category"])] = row["cnt"]
            except ValueError:
                logger.warning("Unknown category %r in database", row["category"])
        return counts
