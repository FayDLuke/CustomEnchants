from __future__ import annotations

import math
import random
from typing import Any

from endstone.inventory import ItemStack

from ..constants import Kind, Trigger, Usage
from ..enchant import CustomEnchant
from ..events import DamageEv, ProjectileHitBlockEv, ShootEv
from ..items import Slot
from ..util import (ActorRef, Vec3, actor_alive, entity_height, is_living, is_player, pos_of, same_actor,
                    make_location, teleport_to, yaw_pitch_for)


class BowEnchant(CustomEnchant):
    usage = Usage.HAND
    item_kind = Kind.BOW
    reactive = True


class _ChildDamage(BowEnchant):
    reagents = (Trigger.DAMAGE_BY_CHILD,)


class AutoAimEnchant(BowEnchant):
    name = "Auto Aim"
    rarity = "mythic"
    max_level = 1
    reactive = False
    ticking = True

    def default_extra(self) -> dict[str, Any]:
        return {"radiusMultiplier": 50}

    def tick(self, player, item, slot, level):
        if not (player.is_sneaking and player.is_on_ground):
            return
        target = self.plugin.projectiles.nearest_target(
            pos_of(player), player.dimension, level * self.extra["radiusMultiplier"], player)
        if target is None:
            return
        rel = pos_of(target) - pos_of(player)
        length = math.hypot(rel.x, rel.z)
        if int(length) == 0:
            return
        yaw = math.degrees(math.atan2(rel.z, rel.x)) - 90
        g = 0.006
        tmp = 1 - g * (g * length * length + 2 * rel.y)
        if tmp < 0:
            return
        pitch = 180 / math.pi * -math.atan((1 - math.sqrt(tmp)) / (g * length))
        teleport_to(player, pos_of(player), yaw, pitch)


class BombardmentEnchant(_ChildDamage):
    name = "Bombardment"

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv):
            return
        victim = event.entity
        dim = victim.dimension
        start = pos_of(victim)
        top = min(start.y + 45, 318.0)
        world_damage = bool(self.plugin.cfg("world-damage.bombardment", self.plugin.cfg("world-damage.missile", False)))
        count = 3 + level
        ref = ActorRef(player)

        def boom(sim, pos: Vec3) -> None:
            who = self.plugin.resolve(ref)
            center = Vec3(pos.x, math.floor(pos.y) + 1.0, pos.z)
            for _ in range(count):
                self.plugin.world.spawn_tnt(dim, center, 0, who, world_damage)

        self.plugin.projectiles.spawn_sim(
            player, item, "minecraft:tnt", Vec3(start.x, top, start.z), Vec3(0, -5.0, 0), dim,
            gravity=0.0, drag=0.0, damage=0, on_entity=lambda sim, _v: boom(sim, sim.pos), on_block=boom, life=120)


class BountyHunterEnchant(_ChildDamage):
    name = "Bounty Hunter"
    rarity = "uncommon"
    cooldown_duration = 30

    def default_extra(self) -> dict[str, Any]:
        return {"base": 7, "multiplier": 1}

    @staticmethod
    def bounty() -> str:
        roll = random.randint(0, 75)
        threshold = 2.5
        if roll < threshold:
            return "minecraft:emerald"
        threshold += 5
        if roll < threshold:
            return "minecraft:diamond"
        threshold += 15
        if roll < threshold:
            return "minecraft:gold_ingot"
        threshold += 27.5
        if roll < threshold:
            return "minecraft:iron_ingot"
        return "minecraft:coal"

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv):
            reward = ItemStack(self.bounty(), random.randint(1, int(self.extra["base"] + level * self.extra["multiplier"])))
            leftover = player.inventory.add_item(reward)
            for rest in (leftover or {}).values():
                player.dimension.drop_item(player.location, rest)


class GrapplingEnchant(BowEnchant):
    name = "Grappling"
    max_level = 1
    reagents = (Trigger.DAMAGE_BY_CHILD, Trigger.PROJECTILE_HIT_BLOCK)

    def _pull(self, mover: Any, get_target, distance: float, fall_owner: Any) -> None:
        speed = min(2.5, 1.0 + 0.07 * distance)
        ticks = int(distance / max(speed, 0.5)) + 25
        self.plugin.nofall.set(fall_owner, False, ticks / 20 + 3)
        self.plugin.motion.pull(mover, get_target, speed=speed, max_ticks=ticks, stop_distance=1.6)

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv):
            victim_ref, owner_ref = ActorRef(event.entity), ActorRef(player)

            def pull_entity() -> None:
                victim, owner = self.plugin.resolve(victim_ref), self.plugin.resolve(owner_ref)
                if victim is None or owner is None or not actor_alive(victim):
                    return
                distance = pos_of(owner).distance(pos_of(victim))
                if distance > 0:
                    self._pull(victim, lambda: (lambda o: pos_of(o) if o is not None else None)(self.plugin.resolve(owner_ref)),
                               distance, player)

            self.plugin.later(pull_entity, 1)
        elif isinstance(event, ProjectileHitBlockEv):
            hit = event.position
            distance = pos_of(player).distance(hit)
            if distance <= 0:
                return
            self._pull(player, lambda: hit, distance, player)


class HeadhunterEnchant(_ChildDamage):
    name = "Headhunter"
    rarity = "uncommon"

    def default_extra(self) -> dict[str, Any]:
        return {"additionalMultiplier": 0.1}

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv) or event.child_pos is None:
            return
        victim = event.entity
        eye = 1.62 if is_player(victim) else entity_height(victim) * 0.9
        if event.child_pos.y > pos_of(victim).y + eye:
            event.damage = event.damage * (1 + self.extra["additionalMultiplier"] * level)


class HealingEnchant(_ChildDamage):
    name = "Healing"

    def default_extra(self) -> dict[str, Any]:
        return {"healthReplenishMultiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv):
            dealt = self.plugin.combat.estimate_final(event.entity, event.damage)
            self.plugin.combat.heal(player, dealt + level * self.extra["healthReplenishMultiplier"])
            event.damage = 0


class MissileEnchant(BowEnchant):
    name = "Missile"
    reagents = (Trigger.PROJECTILE_HIT_BLOCK,)

    def default_extra(self) -> dict[str, Any]:
        return {"multiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, ProjectileHitBlockEv):
            return
        world_damage = bool(self.plugin.cfg("world-damage.missile", False))
        for _ in range(int(level * self.extra["multiplier"]) + 1):
            self.plugin.world.spawn_tnt(event.dimension, event.position, 40, player, world_damage)
        event.remove_projectile = True


class MolotovEnchant(_ChildDamage):
    name = "Molotov"
    rarity = "uncommon"

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv) or not self.plugin.cfg("world-damage.molotov", True):
            return
        victim = event.entity
        dim = victim.dimension
        cx, cy, cz = pos_of(victim).floor()
        placed = []
        for dx in range(-level, level + 1):
            for dz in range(-level, level + 1):
                x, y, z = cx + dx, cy, cz + dz
                if self.plugin.world.block_id(dim, x, y, z) == "minecraft:air":
                    self.plugin.world.set_block(dim, x, y, z, "minecraft:fire")
                    placed.append((x, y, z))

        def cleanup() -> None:
            for x, y, z in placed:
                if self.plugin.world.block_id(dim, x, y, z) == "minecraft:fire":
                    self.plugin.world.set_block(dim, x, y, z, "minecraft:air")

        self.plugin.later(cleanup, 120)


class ParalyzeEnchant(_ChildDamage):
    name = "Paralyze"

    def default_extra(self) -> dict[str, Any]:
        return {"slownessBaseDuration": 40, "slownessDurationMultiplier": 20, "slownessBaseAmplifier": 4,
                "slownessAmplifierMultiplier": 1, "blindnessBaseDuration": 40, "blindnessDurationMultiplier": 20,
                "weaknessBaseDuration": 40, "weaknessDurationMultiplier": 20, "weaknessBaseAmplifier": 4,
                "weaknessAmplifierMultiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv) or not is_living(event.entity):
            return
        e, fx, victim = self.extra, self.plugin.effects, event.entity
        if not fx.has(victim, "slowness"):
            fx.add(victim, "slowness", e["slownessBaseDuration"] + level * e["slownessDurationMultiplier"],
                   e["slownessBaseAmplifier"] + level * e["slownessAmplifierMultiplier"], False)
        if not fx.has(victim, "blindness"):
            fx.add(victim, "blindness", e["blindnessBaseDuration"] + level * e["blindnessDurationMultiplier"], 1, False)
        if not fx.has(victim, "weakness"):
            fx.add(victim, "weakness", e["weaknessBaseDuration"] + level * e["weaknessDurationMultiplier"],
                   e["weaknessBaseAmplifier"] + level * e["weaknessAmplifierMultiplier"], False)


class PiercingEnchant(_ChildDamage):
    """Damage is applied before armor, so the raw value is raised by the estimated armor reduction."""

    name = "Piercing"
    max_level = 1

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv) and is_player(event.entity):
            event.damage = self.plugin.combat.undo_armor(event.entity, event.damage)


class ShuffleEnchant(_ChildDamage):
    name = "Shuffle"
    max_level = 1

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, DamageEv) or not is_living(event.entity):
            return
        victim = event.entity
        mine, theirs = player.location, victim.location
        player.teleport(theirs)
        victim.teleport(mine)
        name = victim.name_tag or victim.name
        if is_player(victim):
            victim.send_message(f"§5You have switched positions with {player.name}")
        player.send_message(f"§5You have switched positions with {name}")


class VolleyEnchant(BowEnchant):
    name = "Volley"
    rarity = "uncommon"
    reagents = (Trigger.SHOOT_BOW,)

    def default_extra(self) -> dict[str, Any]:
        return {"base": 1, "multiplier": 2}

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, ShootEv):
            return
        amount = int(self.extra["base"] + self.extra["multiplier"] * level)
        if amount < 2:
            return
        step = (45 / (amount - 1)) * math.pi / 180
        pitch = (player.location.pitch + 90) * math.pi / 180
        yaw = (player.location.yaw + 90 - 45 / 2) * math.pi / 180
        speed = max(event.velocity.length(), 1.0)
        eye = pos_of(player) + Vec3(0, 1.62, 0)
        for i in range(amount):
            direction = Vec3(math.sin(pitch) * math.cos(yaw + step * i), math.cos(pitch),
                             math.sin(pitch) * math.sin(yaw + step * i)).normalized()
            self.plugin.projectiles.spawn_sim(
                player, item, "minecraft:arrow", eye, direction * speed, player.dimension,
                gravity=0.05, drag=0.01, damage=2.0, life=100,
                on_entity=self.plugin.projectiles.default_entity_hit)
        event.replaced = True


PORK_LEVELS = {
    # level: (damage, dinnerbone, zombie, drop id, drop name)
    1: (1, False, False, None, ""),
    2: (2, False, False, "minecraft:porkchop", "Mysterious Raw Pork"),
    3: (2, False, False, "minecraft:cooked_porkchop", "Mysterious Cooked Pork"),
    4: (3, True, False, "minecraft:cooked_porkchop", "Mysterious Cooked Pork"),
    5: (5, False, True, "minecraft:rotten_flesh", "Mysterious Rotten Pork"),
    6: (6, True, True, "minecraft:rotten_flesh", "Mysterious Rotten Pork"),
}


class ProjectileChangingEnchant(BowEnchant):
    """Blaze / Homing / Porkified / Wither Skull: swap (or steer) the arrow that was just fired."""

    priority = 2
    reagents = (Trigger.SHOOT_BOW,)

    def __init__(self, plugin: Any, enchant_id: int, name: str, kind: str, max_level: int = 1, rarity: str = "rare") -> None:
        self.name = name
        self.projectile_kind = kind
        self.max_level = max_level
        self.rarity = rarity
        super().__init__(plugin, enchant_id)

    def react(self, player, item, slot: Slot, event, level, stack):
        if not isinstance(event, ShootEv):
            return
        pm = self.plugin.projectiles
        if self.projectile_kind == "homing":
            pm.homing[event.arrow_id] = level
            return
        pos, vel, dim = event.position, event.velocity, player.dimension
        if self.projectile_kind == "blaze":
            sim = pm.spawn_sim(player, item, "minecraft:small_fireball", pos, vel, dim, gravity=0.05, drag=0.01,
                               damage=5, on_entity=self._blaze_entity, on_block=self._blaze_block)
        elif self.projectile_kind == "witherskull":
            sim = pm.spawn_sim(player, item, "minecraft:wither_skull", pos, vel, dim, gravity=0.05, drag=0.01,
                               damage=0, on_entity=self._skull_entity)
        else:
            sim = self._porkified(player, item, pos, vel, dim, level)
        if sim is not None:
            event.replaced = True

    # Blaze
    def _blaze_entity(self, sim, victim) -> None:
        owner = self.plugin.resolve(sim.owner) if sim.owner else None
        if not (owner is not None and is_player(owner) and self.plugin.allies.is_ally(owner, victim)):
            self.plugin.combat.ignite(victim, 5)
        self.plugin.projectiles.default_entity_hit(sim, victim)

    def _blaze_block(self, sim, pos: Vec3) -> None:
        if not self.plugin.cfg("world-damage.blaze", True):
            return
        x, y, z = (math.floor(sim.pos.x - sim.vel.x * 0.5), math.floor(sim.pos.y - sim.vel.y * 0.5),
                   math.floor(sim.pos.z - sim.vel.z * 0.5))
        world = self.plugin.world
        if world.block_id(sim.dimension, x, y, z) == "minecraft:air":
            world.set_block(sim.dimension, x, y, z, "minecraft:fire")
            self.plugin.later(lambda: world.block_id(sim.dimension, x, y, z) == "minecraft:fire"
                              and world.set_block(sim.dimension, x, y, z, "minecraft:air"), 100)

    # Wither skull
    def _skull_entity(self, sim, victim) -> None:
        owner = self.plugin.resolve(sim.owner) if sim.owner else None
        if is_living(victim) and not (owner is not None and is_player(owner) and self.plugin.allies.is_ally(owner, victim)):
            self.plugin.effects.add(victim, "wither", 800, 1, True)

    # Porkified
    def _porkified(self, player, item, pos, vel, dim, level):
        level = max(1, min(level, 6))
        damage, dinnerbone, zombie, drop_id, drop_name = PORK_LEVELS[level]
        counter = {"n": 0}

        def on_tick(sim) -> None:
            counter["n"] += 1
            if drop_id and counter["n"] % 2 == 0:
                stack = ItemStack(drop_id, 1)
                meta = stack.item_meta
                meta.display_name = "§r§f" + drop_name
                stack.set_item_meta(meta)
                sim.dimension.drop_item(make_location(sim.dimension, sim.pos), stack)

        sim = self.plugin.projectiles.spawn_sim(
            player, item, "minecraft:zombie_pigman" if zombie else "minecraft:pig", pos, vel, dim,
            gravity=0.05, drag=0.01, damage=damage, on_entity=self.plugin.projectiles.default_entity_hit,
            on_tick=on_tick)
        if sim is not None and dinnerbone and sim.visual is not None:
            visual = self.plugin.resolve(sim.visual)
            if visual is not None:
                visual.name_tag = "Dinnerbone"
        return sim
