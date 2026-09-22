"""Runs the enchants: reaction dispatch, ticking and toggling.

Endstone has no inventory-change events, so toggles are reconciled by diffing what the player currently
wears / holds against the previous scan (this replaces PocketMine's inventory listeners).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .constants import Trigger, Usage
from .enchant import CustomEnchant
from .events import SneakEv
from .items import (Slot, armor_slots, is_boots, is_chestplate, is_helmet, is_leggings)
from .storage import read_enchants
from .util import same_actor

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants


class Equipped:
    __slots__ = ("enchant", "level", "slot", "item")

    def __init__(self, enchant: CustomEnchant, level: int, slot: Slot, item: Any) -> None:
        self.enchant = enchant
        self.level = level
        self.slot = slot
        self.item = item

    def fresh_item(self) -> Any:
        """The current item of that slot, or None if the enchant is no longer there."""
        item = self.item if self.item is not None else self.slot.get()
        if item is None:
            return None
        return item if read_enchants(item).get(self.enchant.key, 0) == self.level else None


class PlayerState:
    def __init__(self) -> None:
        self.cache: dict[int, dict[str, int]] = {}
        self.cache_tick = -10_000
        self.dirty = True
        self.sneaking = False
        self.active: dict[tuple, Equipped] = {}


def applies(enchant: CustomEnchant, slot: Slot, item: Any, held_index: int) -> bool:
    usage = enchant.usage
    if slot.kind == "inv":
        if usage in (Usage.ANY_INVENTORY, Usage.INVENTORY):
            return True
        return usage == Usage.HAND and slot.index == held_index
    if usage in (Usage.ANY_INVENTORY, Usage.ARMOR_INVENTORY):
        return True
    if usage == Usage.HELMET:
        return slot.index == "helmet" and is_helmet(item)
    if usage == Usage.CHESTPLATE:
        return slot.index == "chestplate" and is_chestplate(item)
    if usage == Usage.LEGGINGS:
        return slot.index == "leggings" and is_leggings(item)
    if usage == Usage.BOOTS:
        return slot.index == "boots" and is_boots(item)
    return False


class Engine:
    def __init__(self, plugin: "PiggyCustomEnchants") -> None:
        self.plugin = plugin
        self.states: dict[Any, PlayerState] = {}

    def state(self, player: Any) -> PlayerState:
        st = self.states.get(player.unique_id)
        if st is None:
            st = self.states[player.unique_id] = PlayerState()
        return st

    def invalidate(self, player: Any) -> None:
        self.state(player).dirty = True

    # scanning
    def _parse(self, enchants: dict[str, int]) -> list[tuple[CustomEnchant, int]]:
        out = []
        for key, level in enchants.items():
            enchant = self.plugin.manager.enchants.get(key)
            if enchant is not None and self.plugin.manager.is_enabled(enchant):
                out.append((enchant, level))
        out.sort(key=lambda t: -t[0].priority)
        return out

    def _refresh_cache(self, player: Any, st: PlayerState) -> None:
        st.cache = {}
        try:
            contents = list(player.inventory.contents)
        except Exception:  # noqa: BLE001
            contents = [player.inventory.get_item(i) for i in range(player.inventory.size)]
        for idx, item in enumerate(contents):
            if item is None:
                continue
            found = read_enchants(item)
            if found:
                st.cache[idx] = found
        st.cache_tick = self.plugin.tick_count
        st.dirty = False

    def gather(self, player: Any, full: bool = False) -> list[Equipped]:
        """Every enchanted slot of the player: inventory first, then armor (the order PocketMine used)."""
        st = self.state(player)
        interval = int(self.plugin.cfg("inventory-scan-interval", 5))
        if full or st.dirty or self.plugin.tick_count - st.cache_tick >= interval:
            self._refresh_cache(player, st)
        held_index = player.inventory.held_item_slot
        held = Slot(player, "inv", held_index).get()
        st.cache.pop(held_index, None)
        if held is not None:
            found = read_enchants(held)
            if found:
                st.cache[held_index] = found
        out: list[Equipped] = []
        for idx in sorted(st.cache):
            slot = Slot(player, "inv", idx)
            item = held if idx == held_index else None
            for enchant, level in self._parse(st.cache[idx]):
                if applies(enchant, slot, item, held_index):
                    out.append(Equipped(enchant, level, slot, item))
        for slot in armor_slots(player):
            item = slot.get()
            if item is None:
                continue
            for enchant, level in self._parse(read_enchants(item)):
                if applies(enchant, slot, item, held_index):
                    out.append(Equipped(enchant, level, slot, item))
        return out

    # reactions
    def attempt(self, player: Any, event: Any, full: bool = False) -> None:
        """Port of ReactiveTrait::attemptReaction."""
        tracked = getattr(event, "tracked", None)
        if tracked is not None and (Trigger.DAMAGE_BY_CHILD in event.kinds or Trigger.PROJECTILE_HIT_BLOCK in event.kinds):
            is_owner = Trigger.PROJECTILE_HIT_BLOCK in event.kinds or same_actor(event.damager, player)
            if is_owner:
                self._react_tracked(player, event, tracked)
                self.plugin.projectiles.remove(tracked.id)
                return
        stacks: dict[str, int] = {}
        for e in self.gather(player, full):
            enchant = e.enchant
            if not enchant.reactive or not event.matches(enchant.reagents):
                continue
            item = e.fresh_item()
            if item is None:
                continue
            stacks[enchant.key] = stacks.get(enchant.key, 0) + e.level
            self._call_reaction(player, enchant, item, e.slot, event, e.level, stacks[enchant.key])

    def _react_tracked(self, player: Any, event: Any, tracked: Any) -> None:
        held_slot = Slot(player, "inv", player.inventory.held_item_slot)
        entries = self._parse(tracked.enchants)
        for enchant, level in entries:
            if not enchant.reactive or not event.matches(enchant.reagents):
                continue
            if enchant.usage not in (Usage.INVENTORY, Usage.ANY_INVENTORY, Usage.HAND):
                continue
            self._call_reaction(player, enchant, tracked.item, held_slot, event, level, 1)

    def _call_reaction(self, player: Any, enchant: CustomEnchant, item: Any, slot: Slot, event: Any,
                       level: int, stack: int) -> None:
        try:
            enchant.on_reaction(player, item, slot, event, level, stack)
        except Exception as exc:  # noqa: BLE001
            self.plugin.logger.error(f"[{enchant.name}] reaction failed: {exc!r}")
            self.plugin.debug_trace()

    # ticking / toggling
    def tick_player(self, player: Any) -> None:
        st = self.state(player)
        entries = self.gather(player)
        tick = self.plugin.tick_count
        ran: set[str] = set()
        for e in entries:
            enchant = e.enchant
            if not enchant.ticking or tick % max(1, enchant.tick_interval) != 0:
                continue
            if not enchant.supports_multiple_items and enchant.key in ran:
                continue
            item = e.fresh_item()
            if item is None:
                continue
            ran.add(enchant.key)
            try:
                enchant.on_tick(player, item, e.slot, e.level)
            except Exception as exc:  # noqa: BLE001
                self.plugin.logger.error(f"[{enchant.name}] tick failed: {exc!r}")
                self.plugin.debug_trace()
        self.reconcile_toggles(player, st, entries)
        sneaking = bool(player.is_sneaking)
        if sneaking != st.sneaking:
            st.sneaking = sneaking
            self.attempt(player, SneakEv(sneaking))

    def reconcile_toggles(self, player: Any, st: PlayerState, entries: list[Equipped] | None = None) -> None:
        if entries is None:
            entries = self.gather(player, full=True)
        desired: dict[tuple, Equipped] = {}
        for e in entries:
            if e.enchant.toggleable:
                desired[(e.enchant.key, e.slot.key(), e.level)] = e
        for key in [k for k in st.active if k not in desired]:
            old = st.active.pop(key)
            self._toggle(player, old, False)
        for key, e in desired.items():
            if key not in st.active:
                st.active[key] = e
                self._toggle(player, e, True)

    def _toggle(self, player: Any, e: Equipped, on: bool) -> None:
        try:
            item = e.item if on else None
            if on and item is None:
                item = e.slot.get()
            e.enchant.on_toggle(player, item, e.slot, e.level, on)
        except Exception as exc:  # noqa: BLE001
            self.plugin.logger.error(f"[{e.enchant.name}] toggle failed: {exc!r}")
            self.plugin.debug_trace()

    def release(self, player: Any) -> None:
        """Toggle everything off (player quits / plugin disables)."""
        st = self.states.get(player.unique_id)
        if st is None:
            return
        for key in list(st.active):
            self._toggle(player, st.active.pop(key), False)
        for enchant in self.plugin.manager.all():
            enchant.forget(player)

    def forget(self, player: Any) -> None:
        self.states.pop(player.unique_id, None)
