from __future__ import annotations

import json
import random
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .constants import RARITIES, Kind, Trigger, Usage
from .events import DamageEv
from .items import Slot
from .util import Cooldowns, normalize_name, same_actor

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants

DATA_FILES = ("rarities", "max_levels", "display_names", "descriptions", "extra_data", "cooldowns", "chances")


class EnchantData:
    """The seven per-enchant JSON files of the original plugin (rarities.json, max_levels.json, ...)."""

    def __init__(self, folder: Path, resources: Path | None = None) -> None:
        self.folder = folder
        self.data: dict[str, dict[str, Any]] = {name: {} for name in DATA_FILES}
        self._dirty: set[str] = set()
        folder.mkdir(parents=True, exist_ok=True)
        for name in DATA_FILES:
            path = folder / f"{name}.json"
            if not path.exists() and resources is not None and (resources / f"{name}.json").exists():
                path.write_text((resources / f"{name}.json").read_text(encoding="utf-8"), encoding="utf-8")
            if path.exists():
                try:
                    self.data[name] = json.loads(path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    self.data[name] = {}

    def get(self, enchant: str, file: str, default: Any = "") -> Any:
        key = normalize_name(enchant)
        table = self.data[file]
        if key not in table:
            table[key] = default
            self._dirty.add(file)
        return table[key]

    def set(self, enchant: str, file: str, value: Any) -> None:
        self.data[file][normalize_name(enchant)] = value
        self._dirty.add(file)

    def flush(self) -> None:
        for name in list(self._dirty):
            try:
                (self.folder / f"{name}.json").write_text(
                    json.dumps(self.data[name], indent=2, ensure_ascii=False), encoding="utf-8"
                )
            except OSError:
                pass
        self._dirty.clear()


class CustomEnchant:
    """Base of every enchant.

    An enchant is reactive (reagents + react), ticking (tick), toggleable (toggle) or any mix of them,
    mirroring ReactiveEnchantment / TickingEnchantment / ToggleableEnchantment of the original plugin.
    """

    name: str = ""
    rarity: str = "rare"
    max_level: int = 5
    usage: Usage = Usage.HAND
    item_kind: Kind = Kind.WEAPON
    cooldown_duration: int = 0
    priority: int = 1
    tick_interval: int = 1
    supports_multiple_items: bool = False
    reactive: bool = False
    ticking: bool = False
    toggleable: bool = False
    reagents: tuple[Trigger, ...] = (Trigger.DAMAGE_BY_ENTITY,)
    unsupported_reason: str | None = None

    def __init__(self, plugin: "PiggyCustomEnchants", enchant_id: int) -> None:
        self.plugin = plugin
        self.id = enchant_id
        self.key = normalize_name(self.name)
        data = plugin.enchant_data
        rarity = str(data.get(self.name, "rarities", self.rarity)).lower()
        self.rarity = rarity if rarity in RARITIES else "rare"
        self.max_level = int(data.get(self.name, "max_levels", self.max_level))
        self.display_name = str(data.get(self.name, "display_names", self.name))
        self.description = str(data.get(self.name, "descriptions", ""))
        default_extra = self.default_extra()
        extra = data.get(self.name, "extra_data", default_extra)
        self.extra: dict[str, Any] = dict(extra) if isinstance(extra, dict) else dict(default_extra)
        for k, v in default_extra.items():
            if k not in self.extra:
                self.extra[k] = v
                data.set(self.name, "extra_data", self.extra)
        self.cooldown_duration = int(data.get(self.name, "cooldowns", self.cooldown_duration))
        self.chance = int(data.get(self.name, "chances", 100))
        self.cooldowns = Cooldowns()
        self.chance_multiplier: dict[str, float] = {}
        self.stack: dict[str, int] = {}
        self.armor_stack: dict[str, int] = {}

    # overridables
    def default_extra(self) -> dict[str, Any]:
        return {}

    def react(self, player: Any, item: Any, slot: Slot, event: Any, level: int, stack: int) -> None:
        pass

    def tick(self, player: Any, item: Any, slot: Slot, level: int) -> None:
        pass

    def toggle(self, player: Any, item: Any, slot: Slot, level: int, toggle: bool) -> None:
        pass

    def on_disable(self) -> None:
        pass

    # shared behaviour
    def disabled_in_world(self, player: Any) -> bool:
        return self.plugin.is_disabled_in_world(self.key, player)

    def get_cooldown(self, player: Any) -> float:
        return self.cooldowns.remaining(player)

    def set_cooldown(self, player: Any, seconds: float) -> None:
        self.cooldowns.set(player, seconds)

    def base_chance(self, level: int) -> float:
        return float(self.chance * level)

    def get_chance(self, player: Any, level: int) -> float:
        return self.base_chance(level) * self.chance_multiplier.get(player.name, 1.0)

    def get_chance_multiplier(self, player: Any) -> float:
        return self.chance_multiplier.get(player.name, 1.0)

    def set_chance_multiplier(self, player: Any, value: float) -> None:
        self.chance_multiplier[player.name] = value

    def should_react_to_damage(self) -> bool:
        return self.item_kind in (Kind.WEAPON, Kind.BOW)

    def should_react_to_damaged(self) -> bool:
        return self.usage == Usage.ARMOR_INVENTORY

    def on_reaction(self, player: Any, item: Any, slot: Slot, event: Any, level: int, stack: int) -> None:
        if self.disabled_in_world(player) or self.get_cooldown(player) > 0:
            return
        if isinstance(event, DamageEv) and event.by_entity:
            if same_actor(event.entity, player):
                if not same_actor(event.damager, player) and not self.should_react_to_damaged():
                    return
            elif not self.should_react_to_damage():
                return
        if random.uniform(0, 100) <= self.get_chance(player, level):
            self.react(player, item, slot, event, level, stack)
            self.set_cooldown(player, self.cooldown_duration)

    def on_tick(self, player: Any, item: Any, slot: Slot, level: int) -> None:
        if self.disabled_in_world(player) or self.get_cooldown(player) > 0:
            return
        self.tick(player, item, slot, level)

    def on_toggle(self, player: Any, item: Any, slot: Slot, level: int, toggle: bool) -> None:
        if self.disabled_in_world(player) or self.get_cooldown(player) > 0:
            return
        if toggle:
            self.add_to_stack(player, level)
        else:
            self.remove_from_stack(player, level)
        self.toggle(player, item, slot, level, toggle)

    def add_to_stack(self, player: Any, level: int) -> None:
        self.stack[player.name] = self.get_stack(player) + level
        self.armor_stack[player.name] = self.get_armor_stack(player) + 1

    def remove_from_stack(self, player: Any, level: int) -> None:
        if player.name in self.stack:
            self.stack[player.name] -= level
        self.armor_stack[player.name] = self.get_armor_stack(player) - 1

    def get_stack(self, player: Any) -> int:
        return self.stack.get(player.name, 0)

    def get_armor_stack(self, player: Any) -> int:
        return self.armor_stack.get(player.name, 0)

    def forget(self, player: Any) -> None:
        for table in (self.stack, self.armor_stack, self.chance_multiplier):
            table.pop(player.name, None)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"
