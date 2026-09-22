"""Projectile support.

* Arrows fired from enchanted bows are detected through ActorSpawnEvent (owner = nearest player holding a bow)
  and tracked so damage / block-hit reactions use the item the arrow was fired with.
* Custom projectiles (Blaze, Wither Skull, Porkified, Volley, Bombardment ...) are *simulated*: a vanilla
  entity is spawned as the visual and moved with teleports while collisions are resolved here.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from endstone.inventory import ItemStack

from .constants import PASSABLE_BLOCKS
from .events import ProjectileHitBlockEv, ShootEv
from .items import held_item, is_bow
from .storage import read_enchants
from .util import (ActorRef, Vec3, actor_alive, entity_height, is_living, is_player, make_location, pos_of,
                   same_actor, teleport_to, yaw_pitch_for)

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants


@dataclass
class TrackedProjectile:
    id: int
    owner: ActorRef | None
    owner_name: str
    item: ItemStack | None
    enchants: dict[str, int]
    kind: str  # "arrow" | "sim"
    born_tick: int
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimProjectile:
    tracked: TrackedProjectile
    visual: ActorRef | None
    dimension: Any
    pos: Vec3
    vel: Vec3
    gravity: float
    drag: float
    damage: float
    owner: ActorRef | None
    on_entity: Callable[["SimProjectile", Any], None] | None
    on_block: Callable[["SimProjectile", Vec3], None] | None
    life: int = 200
    age: int = 0
    hit_radius: float = 0.85
    on_tick: Callable[["SimProjectile"], None] | None = None
    fall_through: bool = False


class ProjectileManager:
    def __init__(self, plugin: "PiggyCustomEnchants") -> None:
        self.plugin = plugin
        self.tracked: dict[int, TrackedProjectile] = {}
        self.sims: list[SimProjectile] = []
        self.homing: dict[int, int] = {}  # arrow id -> enchant level

    # tracking
    def track(self, actor_id: int, owner: Any, item: ItemStack | None, kind: str = "arrow") -> TrackedProjectile:
        tp = TrackedProjectile(
            id=actor_id,
            owner=ActorRef(owner) if owner is not None else None,
            owner_name=getattr(owner, "name", ""),
            item=item,
            enchants=read_enchants(item),
            kind=kind,
            born_tick=self.plugin.tick_count,
        )
        self.tracked[actor_id] = tp
        return tp

    def get(self, actor_id: int) -> TrackedProjectile | None:
        return self.tracked.get(actor_id)

    def remove(self, actor_id: int, despawn: bool = False) -> None:
        self.tracked.pop(actor_id, None)
        self.homing.pop(actor_id, None)
        if despawn:
            actor = self.plugin.find_actor(actor_id)
            if actor is not None:
                try:
                    actor.remove()
                except Exception:  # noqa: BLE001
                    pass

    def owner_of(self, tp: TrackedProjectile) -> Any | None:
        return self.plugin.resolve(tp.owner) if tp.owner is not None else None

    # arrow detection
    def on_actor_spawn(self, actor: Any) -> None:
        if getattr(actor, "type", "") != "minecraft:arrow":
            return
        actor_id = actor.id
        self.plugin.later(lambda: self._resolve_arrow(actor_id), 1)

    def _resolve_arrow(self, actor_id: int) -> None:
        arrow = self.plugin.find_actor(actor_id)
        if arrow is None or actor_id in self.tracked:
            return
        apos = pos_of(arrow)
        vel = Vec3(float(arrow.velocity.x), float(arrow.velocity.y), float(arrow.velocity.z))
        best, best_d = None, 4.5
        for player in self.plugin.server.online_players:
            try:
                if player.dimension.name != arrow.dimension.name:
                    continue
                item = held_item(player)
                if not is_bow(item) or not read_enchants(item):
                    continue
                d = pos_of(player).distance(apos)
                if d < best_d:
                    best, best_d = player, d
            except Exception:  # noqa: BLE001
                continue
        if best is None:
            return
        item = held_item(best)
        tp = self.track(actor_id, best, item, "arrow")
        ev = ShootEv(best, actor_id, apos, vel, item)
        try:
            self.plugin.engine.attempt(best, ev)
        except Exception as exc:  # noqa: BLE001
            self.plugin.debug(f"shoot reaction failed: {exc}")
        if ev.replaced:
            self.remove(actor_id, despawn=True)
        elif not tp.enchants:
            self.remove(actor_id)

    # per-tick
    def tick(self) -> None:
        if not self.tracked and not self.sims and not self.homing:
            return
        self._tick_arrows()
        self._tick_sims()

    def _tick_arrows(self) -> None:
        tick = self.plugin.tick_count
        for actor_id, tp in list(self.tracked.items()):
            if tp.kind != "arrow":
                continue
            age = tick - tp.born_tick
            if age > 1200:
                self.remove(actor_id)
                continue
            if age < 2:
                continue
            arrow = self.plugin.find_actor(actor_id)
            if arrow is None or not actor_alive(arrow):
                self.remove(actor_id)
                continue
            level = self.homing.get(actor_id)
            if level is not None:
                self._steer(arrow, tp, level)
            v = arrow.velocity
            speed = math.sqrt(float(v.x) ** 2 + float(v.y) ** 2 + float(v.z) ** 2)
            if arrow.is_on_ground or (age > 3 and speed < 0.03 and level is None):
                ev = ProjectileHitBlockEv(tp, pos_of(arrow), arrow.dimension)
                owner = self.owner_of(tp)
                if owner is not None:
                    try:
                        self.plugin.engine.attempt(owner, ev)
                    except Exception as exc:  # noqa: BLE001
                        self.plugin.debug(f"projectile hit reaction failed: {exc}")
                self.remove(actor_id, despawn=ev.remove_projectile)

    def _steer(self, arrow: Any, tp: TrackedProjectile, level: int) -> None:
        owner = self.owner_of(tp)
        origin = pos_of(arrow)
        target = self.nearest_target(origin, arrow.dimension, level * 10, owner, exclude_id=arrow.id)
        if target is None:
            return
        center = pos_of(target) + Vec3(0, entity_height(target) / 2, 0)
        direction = (center - origin).normalized()
        yaw, pitch = yaw_pitch_for(direction)
        teleport_to(arrow, origin + direction * min(1.5, origin.distance(center)), yaw, pitch)

    def nearest_target(self, origin: Vec3, dimension: Any, radius: float, owner: Any, exclude_id: int = -1) -> Any | None:
        best, best_d = None, radius
        for actor in self.plugin.actors_in(dimension):
            try:
                if actor.id == exclude_id or not is_living(actor) or same_actor(actor, owner) or not actor_alive(actor):
                    continue
                if owner is not None and is_player(owner) and self.plugin.allies.is_ally(owner, actor):
                    continue
                d = pos_of(actor).distance(origin)
                if d <= radius and d < best_d:
                    best, best_d = actor, d
            except Exception:  # noqa: BLE001
                continue
        return best

    # simulated projectiles
    def spawn_sim(
        self,
        owner: Any,
        item: ItemStack | None,
        entity_type: str | None,
        pos: Vec3,
        vel: Vec3,
        dimension: Any,
        gravity: float = 0.05,
        drag: float = 0.01,
        damage: float = 1.0,
        on_entity: Callable[[SimProjectile, Any], None] | None = None,
        on_block: Callable[[SimProjectile, Vec3], None] | None = None,
        life: int = 200,
        hit_radius: float = 0.85,
        on_tick: Callable[[SimProjectile], None] | None = None,
        tracked_from: TrackedProjectile | None = None,
    ) -> SimProjectile | None:
        visual = None
        actor_id = -(len(self.sims) + 1) - self.plugin.tick_count * 1000
        if entity_type:
            try:
                yaw, pitch = yaw_pitch_for(vel.normalized())
                actor = dimension.spawn_actor(make_location(dimension, pos, pitch, yaw), entity_type)
                visual = ActorRef(actor)
                actor_id = actor.id
            except Exception as exc:  # noqa: BLE001
                self.plugin.debug(f"could not spawn visual {entity_type}: {exc}")
        if tracked_from is not None:
            tp = TrackedProjectile(actor_id, tracked_from.owner, tracked_from.owner_name, tracked_from.item,
                                   dict(tracked_from.enchants), "sim", self.plugin.tick_count)
        else:
            tp = TrackedProjectile(actor_id, ActorRef(owner) if owner is not None else None,
                                   getattr(owner, "name", ""), item, read_enchants(item), "sim",
                                   self.plugin.tick_count)
        self.tracked[actor_id] = tp
        sim = SimProjectile(tp, visual, dimension, pos, vel, gravity, drag, damage,
                            tp.owner, on_entity, on_block, life, hit_radius=hit_radius, on_tick=on_tick)
        self.sims.append(sim)
        return sim

    def _finish(self, sim: SimProjectile) -> None:
        if sim in self.sims:
            self.sims.remove(sim)
        self.tracked.pop(sim.tracked.id, None)
        if sim.visual is not None:
            actor = self.plugin.resolve(sim.visual)
            if actor is not None:
                try:
                    actor.remove()
                except Exception:  # noqa: BLE001
                    pass

    def _tick_sims(self) -> None:
        for sim in list(self.sims):
            try:
                if self._step_sim(sim):
                    self._finish(sim)
            except Exception as exc:  # noqa: BLE001
                self.plugin.debug(f"sim step failed: {exc}")
                self._finish(sim)

    def _step_sim(self, sim: SimProjectile) -> bool:
        sim.age += 1
        if sim.age > sim.life:
            return True
        owner = self.plugin.resolve(sim.owner) if sim.owner is not None else None
        speed = sim.vel.length()
        steps = max(1, math.ceil(speed / 0.5))
        step = sim.vel * (1.0 / steps)
        actors = [a for a in self.plugin.actors_in(sim.dimension) if is_living(a) and actor_alive(a)]
        for _ in range(steps):
            sim.pos = sim.pos + step
            x, y, z = sim.pos.floor()
            block_id = self.plugin.world.block_id(sim.dimension, x, y, z)
            if block_id not in PASSABLE_BLOCKS and not sim.fall_through:
                if sim.on_block:
                    sim.on_block(sim, sim.pos)
                return True
            if not sim.fall_through:
                for actor in actors:
                    if same_actor(actor, owner) and sim.age < 6:
                        continue
                    if same_actor(actor, owner):
                        continue
                    center = pos_of(actor) + Vec3(0, entity_height(actor) / 2, 0)
                    if center.distance(sim.pos) <= sim.hit_radius + entity_height(actor) * 0.25:
                        if sim.on_entity:
                            sim.on_entity(sim, actor)
                        return True
        if sim.on_tick:
            sim.on_tick(sim)
        sim.vel = Vec3(sim.vel.x * (1 - sim.drag), (sim.vel.y - sim.gravity) * (1 - sim.drag), sim.vel.z * (1 - sim.drag))
        if sim.visual is not None:
            visual = self.plugin.resolve(sim.visual)
            if visual is None:
                return True
            yaw, pitch = yaw_pitch_for(sim.vel.normalized())
            teleport_to(visual, sim.pos, yaw, pitch)
        return False

    def default_entity_hit(self, sim: SimProjectile, victim: Any) -> None:
        """Damage = ceil(speed * base damage), routed through /damage as a child-entity hit."""
        owner = self.plugin.resolve(sim.owner) if sim.owner is not None else None
        if owner is not None and is_player(owner) and self.plugin.allies.is_ally(owner, victim):
            return
        amount = math.ceil(sim.vel.length() * sim.damage)
        if amount > 0:
            self.plugin.combat.damage(victim, amount, "projectile", attacker=owner, child=sim.tracked)

    def clear(self) -> None:
        for sim in list(self.sims):
            self._finish(sim)
        self.tracked.clear()
        self.homing.clear()


def random_spread(vel: Vec3, amount: float) -> Vec3:
    return Vec3(vel.x + random.uniform(-amount, amount), vel.y + random.uniform(-amount, amount),
                vel.z + random.uniform(-amount, amount))
