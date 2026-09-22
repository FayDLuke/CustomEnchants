from __future__ import annotations

import math
import random
import time
from typing import Any

from ..constants import Kind, Trigger, Usage
from ..enchant import CustomEnchant
from ..events import DamageEv, MoveEv, SneakEv
from ..items import Slot
from ..util import Vec3, actor_alive, direction_of, is_living, pos_of, same_actor, teleport_to


class JetpackEnchant(CustomEnchant):
    name = "Jetpack"
    max_level = 3
    usage = Usage.BOOTS
    item_kind = Kind.BOOTS
    reactive = True
    ticking = True
    toggleable = True
    reagents = (Trigger.SNEAK, Trigger.DAMAGE)

    def __init__(self, plugin: Any, enchant_id: int) -> None:
        super().__init__(plugin, enchant_id)
        self.active: set[str] = set()
        self.power: dict[str, float] = {}
        self.last_activated: dict[str, float] = {}

    def default_extra(self) -> dict[str, Any]:
        return {"power": 300, "rechargeAmount": 0.66, "enableAmount": 25, "drainMultiplier": 1,
                "sprintDrainMultiplier": 1.25, "speedMultiplier": 1, "sprintSpeedMultiplier": 1.25,
                "blocksPerTickMultiplier": 0.4}

    def has_active(self, player: Any) -> bool:
        return player.name in self.active

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv) and event.cause == "fall" and self.has_active(player):
            event.cancel()
        elif isinstance(event, SneakEv) and event.is_sneaking:
            if self.has_active(player):
                chest = player.inventory.chestplate
                parachute = self.plugin.manager.get("parachute")
                has_parachute = chest is not None and parachute is not None and self.plugin.manager.level_on(chest, parachute) > 0
                if not player.is_on_ground and not has_parachute and not player.allow_flight:
                    player.send_popup("§cIt is unsafe to disable your jetpack while in the air.")
                else:
                    self.power_jetpack(player, False)
            else:
                self.power_jetpack(player)

    def tick(self, player, item, slot, level):
        if not self.has_active(player):
            return
        e = self.extra
        sprinting = bool(player.is_sprinting)
        speed = level * (e["sprintSpeedMultiplier"] if sprinting else e["speedMultiplier"])
        step = direction_of(player) * (speed * e["blocksPerTickMultiplier"])
        origin = pos_of(player)
        target = origin + step
        dim = player.dimension
        world = self.plugin.world
        if world.is_passable(dim, *target.floor()) and world.is_passable(dim, target.floor()[0], math.floor(target.y + 1.5), target.floor()[2]):
            teleport_to(player, target)
        self.plugin.nofall.set(player, False, 1)
        world.particle(dim, "minecraft:basic_smoke_particle", origin, 32)
        remaining = self.power.get(player.name, 0)
        bars = math.ceil(remaining / 10)
        if bars > 2:
            color = "§a" if bars > 10 else ("§e" if bars > 5 else "§c")
            player.send_tip(f"{color}Power: " + "|" * int(bars))
        low = math.ceil(remaining / 5)
        if bars <= 2 and low > 0:
            player.send_tip("§cJetpack low on power: " + "|" * int(low))
        if self.plugin.tick_count % 20 == 0:
            self.power[player.name] = remaining - (e["sprintDrainMultiplier"] if sprinting else e["drainMultiplier"])
            if self.power[player.name] <= 0:
                player.send_tip("§cJetpack has run out of power.")
                self.power_jetpack(player, False)

    def toggle(self, player, item, slot, level, toggle):
        if not toggle and self.has_active(player):
            self.power_jetpack(player, False)

    def power_jetpack(self, player: Any, power: bool = True) -> None:
        name = player.name
        if power:
            if name not in self.power:
                self.power[name] = self.extra["power"]
                self.active.add(name)
            else:
                self.power[name] += (time.time() - self.last_activated.get(name, time.time())) * self.extra["rechargeAmount"]
                self.power[name] = min(self.power[name], self.extra["power"])
                if self.power[name] < self.extra["enableAmount"]:
                    player.send_tip(
                        f"§cJetpack needs to charge up to {self.extra['enableAmount']} before it can be re-enabled. "
                        f"({round(abs(self.power[name]), 2)} / {self.extra['power']})")
                    return
                self.active.add(name)
        else:
            self.active.discard(name)
            self.last_activated[name] = time.time()

    def forget(self, player: Any) -> None:
        super().forget(player)
        self.active.discard(player.name)


class MagmaWalkerEnchant(CustomEnchant):
    name = "Magma Walker"
    rarity = "uncommon"
    max_level = 2
    usage = Usage.BOOTS
    item_kind = Kind.BOOTS
    reactive = True
    reagents = (Trigger.MOVE,)

    LAVA = ("minecraft:lava", "minecraft:flowing_lava")

    def __init__(self, plugin: Any, enchant_id: int) -> None:
        super().__init__(plugin, enchant_id)
        # (dimension name, x, y, z) -> [age, next melt tick]
        self.obsidian: dict[tuple[str, int, int, int], list[int]] = {}

    def default_extra(self) -> dict[str, Any]:
        return {"baseRadius": 2, "radiusMultiplier": 1}

    def _is_source_lava(self, block: Any) -> bool:
        try:
            return block.type in self.LAVA and int(block.data.block_states.get("liquid_depth", 0)) == 0
        except Exception:  # noqa: BLE001
            return False

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, MoveEv):
            return
        dim = player.dimension
        px, py, pz = pos_of(player).floor()
        if self.plugin.world.block_id(dim, px, py, pz) in self.LAVA:
            return
        radius = int(level * self.extra["radiusMultiplier"] + self.extra["baseRadius"])
        for x in range(-radius, radius + 1):
            for z in range(-radius, radius + 1):
                bx, by, bz = px + x, py - 1, pz + z
                if self.plugin.world.block_id(dim, bx, by + 1, bz) != "minecraft:air":
                    continue
                block = dim.get_block_at(bx, by, bz)
                if self._is_source_lava(block):
                    block.set_type("minecraft:obsidian")
                    self.obsidian[(dim.name, bx, by, bz)] = [0, self.plugin.tick_count + random.randint(20, 40)]

    def global_tick(self, tick: int) -> None:
        if not self.obsidian or tick % 5 != 0:
            return
        for key, state in list(self.obsidian.items()):
            if tick < state[1] or key not in self.obsidian:
                continue
            dim = self._dimension(key[0])
            if dim is None:
                del self.obsidian[key]
                continue
            neighbours = sum(1 for n in self._sides(key) if n in self.obsidian)
            if random.randint(0, 3) == 0 or neighbours < 4:
                self._melt(key, dim, True)
            else:
                state[1] = tick + random.randint(20, 40)

    def _sides(self, key: tuple[str, int, int, int]):
        d, x, y, z = key
        return [(d, x + 1, y, z), (d, x - 1, y, z), (d, x, y + 1, z), (d, x, y - 1, z), (d, x, y, z + 1), (d, x, y, z - 1)]

    def _dimension(self, name: str) -> Any:
        for dim in self.plugin.server.level.dimensions:
            if dim.name == name:
                return dim
        return None

    def _melt(self, key: tuple[str, int, int, int], dim: Any, melt_neighbours: bool) -> None:
        state = self.obsidian.get(key)
        if state is None:
            return
        if state[0] < 3:
            state[0] += 1
            state[1] = self.plugin.tick_count + random.randint(20, 40)
            return
        del self.obsidian[key]
        _n, x, y, z = key
        block = dim.get_block_at(x, y, z)
        if block.type == "minecraft:obsidian":
            block.set_type("minecraft:lava")
        if melt_neighbours:
            for n in self._sides(key):
                if n in self.obsidian:
                    self._melt(n, dim, False)

    def handle_break(self, event: Any) -> bool:
        """Breaking a magma obsidian block turns it back into lava instead of dropping anything."""
        block = event.block
        key = (block.dimension.name, block.x, block.y, block.z)
        if key not in self.obsidian:
            return False
        del self.obsidian[key]
        event.cancel()
        block.set_type("minecraft:lava")
        return True

    def on_disable(self) -> None:
        for key in list(self.obsidian):
            dim = self._dimension(key[0])
            if dim is not None:
                _n, x, y, z = key
                block = dim.get_block_at(x, y, z)
                if block.type == "minecraft:obsidian":
                    block.set_type("minecraft:lava")
        self.obsidian.clear()


class StompEnchant(CustomEnchant):
    name = "Stomp"
    rarity = "uncommon"
    max_level = 1
    usage = Usage.BOOTS
    item_kind = Kind.BOOTS
    reactive = True
    reagents = (Trigger.DAMAGE,)

    def default_extra(self) -> dict[str, Any]:
        return {"redistributedDamageMultiplier": 0.5, "absorbedDamageMultiplier": 0.75}

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv) or event.cause != "fall":
            return
        me = pos_of(player)
        count = 1
        for actor in self.plugin.actors_in(player.dimension):
            try:
                if same_actor(actor, player) or not is_living(actor) or not actor_alive(actor):
                    continue
                p = pos_of(actor)
                if math.hypot(p.x - me.x, p.z - me.z) <= 1.0 and -0.5 <= p.y - me.y <= 1.8:
                    count += 1
                    self.plugin.combat.damage(actor, event.damage * self.extra["redistributedDamageMultiplier"],
                                              "entity_attack", attacker=player)
            except Exception:  # noqa: BLE001
                continue
        event.damage = max(0.0, event.damage * (1 - self.extra["absorbedDamageMultiplier"] * count))
