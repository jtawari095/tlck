from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GObject, Gtk  # noqa: E402

from ..exceptions import WrongPasswordError
from ..vault import Vault

logger = logging.getLogger(__name__)


class UnlockDialog(Adw.Dialog):
    """
    Handles both first-run vault setup and subsequent unlock.

    Emits 'vault-unlocked' after a successful setup or unlock.
    """

    __gsignals__: dict = {
        "vault-unlocked": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, vault: Vault) -> None:
        super().__init__()
        self._vault = vault
        self._is_setup = not vault.is_initialized

        self.set_content_width(400)
        self.set_follows_content_size(True)
        self.set_can_close(False)

        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_back_button(False)
        toolbar_view.add_top_bar(header)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(360)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(24)
        clamp.set_margin_end(24)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)

        # Icon + headline
        icon = Gtk.Image.new_from_icon_name("dialog-password-symbolic")
        icon.set_pixel_size(64)
        icon.add_css_class("accent")
        box.append(icon)

        if self._is_setup:
            title = "Create Master Password"
            subtitle = "This password encrypts all your secrets.\nThere is no way to recover it if lost."
        else:
            title = "Unlock Vault"
            subtitle = "Enter your master password to continue."

        title_label = Gtk.Label(label=title)
        title_label.add_css_class("title-1")
        title_label.set_wrap(True)
        title_label.set_justify(Gtk.Justification.CENTER)
        box.append(title_label)

        subtitle_label = Gtk.Label(label=subtitle)
        subtitle_label.add_css_class("body")
        subtitle_label.add_css_class("dim-label")
        subtitle_label.set_wrap(True)
        subtitle_label.set_justify(Gtk.Justification.CENTER)
        box.append(subtitle_label)

        # Form group
        group = Adw.PreferencesGroup()
        self._password_row = Adw.PasswordEntryRow(title="Master Password")
        self._password_row.connect("entry-activated", self._on_submit)
        group.add(self._password_row)

        if self._is_setup:
            self._confirm_row = Adw.PasswordEntryRow(title="Confirm Password")
            self._confirm_row.connect("entry-activated", self._on_submit)
            group.add(self._confirm_row)
        else:
            self._confirm_row = None

        box.append(group)

        # Error label
        self._error_label = Gtk.Label()
        self._error_label.add_css_class("error")
        self._error_label.set_visible(False)
        self._error_label.set_wrap(True)
        self._error_label.set_justify(Gtk.Justification.CENTER)
        box.append(self._error_label)

        # Submit button
        action_label = "Create Vault" if self._is_setup else "Unlock"
        self._submit_btn = Gtk.Button(label=action_label)
        self._submit_btn.add_css_class("pill")
        self._submit_btn.add_css_class("suggested-action")
        self._submit_btn.connect("clicked", self._on_submit)
        box.append(self._submit_btn)

        clamp.set_child(box)
        toolbar_view.set_content(clamp)
        self.set_child(toolbar_view)

        self._password_row.grab_focus()

    def _show_error(self, message: str) -> None:
        self._error_label.set_text(message)
        self._error_label.set_visible(True)

    def _clear_error(self) -> None:
        self._error_label.set_visible(False)

    def _on_submit(self, *_args: object) -> None:
        self._clear_error()
        password = self._password_row.get_text()

        if not password:
            self._show_error("Password cannot be empty.")
            return

        if self._is_setup:
            confirm = self._confirm_row.get_text() if self._confirm_row else ""
            if password != confirm:
                self._show_error("Passwords do not match.")
                return
            if len(password) < 8:
                self._show_error("Password must be at least 8 characters.")
                return
            self._vault.setup(password=password)
            self.emit("vault-unlocked")
            self.force_close()
        else:
            try:
                self._vault.unlock(password=password)
            except WrongPasswordError:
                self._show_error("Incorrect password. Try again.")
                self._password_row.set_text("")
                self._password_row.grab_focus()
                return
            self.emit("vault-unlocked")
            self.force_close()
