from __future__ import annotations

import math
import random
from typing import Any

from endstone.inventory import ItemStack

from ..constants import INFINITE_TICKS, Kind, Usage
from ..enchant import CustomEnchant
from ..util import Vec3, actor_alive, is_item_entity, pos_of, teleport_to


class ChestplateEnchant(CustomEnchant):
    usage = Usage.CHESTPLATE
    item_kind = Kind.CHESTPLATE


class ChickenEnchant(ChestplateEnchant):
    name = "Chicken"
    rarity = "uncommon"
    ticking = True

    def default_extra(self) -> dict[str, Any]:
        return {"treasureChanceMultiplier": 5, "treasures": ["minecraft:gold_ingot:1"], "interval": 1200 * 5}

    def __init__(self, plugin: Any, enchant_id: int) -> None:
        super().__init__(plugin, enchant_id)
        self.tick_interval = max(1, int(self.extra["interval"]))

    @staticmethod
    def _parse(entry: str) -> tuple[str, int]:
        parts = entry.rsplit(":", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0], int(parts[1])
        return entry, 1

    def _drops(self) -> list[str]:
        drops = self.plugin.cfg("chicken.drops", self.extra["treasures"])
        return list(drops) if isinstance(drops, (list, tuple)) else [str(drops)]

    def tick(self, player, item, slot, level):
        dim = player.dimension
        loc = player.location
        if random.randint(0, 100) <= self.extra["treasureChanceMultiplier"] * level:
            ident, count = self._parse(random.choice(self._drops()))
            if ":" not in ident:
                ident = "minecraft:" + ident
            stack = ItemStack(ident, count)
            label = ident.replace("minecraft:", "").replace("_", " ")
            article = "an " if label[:1] in "aeiou" else "a "
            dim.drop_item(loc, stack)
            player.send_tip(f"§aYou have laid {article}{label}...")
        else:
            dim.drop_item(loc, ItemStack("minecraft:egg", 1))
            player.send_tip("§aYou have laid an egg.")


class ParachuteEnchant(ChestplateEnchant):
    name = "Parachute"
    rarity = "uncommon"
    max_level = 1
    ticking = True
    toggleable = True

    def is_in_air(self, player: Any) -> bool:
        x, y, z = pos_of(player).floor()
        for k in range(1, 6):
            if self.plugin.world.block_id(player.dimension, x, y - k, z) != "minecraft:air":
                return False
        return True

    def tick(self, player, item, slot, level):
        fx = self.plugin.effects
        jetpack = self.plugin.manager.get("jetpack")
        jetting = jetpack is not None and jetpack.has_active(player)
        in_air = self.is_in_air(player)
        if in_air and not player.allow_flight and not jetting:
            if not fx.has(player, "slow_falling"):
                fx.add(player, "slow_falling", INFINITE_TICKS, 0, False)
        elif fx.has(player, "slow_falling"):
            x, y, z = pos_of(player).floor()
            if in_air or self.plugin.world.block_id(player.dimension, x, y - 1, z) != "minecraft:air":
                fx.remove(player, "slow_falling")

    def toggle(self, player, item, slot, level, toggle):
        if not toggle and self.plugin.effects.has(player, "slow_falling"):
            self.plugin.effects.remove(player, "slow_falling")


class ProwlEnchant(ChestplateEnchant):
    """Players cannot be hidden from other players on Endstone, so Prowl uses invisibility + slowness."""

    name = "Prowl"
    max_level = 1
    toggleable = True
    ticking = True

    def __init__(self, plugin: Any, enchant_id: int) -> None:
        super().__init__(plugin, enchant_id)
        self.prowled: set[str] = set()

    def _stop(self, player: Any) -> None:
        if player.name in self.prowled:
            self.plugin.effects.remove(player, "slowness")
            self.plugin.effects.remove(player, "invisibility")
            self.prowled.discard(player.name)

    def toggle(self, player, item, slot, level, toggle):
        if not toggle:
            self._stop(player)

    def tick(self, player, item, slot, level):
        if player.is_sneaking:
            if player.name not in self.prowled:
                fx = self.plugin.effects
                fx.add(player, "invisibility", INFINITE_TICKS, 0, False)
                fx.add(player, "slowness", INFINITE_TICKS, 0, False)
                self.prowled.add(player.name)
        else:
            self._stop(player)

    def forget(self, player: Any) -> None:
        super().forget(player)
        self.prowled.discard(player.name)


class SpiderEnchant(ChestplateEnchant):
    """setCanClimbWalls is a client flag Endstone cannot set: jump against a wall to climb, sneak to let go."""

    name = "Spider"
    max_level = 1
    toggleable = True
    ticking = True

    def __init__(self, plugin: Any, enchant_id: int) -> None:
        super().__init__(plugin, enchant_id)
        self.climbing: dict[str, int] = {}

    def default_extra(self) -> dict[str, Any]:
        return {"climbSpeed": 0.3, "maxClimbTicks": 80}

    def can_climb(self, player: Any) -> bool:
        x, y, z = pos_of(player).floor()
        world, dim = self.plugin.world, player.dimension
        for dy in (0, 1):
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if not world.is_passable(dim, x + dx, y + dy, z + dz):
                    return True
        return False

    def on_jump(self, player: Any) -> None:
        if self.get_armor_stack(player) > 0 and self.can_climb(player):
            self.climbing[player.name] = int(self.extra["maxClimbTicks"])

    def tick(self, player, item, slot, level):
        left = self.climbing.get(player.name)
        if left is None:
            return
        if left <= 0 or player.is_sneaking or not self.can_climb(player) or player.is_on_ground and left < self.extra["maxClimbTicks"] - 3:
            del self.climbing[player.name]
            return
        self.climbing[player.name] = left - 1
        p = pos_of(player)
        target = p + Vec3(0, self.extra["climbSpeed"], 0)
        if self.plugin.world.is_passable(player.dimension, *Vec3(target.x, target.y + 1.7, target.z).floor()):
            teleport_to(player, target)
            self.plugin.nofall.set(player, False, 1)

    def toggle(self, player, item, slot, level, toggle):
        if not toggle:
            self.climbing.pop(player.name, None)

    def forget(self, player: Any) -> None:
        super().forget(player)
        self.climbing.pop(player.name, None)


class VacuumEnchant(ChestplateEnchant):
    name = "Vacuum"
    max_level = 3
    ticking = True

    def default_extra(self) -> dict[str, Any]:
        return {"radiusMultiplier": 3}

    def tick(self, player, item, slot, level):
        me = pos_of(player)
        radius = self.extra["radiusMultiplier"] * level
        for actor in self.plugin.actors_in(player.dimension):
            try:
                if not is_item_entity(actor) or not actor_alive(actor):
                    continue
                p = pos_of(actor)
                if p.distance(me) <= radius:
                    teleport_to(actor, p + (me - p) * (1 / 3))
            except Exception:  # noqa: BLE001
                continue
