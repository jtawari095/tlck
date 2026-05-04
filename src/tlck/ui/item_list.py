"""
ItemListView — shows either an empty Adw.StatusPage or a scrollable
list of items for the currently selected category.
"""
from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GObject, Gtk  # noqa: E402

from ..models import CATEGORY_ICONS, CATEGORY_LABELS, BaseItem, Category
from ..vault import Vault
from .dialogs import make_dialog

logger = logging.getLogger(__name__)

_EMPTY_DESCRIPTIONS: dict[Category, str] = {
    Category.LOGINS: "Add a login to get started.\nStore usernames, passwords, and TOTP secrets.",
    Category.CREDIT_CARDS: "No credit cards saved yet.\nStore card numbers, CVVs, and expiry dates.",
    Category.ADDRESSES: "No addresses saved.\nKeep postal and contact information organised.",
    Category.SSH_KEYS: "No SSH keys stored.\nSave private keys, public keys, and passphrases.",
    Category.SECURE_NOTES: "No notes yet.\nStore any sensitive text securely.",
}


class ItemListView(Gtk.Box):
    """
    A self-contained view for one vault category.

    Reload the list by calling refresh().  Connects to the vault directly
    so it can handle CRUD without the parent window needing to mediate.
    """

    __gsignals__: dict = {
        "count-changed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, *, category: Category, vault: Vault) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._category = category
        self._vault = vault
        self._items: list[BaseItem] = []

        self.set_vexpand(True)
        self.set_hexpand(True)

        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self._stack.set_hexpand(True)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self._build_empty_page()
        self._build_list_page()

        self.append(self._stack)

    # ── Build ──────────────────────────────────────────────────────────────

    def _build_empty_page(self) -> None:
        status = Adw.StatusPage()
        status.set_icon_name(CATEGORY_ICONS[self._category])
        label = CATEGORY_LABELS[self._category]
        status.set_title(f"No {label}")
        status.set_description(_EMPTY_DESCRIPTIONS[self._category])
        status.set_vexpand(True)
        self._stack.add_named(status, "empty")

    def _build_list_page(self) -> None:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_top(12)
        self._list_box.set_margin_bottom(12)
        self._list_box.set_margin_start(12)
        self._list_box.set_margin_end(12)
        self._list_box.connect("row-activated", self._on_row_activated)

        scroll.set_child(self._list_box)
        self._stack.add_named(scroll, "list")

    # ── Refresh ────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload items from vault and rebuild the list."""
        if not self._vault.is_unlocked:
            return

        self._items = self._vault.list_items(category=self._category)

        # Clear existing rows
        while (child := self._list_box.get_first_child()):
            self._list_box.remove(child)

        for item in self._items:
            row = self._make_row(item)
            self._list_box.append(row)

        visible_page = "list" if self._items else "empty"
        self._stack.set_visible_child_name(visible_page)
        self.emit("count-changed", len(self._items))

    def _make_row(self, item: BaseItem) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(item.name)
        subtitle = item.subtitle()
        if subtitle:
            row.set_subtitle(subtitle)
        row.set_activatable(True)
        row.set_icon_name(CATEGORY_ICONS[self._category])
        chevron = Gtk.Image.new_from_icon_name("go-next-symbolic")
        chevron.add_css_class("dim-label")
        row.add_suffix(chevron)
        # Attach item reference for retrieval on activation
        row.item = item  # type: ignore[attr-defined]
        return row

    # ── Actions ────────────────────────────────────────────────────────────

    def open_new_item_dialog(self, parent: Gtk.Widget) -> None:
        dialog = make_dialog(self._category, item=None)
        dialog.connect("item-saved", self._on_item_saved)
        dialog.present(parent)

    def _on_row_activated(self, _box: Gtk.ListBox, row: Adw.ActionRow) -> None:
        item: BaseItem = row.item  # type: ignore[attr-defined]
        dialog = make_dialog(self._category, item=item)
        dialog.connect("item-saved", self._on_item_saved)
        dialog.connect("item-deleted", self._on_item_deleted)
        window = self.get_ancestor(Gtk.Window)
        dialog.present(window)

    def _on_item_saved(self, _dialog: object, item: BaseItem) -> None:
        if any(existing.id == item.id for existing in self._items):
            self._vault.update_item(category=self._category, item=item)
        else:
            self._vault.add_item(category=self._category, item=item)
        self.refresh()

    def _on_item_deleted(self, _dialog: object, item_id: str) -> None:
        self._vault.delete_item(item_id=item_id)
        self.refresh()
