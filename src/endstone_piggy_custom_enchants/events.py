from __future__ import annotations

from typing import Any, Callable

from .constants import Trigger
from .util import Vec3


class GameEvent:
    """Base for the internal events enchants react to. `kinds` holds every Trigger the event satisfies."""

    kinds: frozenset[Trigger] = frozenset()

    def matches(self, reagents: tuple[Trigger, ...]) -> bool:
        return any(r in self.kinds for r in reagents)


class DamageEv(GameEvent):
    def __init__(self, raw: Any, entity: Any, damager: Any, child: Any, cause: str, tracked: Any = None,
                 child_pos: Vec3 | None = None) -> None:
        self.raw = raw
        self.child_pos = child_pos
        self.entity = entity
        self.damager = damager
        self.child = child
        self.cause = cause
        self.tracked = tracked
        kinds = {Trigger.DAMAGE}
        if damager is not None:
            kinds.add(Trigger.DAMAGE_BY_ENTITY)
            if child is not None:
                kinds.add(Trigger.DAMAGE_BY_CHILD)
        self.kinds = frozenset(kinds)

    @property
    def damage(self) -> float:
        return float(self.raw.damage)

    @damage.setter
    def damage(self, value: float) -> None:
        self.raw.damage = max(0.0, float(value))

    @property
    def by_entity(self) -> bool:
        return Trigger.DAMAGE_BY_ENTITY in self.kinds

    @property
    def by_child(self) -> bool:
        return Trigger.DAMAGE_BY_CHILD in self.kinds

    def cancel(self) -> None:
        self.raw.cancel()


class KnockbackEv(GameEvent):
    kinds = frozenset({Trigger.KNOCKBACK})

    def __init__(self, raw: Any) -> None:
        self.raw = raw
        self.entity = raw.actor
        self.source = raw.source

    def scale(self, factor: float) -> None:
        from endstone.util import Vector

        kb = self.raw.knockback
        self.raw.knockback = Vector(kb.x * factor, kb.y * factor, kb.z * factor)

    def cancel(self) -> None:
        self.raw.cancel()


class BreakEv(GameEvent):
    kinds = frozenset({Trigger.BLOCK_BREAK})

    def __init__(self, raw: Any, player: Any, block: Any, tool: Any) -> None:
        self.raw = raw
        self.player = player
        self.block = block
        self.block_id: str = block.type
        self.pos = (block.x, block.y, block.z)
        self.dimension = block.dimension
        self.tool = tool
        # (priority, fn(DropContext)) - executed once the drops exist in the world.
        self.drop_ops: list[tuple[int, Callable[[Any], None]]] = []

    def add_drop_op(self, priority: int, fn: Callable[[Any], None]) -> None:
        self.drop_ops.append((priority, fn))

    def cancel(self) -> None:
        self.raw.cancel()


class InteractEv(GameEvent):
    kinds = frozenset({Trigger.INTERACT})

    def __init__(self, raw: Any) -> None:
        self.raw = raw
        self.action = raw.action
        self.block = raw.block if raw.has_block else None

    def cancel(self) -> None:
        self.raw.cancel()


class MoveEv(GameEvent):
    kinds = frozenset({Trigger.MOVE})

    def __init__(self, from_pos: Vec3, to_pos: Vec3) -> None:
        self.from_pos = from_pos
        self.to_pos = to_pos


class SneakEv(GameEvent):
    kinds = frozenset({Trigger.SNEAK})

    def __init__(self, sneaking: bool) -> None:
        self.is_sneaking = sneaking


class DeathEv(GameEvent):
    kinds = frozenset({Trigger.DEATH})

    def __init__(self, raw: Any, player: Any) -> None:
        self.raw = raw
        self.player = player
        # (slot key, item) pairs to hand back on respawn instead of dropping.
        self.kept: list[tuple[Any, Any]] = []


class ShootEv(GameEvent):
    kinds = frozenset({Trigger.SHOOT_BOW})

    def __init__(self, player: Any, arrow_id: int, position: Vec3, velocity: Vec3, item: Any) -> None:
        self.player = player
        self.arrow_id = arrow_id
        self.position = position
        self.velocity = velocity
        self.item = item
        self.replaced = False


class ProjectileHitBlockEv(GameEvent):
    kinds = frozenset({Trigger.PROJECTILE_HIT_BLOCK})

    def __init__(self, tracked: Any, position: Vec3, dimension: Any) -> None:
        self.tracked = tracked
        self.position = position
        self.dimension = dimension
        self.remove_projectile = False
