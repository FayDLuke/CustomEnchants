from __future__ import annotations

import math
from typing import Any

from ..constants import CROP_BLOCKS, ORE_DROPS, ORE_TIERS, SMELTING_RESULTS, Kind, Trigger, Usage
from ..drops import DropContext
from ..events import BreakEv, InteractEv
from ..items import Slot, item_id
from .base import RecursiveEnchant
from ..enchant import CustomEnchant

ORE_INDEX: dict[str, int] = {}
for _tier, _ids in enumerate(ORE_TIERS):
    for _id in _ids:
        ORE_INDEX[_id] = _tier
DROP_INDEX = {drop: i for i, drop in enumerate(ORE_DROPS)}


def _is_log(block_id: str) -> bool:
    return block_id.startswith("minecraft:") and block_id.endswith("_log") and "stripped" not in block_id


class ToolEnchant(CustomEnchant):
    item_kind = Kind.TOOLS
    reactive = True
    reagents = (Trigger.BLOCK_BREAK,)


class DrillerEnchant(RecursiveEnchant):
    name = "Driller"
    rarity = "uncommon"
    item_kind = Kind.TOOLS
    reagents = (Trigger.BLOCK_BREAK,)

    def default_extra(self) -> dict[str, Any]:
        return {"distanceMultiplier": 1}

    def safe_react(self, player, item, slot, event, level, stack):
        if not isinstance(event, BreakEv):
            return
        normal = self.plugin.break_normal(player)
        depth = (-normal[0], -normal[1], -normal[2])
        if normal[1] != 0:
            axes = ((1, 0, 0), (0, 0, 1))
        elif normal[0] != 0:
            axes = ((0, 1, 0), (0, 0, 1))
        else:
            axes = ((1, 0, 0), (0, 1, 0))
        ox, oy, oz = event.pos
        positions = []
        for i in range(0, int(level * self.extra["distanceMultiplier"]) + 1):
            cx, cy, cz = ox + depth[0] * i, oy + depth[1] * i, oz + depth[2] * i
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    pos = (cx + axes[0][0] * da + axes[1][0] * db,
                           cy + axes[0][1] * da + axes[1][1] * db,
                           cz + axes[0][2] * da + axes[1][2] * db)
                    if pos != (ox, oy, oz):
                        positions.append(pos)
        self.plugin.break_blocks(player, event.dimension, positions, item)


class EnergizingEnchant(ToolEnchant):
    name = "Energizing"

    def default_extra(self) -> dict[str, Any]:
        return {"duration": 20, "baseAmplifier": -1, "amplifierMultiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, BreakEv) and not self.plugin.effects.has(player, "haste"):
            e = self.extra
            self.plugin.effects.add(player, "haste", e["duration"], level * e["amplifierMultiplier"] + e["baseAmplifier"], False)


class ExplosiveEnchant(RecursiveEnchant):
    name = "Explosive"
    rarity = "uncommon"
    item_kind = Kind.TOOLS
    reagents = (Trigger.BLOCK_BREAK,)
    priority = 4

    def default_extra(self) -> dict[str, Any]:
        return {"sizeMultiplier": 5, "entityDamage": True}

    def safe_react(self, player, item, slot, event, level, stack):
        if not isinstance(event, BreakEv):
            return
        from ..explosion import affected_blocks
        from ..util import Vec3
        from ..constants import UNBREAKABLE_BLOCKS

        size = min(level * self.extra["sizeMultiplier"], float(self.plugin.cfg("explosion-max-size", 12)))
        center = Vec3(event.pos[0] + 0.5, event.pos[1] + 0.5, event.pos[2] + 0.5)
        blocks = affected_blocks(self.plugin, event.dimension, center, size)
        positions = [p for p, b in blocks.items() if b not in UNBREAKABLE_BLOCKS and p != tuple(event.pos)]
        limit = int(self.plugin.cfg("explosion-max-blocks", 2500))
        positions.sort(key=lambda p: (p[0] + .5 - center.x) ** 2 + (p[1] + .5 - center.y) ** 2 + (p[2] + .5 - center.z) ** 2)
        self.plugin.break_blocks(player, event.dimension, positions[:limit], item, region_radius=size + 1, center=center,
                                 drop_chance=1.0 / max(size, 1.0))
        if self.extra["entityDamage"]:
            self.plugin.explosion_effects(event.dimension, center, size, player)


class QuickeningEnchant(ToolEnchant):
    name = "Quickening"
    rarity = "uncommon"

    def default_extra(self) -> dict[str, Any]:
        return {"duration": 40, "baseAmplifier": 1, "amplifierMultiplier": 1}

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, BreakEv) and not self.plugin.effects.has(player, "speed"):
            e = self.extra
            self.plugin.effects.add(player, "speed", e["duration"], level * e["amplifierMultiplier"] + e["baseAmplifier"], False)


class SmeltingEnchant(ToolEnchant):
    name = "Smelting"
    rarity = "uncommon"
    max_level = 1
    priority = 2

    def make_op(self, player: Any, level: int):
        def op(ctx: DropContext) -> None:
            for actor in list(ctx.items):
                stack = ctx.stack_of(actor)
                if stack is None:
                    continue
                result = SMELTING_RESULTS.get(item_id(stack))
                if result:
                    ctx.replace(actor, result, stack.amount)

        return op

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, BreakEv):
            event.add_drop_op(self.priority, self.make_op(player, level))


class TelepathyEnchant(ToolEnchant):
    name = "Telepathy"
    max_level = 1

    def make_op(self, player: Any, level: int):
        def op(ctx: DropContext) -> None:
            for actor in list(ctx.items):
                stack = ctx.stack_of(actor)
                if stack is None:
                    continue
                try:
                    leftover = player.inventory.add_item(stack)
                except Exception as exc:  # noqa: BLE001
                    self.plugin.debug(f"telepathy add_item failed: {exc}")
                    continue
                if not leftover:
                    ctx.remove(actor)
                else:
                    rest = next(iter(leftover.values()))
                    try:
                        actor.item_stack = rest
                    except Exception:  # noqa: BLE001
                        pass

        return op

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, BreakEv):
            event.add_drop_op(self.priority, self.make_op(player, level))


class JackpotEnchant(ToolEnchant):
    name = "Jackpot"
    rarity = "mythic"
    item_kind = Kind.PICKAXE
    priority = 3

    def make_op(self, player: Any, level: int):
        def op(ctx: DropContext) -> None:
            tiers = {ORE_INDEX[b] for b in ctx.block_ids if b in ORE_INDEX and ORE_INDEX[b] + 1 < len(ORE_DROPS)}
            if not tiers:
                return
            for actor in list(ctx.items):
                stack = ctx.stack_of(actor)
                tier = DROP_INDEX.get(item_id(stack)) if stack is not None else None
                if tier is not None and tier in tiers:
                    ctx.replace(actor, ORE_DROPS[tier + 1], 1)

        return op

    def react(self, player, item, slot, event, level, stack):
        if isinstance(event, BreakEv) and event.block_id in ORE_INDEX:
            event.add_drop_op(self.priority, self.make_op(player, level))


class LumberjackEnchant(RecursiveEnchant):
    name = "Lumberjack"
    max_level = 1
    item_kind = Kind.AXE
    reagents = (Trigger.BLOCK_BREAK,)

    def default_extra(self) -> dict[str, Any]:
        return {"limit": 800}

    def safe_react(self, player, item, slot, event, level, stack):
        if not isinstance(event, BreakEv) or not player.is_sneaking or not _is_log(event.block_id):
            return
        limit = int(self.extra["limit"])
        seen = {tuple(event.pos)}
        queue = [tuple(event.pos)]
        found: list[tuple[int, int, int]] = []
        dim = event.dimension
        while queue and len(found) < limit:
            x, y, z = queue.pop()
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                nxt = (x + dx, y + dy, z + dz)
                if nxt in seen:
                    continue
                seen.add(nxt)
                if _is_log(self.plugin.world.block_id(dim, *nxt)):
                    found.append(nxt)
                    queue.append(nxt)
        self.plugin.break_blocks(player, dim, found, item)


class FarmerEnchant(ToolEnchant):
    name = "Farmer"
    rarity = "uncommon"
    max_level = 1
    item_kind = Kind.HOE

    def react(self, player, item, slot, event, level, stack):
        if not isinstance(event, BreakEv) or event.block_id not in CROP_BLOCKS:
            return
        seed = CROP_BLOCKS[event.block_id]
        from endstone.inventory import ItemStack

        if not player.inventory.contains(ItemStack(seed, 1)):
            return
        x, y, z = event.pos
        crop_id, dim = event.block_id, event.dimension

        def replant() -> None:
            below = self.plugin.world.block_id(dim, x, y - 1, z)
            if self.plugin.world.block_id(dim, x, y, z) != "minecraft:air" or below != "minecraft:farmland":
                return
            try:
                if player.inventory.contains(ItemStack(seed, 1)):
                    self.plugin.world.set_block(dim, x, y, z, crop_id)
                    player.inventory.remove_item(ItemStack(seed, 1))
            except Exception as exc:  # noqa: BLE001
                self.plugin.debug(f"farmer replant failed: {exc}")

        self.plugin.later(replant, 1)


class FertilizerEnchant(RecursiveEnchant):
    name = "Fertilizer"
    rarity = "uncommon"
    max_level = 3
    item_kind = Kind.HOE
    reagents = (Trigger.INTERACT,)

    TILLABLE = ("minecraft:grass_block", "minecraft:dirt")

    def default_extra(self) -> dict[str, Any]:
        return {"radiusMultiplier": 1}

    def safe_react(self, player, item, slot, event, level, stack):
        if not isinstance(event, InteractEv) or event.block is None:
            return
        if getattr(event.action, "name", "") != "RIGHT_CLICK_BLOCK":
            return
        block = event.block
        if block.type not in self.TILLABLE:
            return
        radius = int(level * self.extra["radiusMultiplier"])
        dim = block.dimension
        for x in range(-radius, radius + 1):
            for z in range(-radius, radius + 1):
                bx, by, bz = block.x + x, block.y, block.z + z
                if self.plugin.world.block_id(dim, bx, by, bz) in self.TILLABLE and \
                        self.plugin.world.block_id(dim, bx, by + 1, bz) == "minecraft:air":
                    self.plugin.world.set_block(dim, bx, by, bz, "minecraft:farmland")


class HarvestEnchant(RecursiveEnchant):
    name = "Harvest"
    rarity = "uncommon"
    max_level = 3
    item_kind = Kind.HOE
    reagents = (Trigger.BLOCK_BREAK,)

    def default_extra(self) -> dict[str, Any]:
        return {"radiusMultiplier": 1}

    def safe_react(self, player, item, slot, event, level, stack):
        if not isinstance(event, BreakEv) or event.block_id not in CROP_BLOCKS:
            return
        radius = int(level * self.extra["radiusMultiplier"])
        ox, oy, oz = event.pos
        positions = []
        for x in range(-radius, radius + 1):
            for z in range(-radius, radius + 1):
                pos = (ox + x, oy, oz + z)
                if pos != (ox, oy, oz) and self.plugin.world.block_id(event.dimension, *pos) in CROP_BLOCKS:
                    positions.append(pos)
        self.plugin.break_blocks(player, event.dimension, positions, item)
