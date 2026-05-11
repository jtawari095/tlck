from __future__ import annotations

import logging
from pathlib import Path
from typing import final

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .vault import Vault
from .window import TlckWindow

logger = logging.getLogger(__name__)

_APP_ID = "io.github.tlck"
_DATA_DIR = Path(GLib.get_user_data_dir()) / "tlck"
_DB_PATH = _DATA_DIR / "vault.db"

settings = Gtk.Settings.get_default()
settings.set_property("gtk-icon-theme-name", "Adwaita")


# Tlck app
@final
class TlckApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=_APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._vault = Vault(_DB_PATH)

    def do_activate(self) -> None:
        existing = self.get_active_window()
        if existing:
            existing.present()
            return

        window = TlckWindow(app=self, vault=self._vault)
        window.present()
