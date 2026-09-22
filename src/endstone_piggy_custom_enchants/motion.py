"""Teleport-based motion emulation. Endstone has no velocity setter, so knock-ups, pulls and pushes are
integrated here and applied with Actor.teleport each tick."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from .util import ActorRef, Vec3, actor_alive, pos_of, teleport_to

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants


@dataclass
class _Motion:
    ref: ActorRef
    kind: str  # "launch" | "pull"
    ticks_left: int
    velocity: Vec3 = field(default_factory=Vec3)
    gravity: float = 0.08
    drag: float = 0.02
    target: Callable[[], Vec3 | None] | None = None
    speed: float = 1.0
    stop_distance: float = 1.5
    on_end: Callable[[], None] | None = None
    height: float = 1.8
    grounded_ticks: int = 0


class MotionManager:
    def __init__(self, plugin: "PiggyCustomEnchants") -> None:
        self.plugin = plugin
        self.active: list[_Motion] = []

    def launch(self, actor: Any, velocity: Vec3, gravity: float = 0.08, drag: float = 0.02,
               max_ticks: int = 40, on_end: Callable[[], None] | None = None) -> None:
        self.active.append(_Motion(ActorRef(actor), "launch", max_ticks, velocity, gravity, drag, on_end=on_end))

    def pull(self, actor: Any, target: Callable[[], Vec3 | None], speed: float = 1.0, max_ticks: int = 40,
             stop_distance: float = 1.5, on_end: Callable[[], None] | None = None) -> None:
        self.active.append(
            _Motion(ActorRef(actor), "pull", max_ticks, target=target, speed=speed,
                    stop_distance=stop_distance, on_end=on_end)
        )

    def clear(self) -> None:
        self.active.clear()

    def tick(self) -> None:
        if not self.active:
            return
        for motion in list(self.active):
            done = False
            try:
                actor = self.plugin.resolve(motion.ref)
                if actor is None or not actor_alive(actor) and not motion.ref.player:
                    done = True
                else:
                    done = self._step(motion, actor)
            except Exception as exc:  # noqa: BLE001
                self.plugin.debug(f"motion step failed: {exc}")
                done = True
            motion.ticks_left -= 1
            if done or motion.ticks_left <= 0:
                self.active.remove(motion)
                if motion.on_end is not None:
                    try:
                        motion.on_end()
                    except Exception as exc:  # noqa: BLE001
                        self.plugin.debug(f"motion on_end failed: {exc}")

    def _clear_at(self, actor: Any, pos: Vec3, height: float) -> bool:
        x, y, z = pos.floor()
        dim = actor.dimension
        return self.plugin.world.is_passable(dim, x, y, z) and self.plugin.world.is_passable(
            dim, x, math.floor(pos.y + height - 0.1), z
        )

    def _step(self, m: _Motion, actor: Any) -> bool:
        pos = pos_of(actor)
        if m.kind == "launch":
            nxt = pos + m.velocity
            if not self._clear_at(actor, nxt, m.height):
                if m.velocity.y < 0:
                    # landed: stand on top of the block that stopped us
                    teleport_to(actor, Vec3(pos.x, math.floor(nxt.y) + 1.0, pos.z))
                return True
            teleport_to(actor, nxt)
            m.velocity = Vec3(m.velocity.x * (1 - m.drag), (m.velocity.y - m.gravity) * (1 - m.drag),
                              m.velocity.z * (1 - m.drag))
            return False
        target = m.target() if m.target else None
        if target is None:
            return True
        delta = target - pos
        dist = delta.length()
        if dist <= m.stop_distance:
            return True
        step = delta.normalized() * min(m.speed, dist)
        nxt = pos + step
        if not self._clear_at(actor, nxt, m.height):
            nxt = pos + Vec3(step.x, 0.0, step.z) if self._clear_at(actor, pos + Vec3(step.x, 0.0, step.z), m.height) \
                else pos + Vec3(0.0, abs(step.y) + 0.2, 0.0)
            if not self._clear_at(actor, nxt, m.height):
                return True
        teleport_to(actor, nxt)
        return False
