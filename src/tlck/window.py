from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from .models import CATEGORY_ICONS, CATEGORY_LABELS, Category
from .ui.item_list import ItemListView
from .ui.unlock import UnlockDialog
from .vault import Vault

logger = logging.getLogger(__name__)


class TlckWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, vault: Vault) -> None:
        super().__init__(application=app)
        self._vault = vault
        self._item_views: dict[Category, ItemListView] = {}
        self._current_category: Category = Category.LOGINS
        self._sidebar_rows: dict[Category, Adw.ActionRow] = {}
        self._count_labels: dict[Category, Gtk.Label] = {}

        self.set_title("Tlck")
        self.set_default_size(960, 640)
        self.set_size_request(640, 480)

        self._toast_overlay = Adw.ToastOverlay()
        self._build_ui()
        self.set_content(self._toast_overlay)

        self._show_unlock_dialog()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        split_view = Adw.NavigationSplitView()
        split_view.set_min_sidebar_width(220)
        split_view.set_max_sidebar_width(280)
        split_view.set_sidebar_width_fraction(0.27)

        split_view.set_sidebar(self._build_sidebar_page())
        split_view.set_content(self._build_content_page())

        self._split_view = split_view
        self._toast_overlay.set_child(split_view)

    # ── Sidebar ────────────────────────────────────────────────────────────

    def _build_sidebar_page(self) -> Adw.NavigationPage:
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_show_title(True)
        title_widget = Adw.WindowTitle.new("Tlck", "Secret Manager")
        header.set_title_widget(title_widget)
        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(280)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(8)
        box.set_margin_end(8)

        self._sidebar_list = Gtk.ListBox()
        self._sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._sidebar_list.add_css_class("navigation-sidebar")
        self._sidebar_list.connect("row-selected", self._on_category_selected)

        for category in Category:
            row = self._make_sidebar_row(category)
            self._sidebar_list.append(row)
            self._sidebar_rows[category] = row

        box.append(self._sidebar_list)
        clamp.set_child(box)
        scroll.set_child(clamp)
        toolbar_view.set_content(scroll)

        page = Adw.NavigationPage.new(toolbar_view, "Categories")
        return page

    def _make_sidebar_row(self, category: Category) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(CATEGORY_LABELS[category])
        row.set_activatable(True)
        row.set_icon_name(CATEGORY_ICONS[category])

        count_label = Gtk.Label(label="")
        count_label.add_css_class("dim-label")
        count_label.add_css_class("caption")
        count_label.set_valign(Gtk.Align.CENTER)
        row.add_suffix(count_label)
        self._count_labels[category] = count_label

        row.category = category  # type: ignore[attr-defined]
        return row

    # ── Content ────────────────────────────────────────────────────────────

    def _build_content_page(self) -> Adw.NavigationPage:
        self._content_toolbar_view = Adw.ToolbarView()

        self._content_header = Adw.HeaderBar()
        self._content_title = Adw.WindowTitle.new(
            CATEGORY_LABELS[Category.LOGINS], ""
        )
        self._content_header.set_title_widget(self._content_title)

        self._add_button = Gtk.Button()
        self._add_button.set_icon_name("list-add-symbolic")
        self._add_button.set_tooltip_text("Add item")
        self._add_button.add_css_class("suggested-action")
        self._add_button.connect("clicked", self._on_add_clicked)
        self._add_button.set_sensitive(False)
        self._content_header.pack_end(self._add_button)

        self._content_toolbar_view.add_top_bar(self._content_header)

        self._content_stack = Gtk.Stack()
        self._content_stack.set_vexpand(True)
        self._content_stack.set_hexpand(True)
        self._content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        for category in Category:
            view = ItemListView(category=category, vault=self._vault)
            view.connect("count-changed", self._on_count_changed, category)
            self._item_views[category] = view
            self._content_stack.add_named(view, category.value)

        self._content_toolbar_view.set_content(self._content_stack)
        page = Adw.NavigationPage.new(self._content_toolbar_view, "Items")
        return page

    # ── Unlock flow ────────────────────────────────────────────────────────

    def _show_unlock_dialog(self) -> None:
        dialog = UnlockDialog(self._vault)
        dialog.connect("vault-unlocked", self._on_vault_unlocked)
        dialog.present(self)

    def _on_vault_unlocked(self, _dialog: UnlockDialog) -> None:
        self._add_button.set_sensitive(True)
        self._select_category(Category.LOGINS)
        for view in self._item_views.values():
            view.refresh()
        self._update_all_counts()

    # ── Category selection ─────────────────────────────────────────────────

    def _on_category_selected(
        self, _box: Gtk.ListBox, row: Adw.ActionRow | None
    ) -> None:
        if row is None:
            return
        category: Category = row.category  # type: ignore[attr-defined]
        self._current_category = category
        self._content_stack.set_visible_child_name(category.value)
        self._content_title.set_title(CATEGORY_LABELS[category])
        # On narrow screens, navigate to content
        self._split_view.set_show_content(True)

    def _select_category(self, category: Category) -> None:
        row = self._sidebar_rows[category]
        self._sidebar_list.select_row(row)

    # ── Add button ─────────────────────────────────────────────────────────

    def _on_add_clicked(self, _btn: Gtk.Button) -> None:
        view = self._item_views[self._current_category]
        view.open_new_item_dialog(self)

    # ── Count labels ───────────────────────────────────────────────────────

    def _on_count_changed(
        self, _view: ItemListView, count: int, category: Category
    ) -> None:
        label = self._count_labels[category]
        label.set_text(str(count) if count > 0 else "")

    def _update_all_counts(self) -> None:
        counts = self._vault.counts()
        for category, count in counts.items():
            label = self._count_labels.get(category)
            if label:
                label.set_text(str(count) if count > 0 else "")
