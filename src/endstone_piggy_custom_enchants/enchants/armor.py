from __future__ import annotations

import math
import random
from typing import Any

from ..constants import INFINITE_TICKS, PROJECTILE_TYPES, Kind, Trigger, Usage
from ..enchant import CustomEnchant
from ..events import DamageEv, DeathEv, KnockbackEv
from ..items import Slot, held_item, is_axe, is_bow, is_sword
from ..util import (Vec3, actor_alive, entity_height, is_item_entity, is_living, is_player, pos_of, same_actor,
                    teleport_to)


class ArmorEnchant(CustomEnchant):
    usage = Usage.ARMOR_INVENTORY
    item_kind = Kind.ARMOR


class AntiKnockbackEnchant(ArmorEnchant):
    name = "Anti Knockback"
    max_level = 1
    reactive = True
    reagents = (Trigger.KNOCKBACK,)

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, KnockbackEv):
            stack = min(stack, 4)
            event.scale((4 - stack) / (5 - stack))


class _DamageAbsorber(ArmorEnchant):
    """Armored / Heavy / Tank: soak part of the damage dealt with a given weapon type."""

    reactive = True
    weapon_check = staticmethod(lambda item: False)

    def default_extra(self) -> dict[str, Any]:
        return {"absorbedDamageMultiplier": 0.2}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv) and is_player(event.damager):
            if self.weapon_check(held_item(event.damager)):
                event.damage = event.damage * max(0.0, 1 - self.extra["absorbedDamageMultiplier"] * level)


class ArmoredEnchant(_DamageAbsorber):
    name = "Armored"
    weapon_check = staticmethod(is_sword)


class HeavyEnchant(_DamageAbsorber):
    name = "Heavy"
    weapon_check = staticmethod(is_bow)


class TankEnchant(_DamageAbsorber):
    name = "Tank"
    rarity = "uncommon"
    weapon_check = staticmethod(is_axe)


class BerserkerEnchant(ArmorEnchant):
    name = "Berserker"
    cooldown_duration = 300
    reactive = True
    reagents = (Trigger.DAMAGE,)

    def default_extra(self):
        return {"minimumHealth": 4, "effectDurationMultiplier": 200, "effectAmplifierBase": 3,
                "effectAmplifierMultiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv):
            final = self.plugin.combat.estimate_final(player, event.damage)
            if player.health - final <= self.extra["minimumHealth"]:
                fx = self.plugin.effects
                if not fx.has(player, "strength"):
                    fx.add(player, "strength", self.extra["effectDurationMultiplier"] * level,
                           level * self.extra["effectAmplifierMultiplier"] + self.extra["effectAmplifierBase"], False)
                player.send_message("Your bloodloss makes your stronger!")


class CactusEnchant(ArmorEnchant):
    name = "Cactus"
    max_level = 1
    ticking = True
    tick_interval = 10

    def tick(self, player, item, slot, level):
        me = pos_of(player)
        for actor in self.plugin.actors_in(player.dimension):
            try:
                if not is_living(actor) or same_actor(actor, player) or not actor_alive(actor):
                    continue
                p = pos_of(actor)
                if math.hypot(p.x - me.x, p.z - me.z) <= 1.3 and -0.6 <= p.y - me.y <= 1.8:
                    if not self.plugin.allies.is_ally(player, actor):
                        self.plugin.combat.damage(actor, 1, "contact", attacker=player)
            except Exception:  # noqa: BLE001
                continue


class CloakingEnchant(ArmorEnchant):
    name = "Cloaking"
    rarity = "uncommon"
    cooldown_duration = 10
    reactive = True

    def default_extra(self):
        return {"durationMultiplier": 60}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv):
            self.plugin.effects.add(player, "invisibility", self.extra["durationMultiplier"] * level, 0, False)
            player.send_message("§8You have become invisible!")


class EndershiftEnchant(ArmorEnchant):
    name = "Endershift"
    cooldown_duration = 300
    reactive = True
    reagents = (Trigger.DAMAGE,)

    def default_extra(self):
        return {"speedDurationMultiplier": 200, "speedBaseAmplifier": 3, "speedAmplifierMultiplier": 1,
                "strengthDurationMultiplier": 200, "strengthBaseAmplifier": 3, "strengthAmplifierMultiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv) and player.health - self.plugin.combat.estimate_final(player, event.damage) <= 4:
            fx, e = self.plugin.effects, self.extra
            if not fx.has(player, "speed"):
                fx.add(player, "speed", e["speedDurationMultiplier"] * level,
                       level * e["speedAmplifierMultiplier"] + e["speedBaseAmplifier"], False)
            if not fx.has(player, "absorption"):
                fx.add(player, "absorption", e["strengthDurationMultiplier"] * level,
                       level * e["strengthAmplifierMultiplier"] + e["strengthBaseAmplifier"], False)
            player.send_message("You feel a rush of energy coming from your armor!")


class EnlightedEnchant(ArmorEnchant):
    name = "Enlighted"
    rarity = "uncommon"
    reactive = True

    def default_extra(self):
        return {"durationMultiplier": 60, "baseAmplifier": 0, "amplifierMultiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv):
            e = self.extra
            self.plugin.effects.add(player, "regeneration", e["durationMultiplier"] * level,
                                    level * e["amplifierMultiplier"] + e["baseAmplifier"], False)


class ForcefieldEnchant(ArmorEnchant):
    name = "Forcefield"
    rarity = "mythic"
    toggleable = True
    ticking = True

    def default_extra(self):
        return {"radiusMultiplier": 0.75}

    def tick(self, player, item, slot, level):
        power = self.get_stack(player)
        if power <= 0:
            return
        radius = power * self.extra["radiusMultiplier"]
        me = pos_of(player)
        for actor in self.plugin.actors_in(player.dimension):
            try:
                if same_actor(actor, player) or not actor_alive(actor):
                    continue
                p = pos_of(actor)
                if p.distance(me) > radius + 0.9:
                    continue
                if getattr(actor, "type", "") in PROJECTILE_TYPES:
                    # cannot reverse a velocity: incoming projectiles are destroyed instead
                    v = actor.velocity
                    incoming = (me - p).dot(Vec3(float(v.x), float(v.y), float(v.z))) > 0
                    if incoming:
                        actor.remove()
                elif is_living(actor) and not is_item_entity(actor) and not self.plugin.allies.is_ally(player, actor):
                    away = Vec3(p.x - me.x, 0.0, p.z - me.z).normalized() * 0.75
                    if away.length() > 0:
                        target = p + away
                        if self.plugin.world.is_passable(actor.dimension, *target.floor()):
                            teleport_to(actor, target)
            except Exception:  # noqa: BLE001
                continue
        if self.plugin.tick_count % 5 == 0:
            diff = max(radius / power, 0.15)
            theta = 0.0
            while theta <= 2 * math.pi:
                self.plugin.world.particle(
                    player.dimension, "minecraft:enchanting_table_particle",
                    me + Vec3(radius * math.sin(theta), 0.5, radius * math.cos(theta)), 32)
                theta += diff


class _ScaleEnchant(ArmorEnchant):
    """Grow / Shrink need Actor scale, which Endstone 0.11 does not expose."""

    unsupported_reason = "Endstone has no API to change an entity's scale."
    rarity = "uncommon"
    cooldown_duration = 75
    toggleable = True


class GrowEnchant(_ScaleEnchant):
    name = "Grow"

    def default_extra(self):
        return {"power": 60 * 20, "base": 0.3, "multiplier": 0.0125}


class ShrinkEnchant(_ScaleEnchant):
    name = "Shrink"
    max_level = 2

    def default_extra(self):
        return {"power": 60 * 20, "base": 0.7, "multiplier": 0.0125}


class MoltenEnchant(ArmorEnchant):
    name = "Molten"
    reactive = True

    def default_extra(self):
        return {"durationMultiplier": 3}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DamageEv) and is_living(event.damager):
            self.plugin.combat.ignite(event.damager, min(self.extra["durationMultiplier"] * level, 1638))


class OverloadEnchant(ArmorEnchant):
    name = "Overload"
    rarity = "mythic"
    max_level = 3
    toggleable = True

    def default_extra(self):
        return {"multiplier": 2}

    def toggle(self, player, item, slot, level, toggle):
        delta = self.extra["multiplier"] * level * (1 if toggle else -1)
        old_max = float(player.max_health)
        new_max = max(1.0, old_max + delta)
        ratio = new_max / old_max if old_max else 1.0
        player.max_health = int(new_max)
        player.health = int(max(1, min(new_max, round(player.health * ratio))))


class PoisonousCloudEnchant(ArmorEnchant):
    name = "Poisonous Cloud"
    max_level = 3
    ticking = True

    def default_extra(self):
        return {"radiusMultiplier": 3, "durationMultiplier": 100, "baseAmplifier": -1, "amplifierMultiplier": 1}

    def tick(self, player, item, slot, level):
        e = self.extra
        radius = level * e["radiusMultiplier"]
        me = pos_of(player)
        fx = self.plugin.effects
        for actor in self.plugin.actors_in(player.dimension):
            try:
                if same_actor(actor, player) or not is_living(actor) or not actor_alive(actor):
                    continue
                if self.plugin.allies.is_ally(player, actor) or pos_of(actor).distance(me) > radius:
                    continue
                current = fx.get(actor, "poison")
                if current is None or current.expires_tick - self.plugin.tick_count < 20:
                    fx.add(actor, "poison", level * e["durationMultiplier"],
                           level * e["amplifierMultiplier"] + e["baseAmplifier"], False)
            except Exception:  # noqa: BLE001
                continue
        if self.plugin.tick_count % 20 == 0:
            for _ in range(int(6 * level)):
                off = Vec3(random.uniform(-radius, radius), random.uniform(0, radius), random.uniform(-radius, radius))
                self.plugin.world.particle(player.dimension, "minecraft:villager_happy", me + off, 32)


class ReviveEnchant(ArmorEnchant):
    name = "Revive"
    reactive = True
    reagents = (Trigger.DAMAGE,)

    def default_extra(self):
        return {"nauseaDuration": 600, "slownessDuration": 600}

    def react(self, player, item, slot: Slot, event, level, stack):
        if not isinstance(event, DamageEv):
            return
        if self.plugin.combat.estimate_final(player, event.damage) < player.health:
            return
        mgr = self.plugin.manager
        if level > 1:
            mgr.add_enchant(item, self, level - 1, check_compatibility=False)
        else:
            mgr.remove_enchant(item, self)
        slot.set(item)
        self.plugin.engine.invalidate(player)
        fx = self.plugin.effects
        fx.clear(player)
        player.health = int(player.max_health)
        fx.add(player, "saturation", 20, 19, False)
        try:
            player.exp_level = 0
            player.exp_progress = 0.0
        except Exception:  # noqa: BLE001
            pass
        fx.add(player, "nausea", self.extra["nauseaDuration"], 0, False)
        fx.add(player, "slowness", self.extra["slownessDuration"], 0, False)
        me = pos_of(player)
        for i in range(0, 20):
            self.plugin.world.particle(player.dimension, "minecraft:basic_flame_particle", me + Vec3(0, i * 0.75, 0), 48)
        player.send_tip("§aYou were revived.")
        event.cancel()


class SelfDestructEnchant(ArmorEnchant):
    name = "Self Destruct"
    reactive = True
    reagents = (Trigger.DEATH,)

    def default_extra(self):
        return {"tntAmountMultiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, DeathEv):
            pos = pos_of(player)
            world_damage = bool(self.plugin.cfg("world-damage.self-destruct", False))
            for _ in range(int(level * self.extra["tntAmountMultiplier"])):
                offset = Vec3(random.uniform(-1, 0.5), 0.1, random.uniform(-1, 0.5))
                self.plugin.world.spawn_tnt(player.dimension, pos + offset, 40, player, world_damage)


class ShieldedEnchant(ArmorEnchant):
    name = "Shielded"
    max_level = 3
    toggleable = True

    def toggle(self, player, item, slot, level, toggle):
        fx = self.plugin.effects
        if not toggle and self.get_armor_stack(player) == 0:
            fx.remove(player, "resistance")
            return
        fx.remove(player, "resistance")
        fx.add(player, "resistance", INFINITE_TICKS, max(0, self.get_stack(player) - 1), False)
