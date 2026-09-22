from __future__ import annotations

from typing import TYPE_CHECKING, Any

from endstone.inventory import ItemStack

from . import storage
from .constants import ENCHANT_IDS, INCOMPATIBLE_ENCHANTS, Kind
from .enchant import CustomEnchant
from .items import is_book, item_matches_kind
from .util import color_code, normalize_name, roman

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants


class CustomEnchantManager:
    def __init__(self, plugin: "PiggyCustomEnchants") -> None:
        self.plugin = plugin
        self.enchants: dict[str, CustomEnchant] = {}
        self.by_id: dict[int, CustomEnchant] = {}

    # registry
    def register(self, enchant: CustomEnchant) -> None:
        self.enchants[enchant.key] = enchant
        self.by_id[enchant.id] = enchant

    def unregister(self, enchant: CustomEnchant) -> None:
        self.enchants.pop(enchant.key, None)
        self.by_id.pop(enchant.id, None)

    def register_all(self) -> None:
        from .enchants import build_all

        for enchant in build_all(self.plugin):
            self.register(enchant)

    def get(self, ref: str | int) -> CustomEnchant | None:
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            return self.by_id.get(int(ref))
        key = normalize_name(ref)
        found = self.enchants.get(key)
        if found is not None:
            return found
        for enchant in self.enchants.values():
            if normalize_name(enchant.display_name) == key:
                return enchant
        return None

    def all(self) -> list[CustomEnchant]:
        return list(self.enchants.values())

    def is_enabled(self, enchant: CustomEnchant) -> bool:
        if enchant.unsupported_reason is not None and not self.plugin.cfg("enable-unsupported", False):
            return False
        return enchant.key not in self.plugin.disabled_enchants

    @staticmethod
    def id_for(key: str) -> int:
        return ENCHANT_IDS[key]

    # item helpers
    def enchants_of(self, item: ItemStack | None) -> dict[CustomEnchant, int]:
        out: dict[CustomEnchant, int] = {}
        for key, level in storage.read_enchants(item).items():
            enchant = self.enchants.get(key)
            if enchant is not None:
                out[enchant] = level
        return out

    def level_on(self, item: ItemStack | None, enchant: CustomEnchant) -> int:
        return storage.read_enchants(item).get(enchant.key, 0)

    def render_lines(self, enchants: dict[str, int]) -> list[str]:
        numerals = self.plugin.cfg("roman-numerals", True)
        lines = []
        for key, level in enchants.items():
            enchant = self.enchants.get(key)
            if enchant is None:
                continue
            colors = self.plugin.rarity_colors
            shown = roman(level) if numerals else str(level)
            lines.append(f"§r{color_code(colors.get(enchant.rarity, 'gray'))}{enchant.display_name} {shown}")
        return lines

    def popup_text(self, item: ItemStack | None) -> str | None:
        """Text for the hotbar-switch popup (send_popup), mimicking the vanilla item-name-and-enchant box
        for items whose enchants are ours and therefore invisible to that vanilla box (see README)."""
        from .items import pretty_name

        enchants = storage.read_enchants(item)
        if not enchants:
            return None
        lines = self.render_lines(enchants)
        if not lines:
            return None
        return f"§f{pretty_name(item)}\n" + "\n".join(lines)

    def is_compatible(self, item: ItemStack, enchant: CustomEnchant) -> bool:
        for other_key in storage.read_enchants(item):
            if other_key in INCOMPATIBLE_ENCHANTS.get(enchant.key, ()):
                return False
            if enchant.key in INCOMPATIBLE_ENCHANTS.get(other_key, ()):
                return False
        return True

    def can_apply(self, item: ItemStack | None, enchant: CustomEnchant) -> bool:
        if item is None or not item_matches_kind(item, enchant.item_kind):
            return False
        return is_book(item) or self.is_compatible(item, enchant)

    def add_enchant(self, item: ItemStack, enchant: CustomEnchant, level: int = 1,
                    check_compatibility: bool = True) -> bool:
        if check_compatibility and not self.can_apply(item, enchant):
            return False
        current = storage.read_enchants(item)
        current[enchant.key] = max(1, level)
        storage.write_enchants(item, current, self.render_lines(current))
        return True

    def remove_enchant(self, item: ItemStack, enchant: CustomEnchant) -> bool:
        current = storage.read_enchants(item)
        if enchant.key not in current:
            return False
        del current[enchant.key]
        storage.write_enchants(item, current, self.render_lines(current))
        return True

    def set_all(self, item: ItemStack, enchants: dict[str, int]) -> None:
        storage.write_enchants(item, enchants, self.render_lines(enchants))

    def enchants_for_kind(self, kinds: tuple[Kind, ...]) -> list[CustomEnchant]:
        return [e for e in self.enchants.values() if e.item_kind in kinds]

    def make_book(self, enchant: CustomEnchant, level: int) -> ItemStack:
        book = ItemStack("minecraft:enchanted_book", 1)
        storage.ensure_book_uuid(book)
        self.add_enchant(book, enchant, level, check_compatibility=False)
        return book

    def disable_all(self) -> None:
        for enchant in self.enchants.values():
            try:
                enchant.on_disable()
            except Exception as exc:  # noqa: BLE001
                self.plugin.debug(f"on_disable failed for {enchant.name}: {exc}")

    def display_type(self, kind: Kind) -> str:
        from .constants import TYPE_NAMES

        return TYPE_NAMES.get(kind, "Unknown")

    def _unused(self) -> Any:  # pragma: no cover
        return None
