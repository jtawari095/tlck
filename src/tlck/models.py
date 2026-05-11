from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class Category(StrEnum):
    LOGINS = "logins"
    CREDIT_CARDS = "credit_cards"
    ADDRESSES = "addresses"
    SSH_KEYS = "ssh_keys"
    SECURE_NOTES = "secure_notes"


CATEGORY_LABELS: dict[Category, str] = {
    Category.LOGINS: "Logins",
    Category.CREDIT_CARDS: "Credit Cards",
    Category.ADDRESSES: "Addresses",
    Category.SSH_KEYS: "SSH Keys",
    Category.SECURE_NOTES: "Notes",
}

CATEGORY_ICONS: dict[Category, str] = {
    Category.LOGINS: "dialog-password-symbolic",
    Category.CREDIT_CARDS: "dialog-password-symbolic",
    Category.ADDRESSES: "user-home-symbolic",
    Category.SSH_KEYS: "utilities-terminal-symbolic",
    Category.SECURE_NOTES: "document-edit-symbolic",
}


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BaseItem:
    id: str = field(default_factory=_new_id)
    name: str = ""
    notes: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def subtitle(self) -> str:
        return ""


@dataclass
class Login(BaseItem):
    username: str = ""
    email: str = ""
    password: str = ""
    url: str = ""
    totp_secret: str = ""

    def subtitle(self) -> str:
        return self.username or self.email or self.url


@dataclass
class CreditCard(BaseItem):
    cardholder_name: str = ""
    card_number: str = ""
    expiry_month: str = ""
    expiry_year: str = ""
    cvv: str = ""
    pin: str = ""
    card_type: str = ""

    def subtitle(self) -> str:
        if self.card_number and len(self.card_number) >= 4:
            return f"•••• {self.card_number[-4:]}"
        return self.cardholder_name


@dataclass
class Address(BaseItem):
    full_name: str = ""
    company: str = ""
    street1: str = ""
    street2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    phone: str = ""
    email: str = ""

    def subtitle(self) -> str:
        parts = [p for p in (self.city, self.state, self.country) if p]
        return ", ".join(parts)


@dataclass
class SSHKey(BaseItem):
    private_key: str = ""
    public_key: str = ""
    passphrase: str = ""
    fingerprint: str = ""
    key_type: str = ""

    def subtitle(self) -> str:
        parts = [p for p in (self.key_type, self.fingerprint) if p]
        return " ".join(parts) if parts else "SSH Key"


@dataclass
class SecureNote(BaseItem):
    content: str = ""

    def subtitle(self) -> str:
        first_line = self.content.strip().split("\n")[0] if self.content.strip() else ""
        return first_line[:60]


ITEM_CLASS_MAP: dict[Category, type[BaseItem]] = {
    Category.LOGINS: Login,
    Category.CREDIT_CARDS: CreditCard,
    Category.ADDRESSES: Address,
    Category.SSH_KEYS: SSHKey,
    Category.SECURE_NOTES: SecureNote,
}
