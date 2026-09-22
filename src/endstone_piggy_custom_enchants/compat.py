"""Bridges the gaps of the Endstone API (no effect, damage-with-source, fire or block-destroy calls)
by driving the vanilla commands.  Everything here is best-effort and never raises into the caller."""
from __future__ import annotations

import math
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator

from endstone import Player
from endstone.command import CommandSenderWrapper

from .constants import INFINITE_SECONDS, INFINITE_TICKS, PASSABLE_BLOCKS
from .util import Vec3, actor_alive, pos_of

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants

TARGET_TAG = "piggyce_target"
DAMAGER_TAG = "piggyce_damager"


def effect_name(effect: str) -> str:
    return effect.replace("minecraft:", "")


def dimension_command_prefix(dimension: Any) -> str:
    kind = str(getattr(getattr(dimension, "type", None), "name", "")).upper()
    if not kind:
        kind = str(getattr(dimension, "name", "")).upper().replace(" ", "_")
    if "NETHER" in kind:
        return "execute in nether run "
    if kind in ("THE_END", "THEEND", "END"):
        return "execute in the_end run "
    return ""


class Commands:
    def __init__(self, plugin: "PiggyCustomEnchants") -> None:
        self.plugin = plugin
        self._sender = CommandSenderWrapper(
            plugin.server.command_sender, on_message=lambda _m: None, on_error=lambda _m: None
        )

    def run(self, command: str) -> bool:
        try:
            return bool(self.plugin.server.dispatch_command(self._sender, command))
        except Exception as exc:  # noqa: BLE001
            self.plugin.debug(f"command failed: {command!r}: {exc}")
            return False

    @staticmethod
    def prefix(actor: Any) -> str:
        """Non-player selectors only see the executor's dimension, so wrap them in `execute in`."""
        if actor is None or isinstance(actor, Player):
            return ""
        try:
            return dimension_command_prefix(actor.dimension)
        except Exception:  # noqa: BLE001
            return ""

    @contextmanager
    def selector(self, actor: Any, tag: str = TARGET_TAG) -> Iterator[str | None]:
        """Yields a selector string that resolves to exactly `actor` (players by name, others by temp tag)."""
        if actor is None:
            yield None
            return
        if isinstance(actor, Player):
            yield '"' + actor.name.replace('"', "") + '"'
            return
        tagged = False
        try:
            tagged = bool(actor.add_scoreboard_tag(tag))
        except Exception:  # noqa: BLE001
            pass
        try:
            yield f"@e[tag={tag}]" if tagged else None
        finally:
            if tagged:
                try:
                    actor.remove_scoreboard_tag(tag)
                except Exception:  # noqa: BLE001
                    pass


@dataclass
class TrackedEffect:
    amplifier: int
    expires_tick: float


class EffectManager:
    """Potion effects through /effect. Effects cannot be read back, so applied ones are tracked here."""

    def __init__(self, plugin: "PiggyCustomEnchants") -> None:
        self.plugin = plugin
        self._tracked: dict[tuple[Any, str], TrackedEffect] = {}

    @staticmethod
    def _owner(target: Any) -> Any:
        return target.unique_id if isinstance(target, Player) else target.id

    def add(self, target: Any, effect: str, ticks: int, amplifier: int = 0, visible: bool = False) -> None:
        if target is None or not actor_alive(target) and not isinstance(target, Player):
            return
        name = effect_name(effect)
        amplifier = max(0, min(int(amplifier), 255))
        infinite = ticks >= INFINITE_TICKS
        seconds = INFINITE_SECONDS if infinite else max(1, min(INFINITE_SECONDS, math.ceil(ticks / 20)))
        with self.plugin.runner.selector(target) as sel:
            if sel is None:
                return
            hide = "false" if visible else "true"
            self.plugin.runner.run(
                f"{self.plugin.runner.prefix(target)}effect {sel} {name} {seconds} {amplifier} {hide}"
            )
        expires = math.inf if infinite else self.plugin.tick_count + ticks
        self._tracked[(self._owner(target), name)] = TrackedEffect(amplifier, expires)

    def remove(self, target: Any, effect: str) -> None:
        if target is None:
            return
        name = effect_name(effect)
        with self.plugin.runner.selector(target) as sel:
            if sel is not None:
                self.plugin.runner.run(f"{self.plugin.runner.prefix(target)}effect {sel} {name} 0")
        self._tracked.pop((self._owner(target), name), None)

    def clear(self, target: Any) -> None:
        with self.plugin.runner.selector(target) as sel:
            if sel is not None:
                self.plugin.runner.run(f"{self.plugin.runner.prefix(target)}effect {sel} clear")
        self.forget(target)

    def get(self, target: Any, effect: str) -> TrackedEffect | None:
        key = (self._owner(target), effect_name(effect))
        tracked = self._tracked.get(key)
        if tracked is None:
            return None
        if tracked.expires_tick <= self.plugin.tick_count:
            del self._tracked[key]
            return None
        return tracked

    def has(self, target: Any, effect: str) -> bool:
        return self.get(target, effect) is not None

    def forget(self, target: Any) -> None:
        owner = self._owner(target)
        for key in [k for k in self._tracked if k[0] == owner]:
            del self._tracked[key]


# armor points per piece (helmet, chestplate, leggings, boots), used to estimate post-armor damage
ARMOR_POINTS = {
    "leather": (1, 3, 2, 1), "chainmail": (2, 5, 4, 1), "iron": (2, 6, 5, 2), "golden": (2, 5, 3, 1),
    "diamond": (3, 8, 6, 3), "netherite": (3, 8, 6, 3), "copper": (2, 4, 3, 1), "turtle": (2, 0, 0, 0),
}
_ARMOR_SLOT_INDEX = {"_helmet": 0, "_chestplate": 1, "_leggings": 2, "_boots": 3}


def armor_points(player: Any) -> int:
    total = 0
    for slot_name, suffix_idx in (("helmet", 0), ("chestplate", 1), ("leggings", 2), ("boots", 3)):
        try:
            item = getattr(player.inventory, slot_name)
            ident = str(item.type.id).replace("minecraft:", "") if item is not None else ""
        except Exception:  # noqa: BLE001
            continue
        for material, points in ARMOR_POINTS.items():
            if ident.startswith(material):
                total += points[suffix_idx]
                break
    return total


class Combat:
    def __init__(self, plugin: "PiggyCustomEnchants") -> None:
        self.plugin = plugin

    @staticmethod
    def estimate_final(victim: Any, raw: float) -> float:
        """ActorDamageEvent.damage is pre-armor; approximate what will actually be dealt."""
        if isinstance(victim, Player):
            return raw * (1 - min(20, armor_points(victim)) * 0.04)
        return raw

    @staticmethod
    def undo_armor(victim: Any, wanted_final: float) -> float:
        """Raw damage that ends up as `wanted_final` after armor (used by Piercing)."""
        if isinstance(victim, Player):
            factor = 1 - min(20, armor_points(victim)) * 0.04
            return wanted_final / max(factor, 0.2)
        return wanted_final

    def damage(
        self, victim: Any, amount: float, cause: str = "entity_attack", attacker: Any = None, child: Any = None
    ) -> None:
        """Hurts `victim` through /damage. `child` marks the damage as coming from a tracked projectile."""
        if victim is None or amount <= 0:
            return
        value = max(1, int(round(amount)))
        pre = self.plugin.runner.prefix(victim)
        with self.plugin.runner.selector(victim, TARGET_TAG) as vsel:
            if vsel is None:
                return
            if attacker is not None:
                with self.plugin.runner.selector(attacker, DAMAGER_TAG) as asel:
                    cmd = f"{pre}damage {vsel} {value} {cause}" + (f" entity {asel}" if asel else "")
                    self._run_damage(cmd, victim, attacker, child)
            else:
                self._run_damage(f"{pre}damage {vsel} {value} {cause}", victim, None, child)

    def _run_damage(self, cmd: str, victim: Any, attacker: Any, child: Any) -> None:
        if child is not None:
            with self.plugin.damage_as_child(child, attacker):
                self.plugin.runner.run(cmd)
        else:
            with self.plugin.suppress_damage():
                self.plugin.runner.run(cmd)

    @staticmethod
    def heal(target: Any, amount: float) -> None:
        try:
            target.health = int(min(target.max_health, max(0, target.health + round(amount))))
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def set_health(target: Any, value: float) -> None:
        try:
            target.health = int(max(1, min(target.max_health, round(value))))
        except Exception:  # noqa: BLE001
            pass

    def ignite(self, actor: Any, seconds: float) -> None:
        """No set-on-fire API exists; a short-lived fire block at the feet ignites the entity."""
        if not self.plugin.cfg("emulate-ignite", True):
            return
        try:
            x, y, z = pos_of(actor).floor()
            dim = actor.dimension
            block = dim.get_block_at(x, y, z)
            if block.type not in PASSABLE_BLOCKS or block.type in ("minecraft:water", "minecraft:flowing_water"):
                return
            block.set_type("minecraft:fire")
            ticks = max(20, int(seconds * 20))

            def _cleanup() -> None:
                b = dim.get_block_at(x, y, z)
                if b.type == "minecraft:fire":
                    b.set_type("minecraft:air")

            self.plugin.later(_cleanup, ticks)
        except Exception as exc:  # noqa: BLE001
            self.plugin.debug(f"ignite failed: {exc}")


class WorldOps:
    def __init__(self, plugin: "PiggyCustomEnchants") -> None:
        self.plugin = plugin

    def viewers(self, dimension: Any, pos: Vec3, radius: float = 48.0) -> list[Player]:
        out = []
        for p in self.plugin.server.online_players:
            try:
                if p.dimension.name == dimension.name and pos_of(p).distance(pos) <= radius:
                    out.append(p)
            except Exception:  # noqa: BLE001
                continue
        return out

    def particle(self, dimension: Any, name: str, pos: Vec3, radius: float = 48.0) -> None:
        for p in self.viewers(dimension, pos, radius):
            try:
                p.spawn_particle(name, pos.x, pos.y, pos.z)
            except Exception:  # noqa: BLE001
                return

    def sound(self, dimension: Any, name: str, pos: Vec3, volume: float = 1.0, pitch: float = 1.0) -> None:
        for p in self.viewers(dimension, pos, 32.0):
            try:
                p.play_sound(p.location, name, volume, pitch)
            except Exception:  # noqa: BLE001
                return

    def block_id(self, dimension: Any, x: int, y: int, z: int) -> str:
        try:
            return dimension.get_block_at(x, y, z).type
        except Exception:  # noqa: BLE001
            return "minecraft:air"

    def is_passable(self, dimension: Any, x: int, y: int, z: int) -> bool:
        return self.block_id(dimension, x, y, z) in PASSABLE_BLOCKS

    def destroy_block(self, dimension: Any, x: int, y: int, z: int) -> bool:
        """Breaks a block the way a player would (drops included) via /setblock ... destroy."""
        prefix = dimension_command_prefix(dimension)
        return self.plugin.runner.run(f"{prefix}setblock {x} {y} {z} air destroy")

    def spawn_tnt(self, dimension: Any, pos: Vec3, fuse: int, owner: Any, break_blocks: bool,
                  size: float = 4.0) -> None:
        """Emulates PiggyTNT: a primed-TNT visual that is swapped for our own explosion when the fuse ends."""
        from .explosion import explode
        from .util import ActorRef, make_location

        visual = None
        if fuse > 0:
            try:
                visual = ActorRef(dimension.spawn_actor(make_location(dimension, pos), "minecraft:tnt"))
            except Exception as exc:  # noqa: BLE001
                self.plugin.debug(f"tnt visual failed: {exc}")
        owner_ref = ActorRef(owner) if owner is not None else None

        def detonate() -> None:
            if visual is not None:
                actor = self.plugin.resolve(visual)
                if actor is not None:
                    try:
                        actor.remove()
                    except Exception:  # noqa: BLE001
                        pass
            who = self.plugin.resolve(owner_ref) if owner_ref is not None else None
            explode(self.plugin, dimension, pos + Vec3(0, 0.49, 0), size, who, True, break_blocks)

        if fuse <= 0:
            detonate()
        else:
            self.plugin.later(detonate, max(1, fuse - 1))

    def set_block(self, dimension: Any, x: int, y: int, z: int, block_type: str) -> None:
        try:
            dimension.get_block_at(x, y, z).set_type(block_type)
        except Exception as exc:  # noqa: BLE001
            self.plugin.debug(f"set_block failed: {exc}")
