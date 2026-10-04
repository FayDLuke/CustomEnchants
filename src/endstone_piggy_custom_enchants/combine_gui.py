"""Hopper-based combine station, built on top of the third-party `endstone-inventoryui` plugin (not a
built-in Endstone feature — see README). Imports from it are deferred to open_combine_menu() so the rest
of the plugin keeps working if that dependency isn't installed."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from endstone.inventory import ItemStack

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants

# Hopper layout (5 slots): [book] [confirm] [target] [locked] [locked].
SLOT_BOOK = 0
SLOT_CONFIRM = 1
SLOT_TARGET = 2
LOCKED_SLOTS = (3, 4)


def _confirm_icon() -> ItemStack:
    item = ItemStack("minecraft:lime_dye", 1)
    meta = item.item_meta
    meta.display_name = "§a§lCombine"
    meta.lore = ["§7Click to attempt the combine.", "§7The book is consumed either way."]
    item.set_item_meta(meta)
    return item


def _locked_icon() -> ItemStack:
    item = ItemStack("minecraft:gray_stained_glass_pane", 1)
    meta = item.item_meta
    meta.display_name = "§7"
    item.set_item_meta(meta)
    return item


def is_available() -> bool:
    try:
        import endstone_inventoryui  # noqa: F401
    except ImportError:
        return False
    return True


def open_combine_menu(plugin: "PiggyCustomEnchants", player: Any) -> bool:
    """Opens a fresh, per-player combine station. Returns False (and messages the player) if the
    endstone-inventoryui dependency isn't installed on this server."""
    try:
        from endstone_inventoryui import Menu, MenuTransaction, MenuTransactionResult, MenuType
    except ImportError:
        player.send_error_message(
            "The combine station needs the 'endstone-inventoryui' plugin, which isn't installed on this server."
        )
        return False

    menu = Menu(MenuType.HOPPER, "§8Combine Enchant")
    inv = menu.inventory
    inv.set_item(SLOT_CONFIRM, _confirm_icon())
    for slot in LOCKED_SLOTS:
        inv.set_item(slot, _locked_icon())

    def on_click(tr: "MenuTransaction") -> "MenuTransactionResult":
        if tr.slot in LOCKED_SLOTS:
            return tr.discard()
        if tr.slot == SLOT_CONFIRM:
            _do_combine(plugin, player, inv)
            return tr.discard()
        return tr.proceed()

    menu.set_listener(on_click)
    menu.send_to(player)
    return True


def _do_combine(plugin: "PiggyCustomEnchants", player: Any, inv: Any) -> None:
    book = inv.get_item(SLOT_BOOK)
    target = inv.get_item(SLOT_TARGET)
    result = plugin.combine.attempt(player, target, book)
    player.send_popup(result.message)

    if result.consumed_book:
        if book.amount > 1:
            book.amount -= 1
            inv.set_item(SLOT_BOOK, book)
        else:
            inv.set_item(SLOT_BOOK, None)

    if result.success and result.result_item is not None:
        inv.set_item(SLOT_TARGET, result.result_item)
