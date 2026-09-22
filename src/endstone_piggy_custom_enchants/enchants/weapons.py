from __future__ import annotations

import random
import time
from typing import Any

from ..constants import BAD_EFFECTS, Kind, Usage
from ..enchant import CustomEnchant
from ..events import DamageEv
from ..util import (ActorRef, Vec3, actor_alive, is_living, is_player, pos_of, same_actor, uvarint, varint)


class WeaponEnchant(CustomEnchant):
    usage = Usage.HAND
    item_kind = Kind.WEAPON
    reactive = True


class BlessedEnchant(WeaponEnchant):
    name = "Blessed"
    rarity = "uncommon"
    max_level = 3

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv):
            for effect in BAD_EFFECTS:
                self.plugin.effects.remove(player, effect)


class DeathbringerEnchant(WeaponEnchant):
    name = "Deathbringer"

    def default_extra(self) -> dict[str, Any]:
        return {"base": 2, "multiplier": 0.1}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv):
            event.damage = event.damage + self.extra["base"] + level * self.extra["multiplier"]


class DeepWoundsEnchant(WeaponEnchant):
    name = "Deep Wounds"
    cooldown_duration = 7

    def __init__(self, plugin: Any, enchant_id: int) -> None:
        super().__init__(plugin, enchant_id)
        self.bleeding: dict[Any, Any] = {}

    def default_extra(self) -> dict[str, Any]:
        return {"interval": 20, "durationMultiplier": 20, "base": 1, "multiplier": 0.066}

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv):
            return
        victim = event.entity
        ref = ActorRef(victim)
        if ref in self.bleeding:
            return
        end_time = time.time() + self.extra["durationMultiplier"] * level

        def bleed() -> bool:
            target = self.plugin.resolve(ref)
            if target is None or not actor_alive(target) or end_time < time.time():
                self.bleeding.pop(ref, None)
                return False
            self.plugin.combat.damage(target, self.extra["base"] + target.health * self.extra["multiplier"], "magic")
            self.plugin.world.particle(target.dimension, "minecraft:redstone_ore_dust_particle", pos_of(target) + Vec3(0, 1, 0), 32)
            return True

        self.bleeding[ref] = self.plugin.repeat(bleed, int(self.extra["interval"]), int(self.extra["interval"]))


class DisarmingEnchant(WeaponEnchant):
    name = "Disarming"
    rarity = "uncommon"

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv) or not is_player(event.entity):
            return
        victim = event.entity
        choices = [(i, s) for i, s in enumerate(victim.inventory.contents) if s is not None]
        if choices:
            index, stack_item = random.choice(choices)
            victim.inventory.set_item(index, None)
            victim.dimension.drop_item(victim.location, stack_item)


class DisarmorEnchant(WeaponEnchant):
    name = "Disarmor"
    rarity = "uncommon"

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv) or not is_player(event.entity):
            return
        victim = event.entity
        pieces = [n for n in ("helmet", "chestplate", "leggings", "boots") if getattr(victim.inventory, n) is not None]
        if pieces:
            name = random.choice(pieces)
            piece = getattr(victim.inventory, name)
            setattr(victim.inventory, name, None)
            victim.dimension.drop_item(victim.location, piece)


class GooeyEnchant(WeaponEnchant):
    name = "Gooey"

    def default_extra(self) -> dict[str, Any]:
        return {"base": 0.75, "multiplier": 0.15}

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv):
            return
        ref = ActorRef(event.entity)
        power = level * self.extra["multiplier"] + self.extra["base"]

        def launch() -> None:
            target = self.plugin.resolve(ref)
            if target is not None and actor_alive(target):
                self.plugin.motion.launch(target, Vec3(0, power, 0), max_ticks=60)

        self.plugin.later(launch, 1)


class HallucinationEnchant(WeaponEnchant):
    """Fake bedrock cage around the victim, sent as UpdateBlock packets only to that player."""

    name = "Hallucination"
    rarity = "mythic"
    UPDATE_BLOCK_ID = 21

    def __init__(self, plugin: Any, enchant_id: int) -> None:
        super().__init__(plugin, enchant_id)
        self.hallucinating: set[str] = set()

    def default_extra(self) -> dict[str, Any]:
        return {"duration": 20 * 60, "resendInterval": 10}

    def _send(self, victim: Any, x: int, y: int, z: int, runtime_id: int) -> None:
        payload = varint(x) + uvarint(y) + varint(z) + uvarint(runtime_id) + uvarint(2) + uvarint(0)
        victim.send_packet(self.UPDATE_BLOCK_ID, payload)

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv) or not is_player(event.entity):
            return
        victim = event.entity
        if victim.name in self.hallucinating:
            return
        self.hallucinating.add(victim.name)
        ref = ActorRef(victim)
        p0 = pos_of(victim)
        ox, oy, oz = round(p0.x), round(p0.y), round(p0.z)
        dim = victim.dimension
        server = self.plugin.server
        bedrock = server.create_block_data("minecraft:bedrock").runtime_id
        lava = server.create_block_data("minecraft:lava").runtime_id
        cage = [(x, y, z) for x in range(ox - 1, ox + 2) for y in range(oy - 1, oy + 3) for z in range(oz - 1, oz + 2)]
        started = self.plugin.tick_count

        def restore(target: Any) -> None:
            for x, y, z in [(ox + a, oy + b, oz + c) for a in (-1, 0, 1) for b in range(-1, 4) for c in (-1, 0, 1)]:
                try:
                    self._send(target, x, y, z, dim.get_block_at(x, y, z).data.runtime_id)
                except Exception:  # noqa: BLE001
                    continue

        def tick() -> bool:
            target = self.plugin.resolve(ref)
            if target is None or self.plugin.tick_count - started >= self.extra["duration"]:
                if target is not None:
                    restore(target)
                self.hallucinating.discard(victim.name)
                return False
            for x, y, z in cage:
                self._send(target, x, y, z, lava if (x, y, z) == (ox, oy, oz) else bedrock)
            if (self.plugin.tick_count - started) % 20 == 0:
                target.send_tip("§cYou seem to be hallucinating...")
            return True

        self.plugin.repeat(tick, 1, int(self.extra["resendInterval"]))


class LifestealEnchant(WeaponEnchant):
    name = "Lifesteal"
    rarity = "common"

    def default_extra(self) -> dict[str, Any]:
        return {"base": 2, "multiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv):
            self.plugin.combat.heal(player, self.extra["base"] + level * self.extra["multiplier"])


class LightningEnchant(WeaponEnchant):
    name = "Lightning"
    rarity = "mythic"

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv):
            victim = event.entity
            victim.dimension.spawn_actor(victim.location, "minecraft:lightning_bolt")


class VampireEnchant(WeaponEnchant):
    name = "Vampire"
    rarity = "uncommon"
    max_level = 1
    cooldown_duration = 5

    def default_extra(self) -> dict[str, Any]:
        return {"healthMultiplier": 0.5, "foodMultiplier": 0.5}

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv):
            return
        dealt = self.plugin.combat.estimate_final(event.entity, event.damage)
        self.plugin.combat.heal(player, dealt * self.extra["healthMultiplier"])
        if self.extra["foodMultiplier"] > 0:
            self.plugin.effects.add(player, "saturation", 1, 0, False)
