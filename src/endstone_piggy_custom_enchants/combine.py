"""The "combine" mechanic: apply an enchant book to a tool/armor piece with a rarity-based success chance,
like an anvil gamble. This module is pure logic with no GUI dependency — anything that can hand it two
ItemStacks (a chest-UI, a command, a form) can drive it the same way."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import storage
from .items import is_air, is_book, item_matches_kind

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants

# Fallback used only if a rarity is missing from config (config.toml always ships all four).
DEFAULT_SUCCESS_CHANCE = {"common": 85.0, "uncommon": 65.0, "rare": 45.0, "mythic": 25.0}


@dataclass
class CombineResult:
    success: bool
    # False = rejected before the roll (wrong item, incompatible, nothing to gain) — book is kept.
    # True = the dice were rolled — book is always consumed, win or lose.
    attempted: bool
    message: str
    result_item: Any = None  # the target item with the enchant applied, set only on success
    chance: float = 0.0

    @property
    def consumed_book(self) -> bool:
        return self.attempted


class CombineService:
    def __init__(self, plugin: "PiggyCustomEnchants") -> None:
        self.plugin = plugin

    def chance_for(self, rarity: str) -> float:
        return float(self.plugin.cfg(f"combine.success-chance.{rarity}", DEFAULT_SUCCESS_CHANCE.get(rarity, 50.0)))

    def attempt(self, player: Any, target_item: Any, book_item: Any) -> CombineResult:
        manager = self.plugin.manager
        if is_air(book_item) or not is_book(book_item):
            return CombineResult(False, False, "§cPlace a custom enchant book in the book slot.")
        book_enchants = storage.read_enchants(book_item)
        if not book_enchants:
            return CombineResult(False, False, "§cThat book has no custom enchant on it.")
        key, level = next(iter(book_enchants.items()))
        enchant = manager.enchants.get(key)
        if enchant is None or not manager.is_enabled(enchant):
            return CombineResult(False, False, "§cThat enchant is currently disabled.")
        if is_air(target_item):
            return CombineResult(False, False, "§cPlace the tool/armor you want to enchant.")
        if target_item.amount != 1:
            return CombineResult(False, False, "§cYou can only combine one item at a time.")
        if not item_matches_kind(target_item, enchant.item_kind):
            return CombineResult(False, False, f"§c{enchant.display_name} cannot go on that item.")
        current = manager.level_on(target_item, enchant)
        if current >= level:
            return CombineResult(False, False, "§cThe item already has this enchant at an equal or higher level.")
        if not manager.is_compatible(target_item, enchant):
            return CombineResult(False, False, "§cThis enchant conflicts with another enchant on that item.")

        chance = self.chance_for(enchant.rarity)
        if random.uniform(0, 100) > chance:
            return CombineResult(False, True, f"§c✘ Failed! ({chance:.0f}% chance) The book was consumed.", chance=chance)

        manager.add_enchant(target_item, enchant, level, check_compatibility=False)
        return CombineResult(
            True, True, f"§a✔ Success! {enchant.display_name} {level} applied.", target_item, chance,
        )
