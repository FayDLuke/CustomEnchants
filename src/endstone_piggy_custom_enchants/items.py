from __future__ import annotations

from typing import Any

from endstone import Player
from endstone.inventory import ItemStack

from .constants import Kind

ARMOR_SLOTS = ("helmet", "chestplate", "leggings", "boots")


def item_id(item: ItemStack | None) -> str:
    if item is None:
        return ""
    try:
        return str(item.type.id)
    except Exception:
        return ""


def is_air(item: ItemStack | None) -> bool:
    return item is None or item_id(item) in ("", "minecraft:air")


def is_sword(item: ItemStack | None) -> bool:
    return item_id(item).endswith("_sword")


def is_axe(item: ItemStack | None) -> bool:
    return item_id(item).endswith("_axe")


def is_pickaxe(item: ItemStack | None) -> bool:
    return item_id(item).endswith("_pickaxe")


def is_shovel(item: ItemStack | None) -> bool:
    return item_id(item).endswith("_shovel")


def is_hoe(item: ItemStack | None) -> bool:
    return item_id(item).endswith("_hoe")


def is_bow(item: ItemStack | None) -> bool:
    return item_id(item) == "minecraft:bow"


def is_helmet(item: ItemStack | None) -> bool:
    return item_id(item).endswith("_helmet")


def is_chestplate(item: ItemStack | None) -> bool:
    return item_id(item).endswith("_chestplate")


def is_leggings(item: ItemStack | None) -> bool:
    return item_id(item).endswith("_leggings")


def is_boots(item: ItemStack | None) -> bool:
    return item_id(item).endswith("_boots")


def is_armor(item: ItemStack | None) -> bool:
    return is_helmet(item) or is_chestplate(item) or is_leggings(item) or is_boots(item)


def pretty_name(item: ItemStack | None) -> str:
    """Human-readable item name: its custom display name if set, else the item id title-cased."""
    if item is None:
        return ""
    try:
        meta = item.item_meta
        if meta.has_display_name():
            return meta.display_name
    except Exception:  # noqa: BLE001
        pass
    return item_id(item).replace("minecraft:", "").replace("_", " ").title()


def is_book(item: ItemStack | None) -> bool:
    return item_id(item) in ("minecraft:book", "minecraft:enchanted_book")


def max_durability(item: ItemStack | None) -> int:
    try:
        return int(item.type.max_durability)
    except Exception:
        return 0


def is_durable(item: ItemStack | None) -> bool:
    return max_durability(item) > 0


def item_matches_kind(item: ItemStack | None, kind: Kind) -> bool:
    if is_book(item):
        return True
    if kind == Kind.GLOBAL:
        return True
    if kind == Kind.DAMAGEABLE:
        return is_durable(item)
    if kind == Kind.WEAPON:
        return is_sword(item) or is_axe(item) or is_bow(item)
    if kind == Kind.SWORD:
        return is_sword(item)
    if kind == Kind.BOW:
        return is_bow(item)
    if kind == Kind.TOOLS:
        return (
            is_pickaxe(item) or is_axe(item) or is_shovel(item) or is_hoe(item)
            or item_id(item) == "minecraft:shears"
        )
    if kind == Kind.PICKAXE:
        return is_pickaxe(item)
    if kind == Kind.AXE:
        return is_axe(item)
    if kind == Kind.SHOVEL:
        return is_shovel(item)
    if kind == Kind.HOE:
        return is_hoe(item)
    if kind == Kind.ARMOR:
        return is_armor(item) or item_id(item) == "minecraft:elytra"
    if kind == Kind.HELMET:
        return is_helmet(item)
    if kind == Kind.CHESTPLATE:
        return is_chestplate(item)
    if kind == Kind.LEGGINGS:
        return is_leggings(item)
    if kind == Kind.BOOTS:
        return is_boots(item)
    if kind == Kind.COMPASS:
        return item_id(item) == "minecraft:compass"
    return False


class Slot:
    """Reference to one inventory location of a player. kind is 'inv' or 'armor'."""

    __slots__ = ("player", "kind", "index")

    def __init__(self, player: Player, kind: str, index: Any) -> None:
        self.player = player
        self.kind = kind
        self.index = index

    @property
    def is_armor(self) -> bool:
        return self.kind == "armor"

    @property
    def is_held(self) -> bool:
        return self.kind == "inv" and self.index == self.player.inventory.held_item_slot

    def key(self) -> tuple[str, Any]:
        return self.kind, self.index

    def get(self) -> ItemStack | None:
        inv = self.player.inventory
        item = getattr(inv, self.index) if self.is_armor else inv.get_item(self.index)
        return None if is_air(item) else item

    def set(self, item: ItemStack | None) -> None:
        inv = self.player.inventory
        if self.is_armor:
            setattr(inv, self.index, item)
        else:
            inv.set_item(self.index, item)

    def __repr__(self) -> str:
        return f"Slot({self.kind}:{self.index})"


def armor_slots(player: Player) -> list[Slot]:
    return [Slot(player, "armor", name) for name in ARMOR_SLOTS]


def inventory_slots(player: Player) -> list[Slot]:
    return [Slot(player, "inv", i) for i in range(player.inventory.size)]


def held_item(player: Player) -> ItemStack | None:
    item = player.inventory.item_in_main_hand
    return None if is_air(item) else item
