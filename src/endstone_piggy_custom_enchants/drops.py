"""BlockBreakEvent exposes no drop list. Instead the item entities that appear around the broken block are
picked up one/two ticks later and handed to the enchants' drop operations (Jackpot -> Smelting -> Telepathy)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from endstone.inventory import ItemStack

from .util import Vec3, actor_alive, is_item_entity, nearby_actors

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants

DropOp = Callable[["DropContext"], None]


class DropContext:
    def __init__(self, plugin: "PiggyCustomEnchants", player: Any, dimension: Any, items: list[Any],
                 block_ids: set[str], pos: tuple[int, int, int]) -> None:
        self.plugin = plugin
        self.player = player
        self.dimension = dimension
        self.items = items
        self.block_ids = block_ids
        self.pos = pos

    def remove(self, actor: Any) -> None:
        try:
            actor.remove()
        except Exception:  # noqa: BLE001
            pass
        if actor in self.items:
            self.items.remove(actor)

    def stack_of(self, actor: Any) -> ItemStack | None:
        try:
            return actor.item_stack
        except Exception:  # noqa: BLE001
            return None

    def replace(self, actor: Any, item_type: str, amount: int) -> None:
        try:
            actor.item_stack = ItemStack(item_type, max(1, amount))
        except Exception as exc:  # noqa: BLE001
            self.plugin.debug(f"replace drop failed: {exc}")


def schedule_drop_ops(
    plugin: "PiggyCustomEnchants",
    player: Any,
    dimension: Any,
    center: Vec3,
    radius: float,
    ops: list[tuple[int, DropOp]],
    block_ids: set[str] | None = None,
    pos: tuple[int, int, int] = (0, 0, 0),
) -> None:
    if not ops:
        return
    ordered = [fn for _p, fn in sorted(ops, key=lambda t: -t[0])]
    before = {a.id for a in nearby_actors(dimension, center, radius) if is_item_entity(a)}
    processed: set[int] = set()

    def run() -> None:
        fresh = [
            a for a in nearby_actors(dimension, center, radius)
            if is_item_entity(a) and a.id not in before and a.id not in processed and actor_alive(a)
        ]
        if not fresh:
            return
        processed.update(a.id for a in fresh)
        ctx = DropContext(plugin, player, dimension, fresh, block_ids or set(), pos)
        for fn in ordered:
            try:
                fn(ctx)
            except Exception as exc:  # noqa: BLE001
                plugin.debug(f"drop op failed: {exc}")

    plugin.later(run, 1)
    plugin.later(run, 3)
