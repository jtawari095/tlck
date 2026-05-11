"""
Item CRUD dialogs for all vault categories.

Each dialog class accepts an optional item for editing (None means new item).
It emits:
  - 'item-saved'   with the (possibly new) BaseItem instance
  - 'item-deleted' with the item id string (only when editing)
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, GObject, Gtk  # noqa: E402

from ..models import (
    Address,
    BaseItem,
    CreditCard,
    Login,
    SecureNote,
    SSHKey,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _entry_row(title: str, text: str = "", *, placeholder: str = "") -> Adw.EntryRow:
    row = Adw.EntryRow(title=title)
    row.set_text(text)
    if placeholder:
        row.set_show_apply_button(False)
    return row


def _password_row(title: str, text: str = "") -> Adw.PasswordEntryRow:
    row = Adw.PasswordEntryRow(title=title)
    row.set_text(text)
    return row


def _copy_button(tooltip: str) -> Gtk.Button:
    btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
    btn.set_tooltip_text(tooltip)
    btn.set_valign(Gtk.Align.CENTER)
    btn.add_css_class("flat")
    return btn


def _copy_to_clipboard(widget: Gtk.Widget, text: str) -> None:
    display = Gdk.Display.get_default()
    if display:
        display.get_clipboard().set(text)
    _show_toast(widget, "Copied to clipboard")


def _show_toast(widget: Gtk.Widget, message: str) -> None:
    ancestor = widget.get_ancestor(Adw.ToastOverlay)
    if isinstance(ancestor, Adw.ToastOverlay):
        ancestor.add_toast(Adw.Toast.new(message))


def _make_text_row(
    label: str, text: str = "", *, monospace: bool = False, height: int = 80
) -> tuple[Adw.PreferencesRow, Gtk.TextView]:
    """A PreferencesRow containing a multi-line TextView."""
    row = Adw.PreferencesRow()
    row.set_activatable(False)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    outer.set_margin_top(8)
    outer.set_margin_bottom(8)
    outer.set_margin_start(12)
    outer.set_margin_end(12)

    lbl = Gtk.Label(label=label, xalign=0)
    lbl.add_css_class("caption")
    lbl.add_css_class("dim-label")
    outer.append(lbl)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scroll.set_min_content_height(height)

    tv = Gtk.TextView()
    tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    tv.set_top_margin(6)
    tv.set_bottom_margin(6)
    tv.set_left_margin(6)
    tv.set_right_margin(6)
    if monospace:
        tv.set_monospace(True)
    if text:
        tv.get_buffer().set_text(text)

    scroll.set_child(tv)
    scroll.add_css_class("card")
    outer.append(scroll)

    row.set_child(outer)
    return row, tv


# ── Base dialog ───────────────────────────────────────────────────────────────


class _BaseItemDialog(Adw.Dialog):
    __gsignals__: dict = {
        "item-saved": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "item-deleted": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    _item: BaseItem | None

    def __init__(
        self,
        *,
        title: str,
        item: BaseItem | None = None,
        content_width: int = 500,
    ) -> None:
        super().__init__()
        self._item = item
        self._editing = item is not None

        self.set_content_width(content_width)
        self.set_content_height(600)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_back_button(False)

        heading = Gtk.Label(label=title)
        heading.add_css_class("heading")
        header.set_title_widget(heading)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_btn)

        self._save_btn = Gtk.Button(label="Save")
        self._save_btn.add_css_class("suggested-action")
        self._save_btn.connect("clicked", self._on_save_clicked)
        header.pack_end(self._save_btn)

        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(480)

        inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        inner_box.set_margin_top(16)
        inner_box.set_margin_bottom(16)
        inner_box.set_margin_start(12)
        inner_box.set_margin_end(12)

        self._build_form(inner_box)

        if self._editing:
            delete_btn = Gtk.Button(label="Delete Item")
            delete_btn.add_css_class("destructive-action")
            delete_btn.add_css_class("pill")
            delete_btn.set_margin_top(8)
            delete_btn.connect("clicked", self._on_delete_clicked)
            inner_box.append(delete_btn)

        clamp.set_child(inner_box)
        scroll.set_child(clamp)
        toolbar_view.set_content(scroll)
        self.set_child(toolbar_view)

    def _build_form(self, container: Gtk.Box) -> None:
        """Subclasses override this to populate the form."""
        raise NotImplementedError

    def _collect_item(self) -> BaseItem:
        """Subclasses return the (new or updated) item from form state."""
        raise NotImplementedError

    def _on_save_clicked(self, _btn: Gtk.Button) -> None:
        item = self._collect_item()
        if not item.name.strip():
            _show_toast(self._save_btn, "Name is required")
            return
        self.emit("item-saved", item)
        self.close()

    def _on_delete_clicked(self, _btn: Gtk.Button) -> None:
        assert self._item is not None
        confirm = Adw.AlertDialog.new(
            "Delete Item?",
            f'"{self._item.name}" will be permanently deleted.',
        )
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("delete", "Delete")
        confirm.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        confirm.set_default_response("cancel")
        confirm.set_close_response("cancel")
        confirm.connect("response", self._on_delete_response)
        confirm.present(self)

    def _on_delete_response(self, _dialog: Adw.AlertDialog, response: str) -> None:
        if response == "delete" and self._item is not None:
            self.emit("item-deleted", self._item.id)
            self.close()

    @staticmethod
    def _add_copy_suffix(row: Adw.EntryRow | Adw.PasswordEntryRow) -> None:
        btn = _copy_button("Copy")
        btn.connect(
            "clicked",
            lambda _: _copy_to_clipboard(row, row.get_text()),
        )
        row.add_suffix(btn)

    @staticmethod
    def _notes_group(notes: str) -> tuple[Adw.PreferencesGroup, Gtk.TextView]:
        group = Adw.PreferencesGroup(title="Notes")
        row, tv = _make_text_row("Notes", notes)
        group.add(row)
        return group, tv


# ── Login dialog ──────────────────────────────────────────────────────────────


class LoginDialog(_BaseItemDialog):
    def __init__(self, item: Login | None = None) -> None:
        self._login = item
        title = "Edit Login" if item else "New Login"
        super().__init__(title=title, item=item)

    def _build_form(self, container: Gtk.Box) -> None:
        i = self._login

        # ── Basic details ──────────────────────────────────────────────────
        details_group = Adw.PreferencesGroup(title="Details")

        self._name_row = _entry_row("Name", i.name if i else "")
        details_group.add(self._name_row)

        self._url_row = _entry_row("Website / URL", i.url if i else "")
        details_group.add(self._url_row)

        container.append(details_group)

        # ── Credentials ────────────────────────────────────────────────────
        creds_group = Adw.PreferencesGroup(title="Credentials")

        self._username_row = _entry_row("Username", i.username if i else "")
        self._add_copy_suffix(self._username_row)
        creds_group.add(self._username_row)

        self._email_row = _entry_row("Email", i.email if i else "")
        self._add_copy_suffix(self._email_row)
        creds_group.add(self._email_row)

        self._password_row = _password_row("Password", i.password if i else "")
        self._add_copy_suffix(self._password_row)
        creds_group.add(self._password_row)

        container.append(creds_group)

        # ── TOTP ───────────────────────────────────────────────────────────
        totp_group = Adw.PreferencesGroup(title="Two-Factor Authentication (TOTP)")

        self._totp_secret_row = _entry_row("Secret Key", i.totp_secret if i else "")
        totp_group.add(self._totp_secret_row)

        # Live TOTP code display
        self._totp_code_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=12
        )
        self._totp_code_box.set_margin_start(12)
        self._totp_code_box.set_margin_end(12)
        self._totp_code_box.set_margin_top(4)
        self._totp_code_box.set_margin_bottom(4)
        self._totp_code_box.set_visible(bool(i and i.totp_secret))

        self._totp_code_label = Gtk.Label()
        self._totp_code_label.add_css_class("title-2")
        self._totp_code_label.add_css_class("monospace")
        self._totp_code_label.set_selectable(True)
        self._totp_code_box.append(self._totp_code_label)

        self._totp_timer_bar = Gtk.LevelBar()
        self._totp_timer_bar.set_min_value(0)
        self._totp_timer_bar.set_max_value(30)
        self._totp_timer_bar.set_hexpand(True)
        self._totp_timer_bar.set_valign(Gtk.Align.CENTER)
        self._totp_code_box.append(self._totp_timer_bar)

        totp_copy_btn = _copy_button("Copy TOTP code")
        totp_copy_btn.connect(
            "clicked",
            lambda _: _copy_to_clipboard(self, self._totp_code_label.get_text()),
        )
        self._totp_code_box.append(totp_copy_btn)

        totp_code_row = Adw.PreferencesRow()
        totp_code_row.set_activatable(False)
        totp_code_row.set_child(self._totp_code_box)
        totp_group.add(totp_code_row)

        container.append(totp_group)

        # ── Notes ──────────────────────────────────────────────────────────
        notes_group, self._notes_tv = self._notes_group(i.notes if i else "")
        container.append(notes_group)

        # Start TOTP refresh timer
        self._totp_secret_row.connect("changed", self._on_totp_secret_changed)
        self._totp_timer_id: int | None = None
        if i and i.totp_secret:
            self._start_totp_refresh(i.totp_secret)

    def _on_totp_secret_changed(self, row: Adw.EntryRow) -> None:
        secret = row.get_text().strip()
        if secret:
            self._totp_code_box.set_visible(True)
            self._start_totp_refresh(secret)
        else:
            self._totp_code_box.set_visible(False)
            self._stop_totp_refresh()

    def _start_totp_refresh(self, secret: str) -> None:
        self._stop_totp_refresh()
        self._update_totp(secret)
        self._totp_timer_id = GLib.timeout_add(1000, self._tick_totp)

    def _stop_totp_refresh(self) -> None:
        if self._totp_timer_id is not None:
            GLib.source_remove(self._totp_timer_id)
            self._totp_timer_id = None

    def _tick_totp(self) -> bool:
        secret = self._totp_secret_row.get_text().strip()
        if not secret:
            return GLib.SOURCE_REMOVE
        self._update_totp(secret)
        return GLib.SOURCE_CONTINUE

    def _update_totp(self, secret: str) -> None:
        try:
            import pyotp

            totp = pyotp.TOTP(secret)
            code = totp.now()
            remaining = 30 - (int(time.time()) % 30)
            self._totp_code_label.set_text(f"{code[:3]} {code[3:]}")
            self._totp_timer_bar.set_value(remaining)
        except Exception:
            self._totp_code_label.set_text("Invalid secret")
            self._totp_timer_bar.set_value(0)

    def do_close_request(self) -> bool:
        self._stop_totp_refresh()
        return False  # allow close

    def _collect_item(self) -> Login:
        base = self._login or Login()
        base.name = self._name_row.get_text().strip()
        base.url = self._url_row.get_text().strip()
        base.username = self._username_row.get_text().strip()
        base.email = self._email_row.get_text().strip()
        base.password = self._password_row.get_text()
        base.totp_secret = self._totp_secret_row.get_text().strip()
        buf = self._notes_tv.get_buffer()
        base.notes = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        return base


# ── Credit Card dialog ────────────────────────────────────────────────────────


class CreditCardDialog(_BaseItemDialog):
    def __init__(self, item: CreditCard | None = None) -> None:
        self._card = item
        title = "Edit Credit Card" if item else "New Credit Card"
        super().__init__(title=title, item=item)

    def _build_form(self, container: Gtk.Box) -> None:
        c = self._card

        details_group = Adw.PreferencesGroup(title="Card Details")

        self._name_row = _entry_row("Label", c.name if c else "")
        details_group.add(self._name_row)

        self._holder_row = _entry_row("Cardholder Name", c.cardholder_name if c else "")
        details_group.add(self._holder_row)

        self._card_type_row = _entry_row("Card Type", c.card_type if c else "")
        details_group.add(self._card_type_row)

        container.append(details_group)

        numbers_group = Adw.PreferencesGroup(title="Numbers")

        self._number_row = _entry_row("Card Number", c.card_number if c else "")
        self._add_copy_suffix(self._number_row)
        numbers_group.add(self._number_row)

        expiry_row = Adw.ActionRow(title="Expiry")
        expiry_row.set_activatable(False)
        expiry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        expiry_box.set_valign(Gtk.Align.CENTER)

        self._expiry_month = Gtk.Entry()
        self._expiry_month.set_placeholder_text("MM")
        self._expiry_month.set_max_length(2)
        self._expiry_month.set_width_chars(4)
        if c:
            self._expiry_month.set_text(c.expiry_month)
        expiry_box.append(self._expiry_month)

        expiry_box.append(Gtk.Label(label="/"))

        self._expiry_year = Gtk.Entry()
        self._expiry_year.set_placeholder_text("YYYY")
        self._expiry_year.set_max_length(4)
        self._expiry_year.set_width_chars(6)
        if c:
            self._expiry_year.set_text(c.expiry_year)
        expiry_box.append(self._expiry_year)

        expiry_row.add_suffix(expiry_box)
        numbers_group.add(expiry_row)

        self._cvv_row = _password_row("CVV", c.cvv if c else "")
        self._add_copy_suffix(self._cvv_row)
        numbers_group.add(self._cvv_row)

        self._pin_row = _password_row("PIN", c.pin if c else "")
        self._add_copy_suffix(self._pin_row)
        numbers_group.add(self._pin_row)

        container.append(numbers_group)

        notes_group, self._notes_tv = self._notes_group(c.notes if c else "")
        container.append(notes_group)

    def _collect_item(self) -> CreditCard:
        base = self._card or CreditCard()
        base.name = self._name_row.get_text().strip()
        base.cardholder_name = self._holder_row.get_text().strip()
        base.card_type = self._card_type_row.get_text().strip()
        base.card_number = self._number_row.get_text().strip()
        base.expiry_month = self._expiry_month.get_text().strip()
        base.expiry_year = self._expiry_year.get_text().strip()
        base.cvv = self._cvv_row.get_text()
        base.pin = self._pin_row.get_text()
        buf = self._notes_tv.get_buffer()
        base.notes = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        return base


# ── Address dialog ────────────────────────────────────────────────────────────


class AddressDialog(_BaseItemDialog):
    def __init__(self, item: Address | None = None) -> None:
        self._addr = item
        title = "Edit Address" if item else "New Address"
        super().__init__(title=title, item=item)

    def _build_form(self, container: Gtk.Box) -> None:
        a = self._addr

        identity_group = Adw.PreferencesGroup(title="Identity")

        self._name_row = _entry_row("Label", a.name if a else "")
        identity_group.add(self._name_row)

        self._full_name_row = _entry_row("Full Name", a.full_name if a else "")
        identity_group.add(self._full_name_row)

        self._company_row = _entry_row("Company", a.company if a else "")
        identity_group.add(self._company_row)

        self._email_row = _entry_row("Email", a.email if a else "")
        identity_group.add(self._email_row)

        self._phone_row = _entry_row("Phone", a.phone if a else "")
        identity_group.add(self._phone_row)

        container.append(identity_group)

        address_group = Adw.PreferencesGroup(title="Address")

        self._street1_row = _entry_row("Street Address", a.street1 if a else "")
        address_group.add(self._street1_row)

        self._street2_row = _entry_row("Apt / Suite / Unit", a.street2 if a else "")
        address_group.add(self._street2_row)

        self._city_row = _entry_row("City", a.city if a else "")
        address_group.add(self._city_row)

        self._state_row = _entry_row("State / Province", a.state if a else "")
        address_group.add(self._state_row)

        self._postal_row = _entry_row("Postal Code", a.postal_code if a else "")
        address_group.add(self._postal_row)

        self._country_row = _entry_row("Country", a.country if a else "")
        address_group.add(self._country_row)

        container.append(address_group)

        notes_group, self._notes_tv = self._notes_group(a.notes if a else "")
        container.append(notes_group)

    def _collect_item(self) -> Address:
        base = self._addr or Address()
        base.name = self._name_row.get_text().strip()
        base.full_name = self._full_name_row.get_text().strip()
        base.company = self._company_row.get_text().strip()
        base.email = self._email_row.get_text().strip()
        base.phone = self._phone_row.get_text().strip()
        base.street1 = self._street1_row.get_text().strip()
        base.street2 = self._street2_row.get_text().strip()
        base.city = self._city_row.get_text().strip()
        base.state = self._state_row.get_text().strip()
        base.postal_code = self._postal_row.get_text().strip()
        base.country = self._country_row.get_text().strip()
        buf = self._notes_tv.get_buffer()
        base.notes = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        return base


# ── SSH Key dialog ────────────────────────────────────────────────────────────


class SSHKeyDialog(_BaseItemDialog):
    def __init__(self, item: SSHKey | None = None) -> None:
        self._key = item
        title = "Edit SSH Key" if item else "New SSH Key"
        super().__init__(title=title, item=item, content_width=540)

    def _build_form(self, container: Gtk.Box) -> None:
        k = self._key

        details_group = Adw.PreferencesGroup(title="Details")

        self._name_row = _entry_row("Name", k.name if k else "")
        details_group.add(self._name_row)

        self._key_type_row = _entry_row("Key Type", k.key_type if k else "ed25519")
        details_group.add(self._key_type_row)

        self._fingerprint_row = _entry_row("Fingerprint", k.fingerprint if k else "")
        self._add_copy_suffix(self._fingerprint_row)
        details_group.add(self._fingerprint_row)

        self._passphrase_row = _password_row("Passphrase", k.passphrase if k else "")
        self._add_copy_suffix(self._passphrase_row)
        details_group.add(self._passphrase_row)

        container.append(details_group)

        keys_group = Adw.PreferencesGroup(title="Key Material")

        pub_row, self._pub_tv = _make_text_row(
            "Public Key", k.public_key if k else "", monospace=True, height=80
        )
        keys_group.add(pub_row)

        priv_row, self._priv_tv = _make_text_row(
            "Private Key", k.private_key if k else "", monospace=True, height=120
        )
        keys_group.add(priv_row)

        container.append(keys_group)

        notes_group, self._notes_tv = self._notes_group(k.notes if k else "")
        container.append(notes_group)

    def _collect_item(self) -> SSHKey:
        base = self._key or SSHKey()
        base.name = self._name_row.get_text().strip()
        base.key_type = self._key_type_row.get_text().strip()
        base.fingerprint = self._fingerprint_row.get_text().strip()
        base.passphrase = self._passphrase_row.get_text()

        def _tv_text(tv: Gtk.TextView) -> str:
            buf = tv.get_buffer()
            return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

        base.public_key = _tv_text(self._pub_tv)
        base.private_key = _tv_text(self._priv_tv)
        buf = self._notes_tv.get_buffer()
        base.notes = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        return base


# ── Note dialog ───────────────────────────────────────────────────────────────


class SecureNoteDialog(_BaseItemDialog):
    def __init__(self, item: SecureNote | None = None) -> None:
        self._note = item
        title = "Edit Note" if item else "New Note"
        super().__init__(title=title, item=item)

    def _build_form(self, container: Gtk.Box) -> None:
        n = self._note

        details_group = Adw.PreferencesGroup(title="Details")
        self._name_row = _entry_row("Title", n.name if n else "")
        details_group.add(self._name_row)
        container.append(details_group)

        content_group = Adw.PreferencesGroup(title="Content")
        content_row, self._content_tv = _make_text_row(
            "", n.content if n else "", height=200
        )
        content_group.add(content_row)
        container.append(content_group)

    def _collect_item(self) -> SecureNote:
        base = self._note or SecureNote()
        base.name = self._name_row.get_text().strip()
        buf = self._content_tv.get_buffer()
        base.content = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        base.notes = ""
        return base


# ── Factory ───────────────────────────────────────────────────────────────────

from ..models import Category  # noqa: E402

_DIALOG_MAP: dict[Category, type[_BaseItemDialog]] = {
    Category.LOGINS: LoginDialog,
    Category.CREDIT_CARDS: CreditCardDialog,
    Category.ADDRESSES: AddressDialog,
    Category.SSH_KEYS: SSHKeyDialog,
    Category.SECURE_NOTES: SecureNoteDialog,
}


def make_dialog(category: Category, item: BaseItem | None = None) -> _BaseItemDialog:
    """Return the correct dialog instance for the given category."""
    cls = _DIALOG_MAP[category]
    return cls(item=item)  # type: ignore[arg-type]
