class TlckError(Exception):
    """Base exception for all tlck errors."""


class VaultError(TlckError):
    """Raised for vault-level failures (e.g. not initialized, locked)."""


class WrongPasswordError(VaultError):
    """Raised when the master password is incorrect."""


class ItemNotFoundError(TlckError):
    """Raised when a requested vault item does not exist."""
