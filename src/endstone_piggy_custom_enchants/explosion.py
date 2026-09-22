"""Port of PiggyExplosion (explodeA ray casting + explodeB damage/drops)."""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Any

from .constants import BLAST_RESISTANCE, UNBREAKABLE_BLOCKS
from .util import Vec3, is_living, pos_of, same_actor

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants

RAYS = 16
STEP = 0.3
_DIRECTIONS: list[tuple[float, float, float]] | None = None


def _directions() -> list[tuple[float, float, float]]:
    global _DIRECTIONS
    if _DIRECTIONS is None:
        out = []
        m = RAYS - 1
        for i in range(RAYS):
            for j in range(RAYS):
                for k in range(RAYS):
                    if i in (0, m) or j in (0, m) or k in (0, m):
                        x, y, z = i / m * 2 - 1, j / m * 2 - 1, k / m * 2 - 1
                        ln = math.sqrt(x * x + y * y + z * z)
                        out.append((x / ln * STEP, y / ln * STEP, z / ln * STEP))
        _DIRECTIONS = out
    return _DIRECTIONS


def affected_blocks(plugin: "PiggyCustomEnchants", dimension: Any, center: Vec3, size: float) -> dict[tuple[int, int, int], str]:
    cache: dict[tuple[int, int, int], tuple[str, float]] = {}
    affected: dict[tuple[int, int, int], str] = {}
    default_resistance = float(plugin.cfg("explosion-default-resistance", 3.0))

    def lookup(pos: tuple[int, int, int]) -> tuple[str, float]:
        hit = cache.get(pos)
        if hit is None:
            block_id = plugin.world.block_id(dimension, *pos)
            if block_id in ("minecraft:air", "minecraft:cave_air", "minecraft:void_air"):
                hit = (block_id, -1.0)
            else:
                hit = (block_id, BLAST_RESISTANCE.get(block_id, default_resistance))
            cache[pos] = hit
        return hit

    for dx, dy, dz in _directions():
        px, py, pz = center.x, center.y, center.z
        force = size * (random.randint(700, 1300) / 1000)
        while force > 0:
            pos = (math.floor(px), math.floor(py), math.floor(pz))
            block_id, resistance = lookup(pos)
            if resistance >= 0:
                force -= (resistance / 5 + 0.3) * STEP
                if force > 0 and pos not in affected:
                    affected[pos] = block_id
            px += dx
            py += dy
            pz += dz
            force -= STEP * 0.75
    return affected


def explode(
    plugin: "PiggyCustomEnchants",
    dimension: Any,
    center: Vec3,
    size: float,
    owner: Any = None,
    entity_damage: bool = True,
    break_blocks: bool = True,
) -> None:
    size = min(float(size), float(plugin.cfg("explosion-max-size", 12)))
    if size <= 0:
        return

    if break_blocks:
        blocks = affected_blocks(plugin, dimension, center, size)
        limit = int(plugin.cfg("explosion-max-blocks", 2500))
        items = [(p, b) for p, b in blocks.items() if b not in UNBREAKABLE_BLOCKS]
        if len(items) > limit:
            items.sort(key=lambda pb: (pb[0][0] + .5 - center.x) ** 2 + (pb[0][1] + .5 - center.y) ** 2
                       + (pb[0][2] + .5 - center.z) ** 2)
            items = items[:limit]
        yield_chance = 1.0 / size
        for (x, y, z), _block in items:
            if random.random() < yield_chance:
                plugin.world.destroy_block(dimension, x, y, z)
            else:
                plugin.world.set_block(dimension, x, y, z, "minecraft:air")

    if entity_damage:
        explosion_effects(plugin, dimension, center, size, owner)
    else:
        _fx(plugin, dimension, center)


def _fx(plugin: "PiggyCustomEnchants", dimension: Any, center: Vec3) -> None:
    plugin.world.particle(dimension, "minecraft:huge_explosion_emitter", center, 64)
    plugin.world.sound(dimension, "random.explode", center, 4.0, 1.0)


def explosion_effects(plugin: "PiggyCustomEnchants", dimension: Any, center: Vec3, size: float, owner: Any) -> None:
    """explodeB without the block part: damage nearby living entities, then particle + sound."""
    explosion_size = size * 2
    for actor in dimension.actors:
        try:
            if not is_living(actor) or same_actor(actor, owner):
                continue
            distance = pos_of(actor).distance(center) / explosion_size
            if distance > 1:
                continue
            impact = 1 - distance
            damage = int(((impact * impact + impact) / 2) * 8 * explosion_size + 1)
            plugin.combat.damage(actor, damage, "entity_explosion", attacker=owner)
        except Exception as exc:  # noqa: BLE001
            plugin.debug(f"explosion damage failed: {exc}")
    _fx(plugin, dimension, center)
