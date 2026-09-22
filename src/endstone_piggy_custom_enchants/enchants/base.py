from __future__ import annotations

from typing import Any, Callable

from ..constants import INFINITE_TICKS, Kind, Usage
from ..enchant import CustomEnchant
from ..events import DamageEv
from ..items import Slot
from ..util import is_living


class RecursiveEnchant(CustomEnchant):
    """Enchants that break/affect other blocks: guarded so they never trigger each other."""

    reactive = True

    def react(self, player: Any, item: Any, slot: Slot, event: Any, level: int, stack: int) -> None:
        if player.name in self.plugin.recursion:
            return
        self.plugin.recursion.add(player.name)
        try:
            self.safe_react(player, item, slot, event, level, stack)
        finally:
            self.plugin.recursion.discard(player.name)

    def safe_react(self, player: Any, item: Any, slot: Slot, event: Any, level: int, stack: int) -> None:
        pass


class ToggleableEffectEnchant(CustomEnchant):
    toggleable = True

    def __init__(self, plugin: Any, enchant_id: int, name: str, max_level: int, usage: Usage, kind: Kind,
                 effect: str, base_amplifier: int = 0, amplifier_multiplier: int = 1, rarity: str = "rare") -> None:
        self.name = name
        self.max_level = max_level
        self.usage = usage
        self.item_kind = kind
        self.rarity = rarity
        self.effect = effect
        self._base_amplifier = base_amplifier
        self._amplifier_multiplier = amplifier_multiplier
        super().__init__(plugin, enchant_id)

    def default_extra(self) -> dict[str, Any]:
        return {"baseAmplifier": self._base_amplifier, "amplifierMultiplier": self._amplifier_multiplier}

    def toggle(self, player: Any, item: Any, slot: Slot, level: int, toggle: bool) -> None:
        fx = self.plugin.effects
        if toggle:
            if self.effect == "jump_boost":
                self.plugin.nofall.set(player, False, 2147483647)
        elif self.usage != Usage.ARMOR_INVENTORY or self.get_armor_stack(player) == 0:
            if self.effect == "jump_boost":
                self.plugin.nofall.set(player, True)
            fx.remove(player, self.effect)
            return
        fx.remove(player, self.effect)
        amplifier = self.extra["baseAmplifier"] + self.extra["amplifierMultiplier"] * level
        fx.add(player, self.effect, INFINITE_TICKS, int(min(amplifier, 255)), False)


class AttackerDeterrentEnchant(CustomEnchant):
    """Armor enchant that afflicts whoever hits the wearer."""

    reactive = True
    usage = Usage.ARMOR_INVENTORY
    item_kind = Kind.ARMOR

    def __init__(self, plugin: Any, enchant_id: int, name: str, effects: list[str], durations: list[int],
                 amplifiers: list[int], rarity: str = "rare") -> None:
        self.name = name
        self.rarity = rarity
        self.effects = effects
        self._durations = durations
        self._amplifiers = amplifiers
        super().__init__(plugin, enchant_id)

    def default_extra(self) -> dict[str, Any]:
        return {"durationMultipliers": self._durations, "amplifierMultipliers": self._amplifiers}

    def react(self, player: Any, item: Any, slot: Slot, event: Any, level: int, stack: int) -> None:
        if not isinstance(event, DamageEv) or not is_living(event.damager):
            return
        for i, effect in enumerate(self.effects):
            self.plugin.effects.add(
                event.damager, effect,
                int(self.extra["durationMultipliers"][i] * level),
                int(self.extra["amplifierMultipliers"][i] * level), True,
            )


class LacedWeaponEnchant(CustomEnchant):
    reactive = True

    def __init__(self, plugin: Any, enchant_id: int, name: str, rarity: str = "rare",
                 effects: list[str] | None = None, duration_multiplier: list[int] | None = None,
                 amplifier_multiplier: list[int] | None = None, base_duration: list[int] | None = None,
                 base_amplifier: list[int] | None = None) -> None:
        self.name = name
        self.rarity = rarity
        self.effects = effects or ["poison"]
        self._dm = duration_multiplier or [60]
        self._am = amplifier_multiplier or [1]
        self._bd = base_duration or [0]
        self._ba = base_amplifier or [0]
        super().__init__(plugin, enchant_id)

    def default_extra(self) -> dict[str, Any]:
        return {"durationMultiplier": self._dm, "amplifierMultiplier": self._am,
                "baseDuration": self._bd, "baseAmplifier": self._ba}

    @staticmethod
    def _at(values: list[int], i: int, default: int) -> int:
        return values[i] if i < len(values) else default

    def react(self, player: Any, item: Any, slot: Slot, event: Any, level: int, stack: int) -> None:
        if not isinstance(event, DamageEv) or not is_living(event.entity):
            return
        for i, effect in enumerate(self.effects):
            duration = self._at(self.extra["baseDuration"], i, 0) + self._at(self.extra["durationMultiplier"], i, 60) * level
            amplifier = self._at(self.extra["baseAmplifier"], i, 0) + self._at(self.extra["amplifierMultiplier"], i, 1) * level
            self.plugin.effects.add(event.entity, effect, duration, amplifier, True)


class ConditionalDamageMultiplierEnchant(CustomEnchant):
    reactive = True

    def __init__(self, plugin: Any, enchant_id: int, name: str, condition: Callable[[DamageEv], bool],
                 rarity: str = "rare") -> None:
        self.name = name
        self.rarity = rarity
        self.condition = condition
        super().__init__(plugin, enchant_id)

    def default_extra(self) -> dict[str, Any]:
        return {"additionalMultiplier": 0.1}

    def react(self, player: Any, item: Any, slot: Slot, event: Any, level: int, stack: int) -> None:
        if isinstance(event, DamageEv) and self.condition(event):
            event.damage = event.damage * (1 + self.extra["additionalMultiplier"] * level)
