from __future__ import annotations

from typing import Any

from ..constants import Kind, Trigger, Usage
from ..enchant import CustomEnchant
from ..events import MoveEv
from ..util import pos_of


class HelmetEnchant(CustomEnchant):
    usage = Usage.HELMET
    item_kind = Kind.HELMET


class AntitoxinEnchant(HelmetEnchant):
    """No EntityEffectAddEvent exists: poison is stripped again shortly after it is applied."""

    name = "Antitoxin"
    rarity = "mythic"
    max_level = 1
    ticking = True
    tick_interval = 5

    def tick(self, player, item, slot, level):
        self.plugin.effects.remove(player, "poison")
        self.plugin.effects.remove(player, "fatal_poison")


class FocusedEnchant(HelmetEnchant):
    """No EntityEffectAddEvent exists: nausea is stripped again shortly after it is applied."""

    name = "Focused"
    rarity = "uncommon"
    ticking = True
    tick_interval = 5

    def tick(self, player, item, slot, level):
        self.plugin.effects.remove(player, "nausea")


class ImplantsEnchant(HelmetEnchant):
    name = "Implants"
    reactive = True
    reagents = (Trigger.MOVE,)

    def __init__(self, plugin: Any, enchant_id: int) -> None:
        super().__init__(plugin, enchant_id)
        self._last_air: dict[str, int] = {}

    def default_extra(self) -> dict[str, Any]:
        return {"foodReplenishAmountMultiplier": 1, "airTicksReplenishAmountMultiplier": 40, "airReplenishInterval": 60}

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, MoveEv):
            return
        fx = self.plugin.effects
        now = self.plugin.tick_count
        if not fx.has(player, "saturation"):
            fx.add(player, "saturation", 20, max(0, level * int(self.extra["foodReplenishAmountMultiplier"]) - 1), False)
        x, y, z = pos_of(player).floor()
        head_in_water = self.plugin.world.block_id(player.dimension, x, y + 1, z) in ("minecraft:water", "minecraft:flowing_water")
        if head_in_water and now - self._last_air.get(player.name, -10_000) >= self.extra["airReplenishInterval"]:
            fx.add(player, "water_breathing", int(self.extra["airReplenishInterval"]) + 20, 0, False)
            self._last_air[player.name] = now


class MeditationEnchant(HelmetEnchant):
    name = "Meditation"
    rarity = "uncommon"
    max_level = 2
    reactive = True
    ticking = True
    reagents = (Trigger.MOVE,)

    def __init__(self, plugin: Any, enchant_id: int) -> None:
        super().__init__(plugin, enchant_id)
        self.meditation_tick: dict[str, int] = {}

    def default_extra(self) -> dict[str, Any]:
        return {"duration": 20 * 20, "healthReplenishAmountMultiplier": 1, "foodReplenishAmountMultiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, MoveEv):
            self.meditation_tick[player.name] = 0

    def tick(self, player, item, slot, level):
        if player.name not in self.meditation_tick:
            return
        self.meditation_tick[player.name] += 1
        count = self.meditation_tick[player.name]
        if count % 10 == 0:
            filled = int(count / 40)
            player.send_tip("§2Meditating...\n§a" + "▌" * filled + "§7" + "▌" * max(0, int(20 * 20 / 40) - filled))
        if count >= self.extra["duration"]:
            self.meditation_tick[player.name] = 0
            self.plugin.combat.heal(player, level * self.extra["healthReplenishAmountMultiplier"])
            self.plugin.effects.add(player, "saturation", 20, max(0, int(level * self.extra["foodReplenishAmountMultiplier"]) - 1), False)

    def forget(self, player: Any) -> None:
        super().forget(player)
        self.meditation_tick.pop(player.name, None)
