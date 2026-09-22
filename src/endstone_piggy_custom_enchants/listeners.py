"""Endstone event handlers.

NOTE: this module intentionally does NOT use `from __future__ import annotations`: Endstone reads the
handler's parameter annotation at registration time and needs the real event class, not a string.
"""
import functools

from endstone import Player
from endstone.actor import Item as ItemActor
from endstone.event import (ActorDamageEvent, ActorKnockbackEvent, ActorSpawnEvent, BlockBreakEvent, EventPriority,
                            PlayerDeathEvent, PlayerInteractEvent, PlayerItemHeldEvent, PlayerJoinEvent,
                            PlayerJumpEvent, PlayerMoveEvent, PlayerQuitEvent, PlayerRespawnEvent, event_handler)

from .drops import schedule_drop_ops
from .events import BreakEv, DamageEv, DeathEv, InteractEv, KnockbackEv, MoveEv
from .items import held_item
from .util import Vec3, is_player, is_projectile, pos_of, same_actor, vec_of

FACE_NORMALS = {
    "DOWN": (0, -1, 0), "UP": (0, 1, 0), "NORTH": (0, 0, -1), "SOUTH": (0, 0, 1), "WEST": (-1, 0, 0),
    "EAST": (1, 0, 0),
}


def guarded(fn):
    @functools.wraps(fn)
    def wrapper(self, event):
        try:
            return fn(self, event)
        except Exception as exc:  # noqa: BLE001
            self.plugin.logger.error(f"{fn.__name__} failed: {exc!r}")
            self.plugin.debug_trace()
            return None

    return wrapper


class PiggyListener:
    def __init__(self, plugin):
        self.plugin = plugin

    # damage
    @event_handler(priority=EventPriority.HIGHEST, ignore_cancelled=True)
    @guarded
    def on_damage(self, event: ActorDamageEvent):
        p = self.plugin
        ctx = p.damage_ctx
        if ctx is not None and ctx.mode == "suppress":
            return
        victim = event.actor
        src = event.damage_source
        cause = str(src.type)

        if is_player(victim) and cause == "fall" and not p.nofall.should_take(victim):
            boots = victim.inventory.boots
            springs = p.manager.get("springs")
            if boots is None or springs is None or p.manager.level_on(boots, springs) == 0:
                p.nofall.set(victim, True)
            event.cancel()
            return

        damager = src.actor
        damaging = src.damaging_actor
        child = tracked = child_pos = None
        if ctx is not None and ctx.mode == "child":
            tracked, damager = ctx.tracked, ctx.owner
            child = tracked
            child_pos = tracked.extra.get("pos")
        elif damaging is not None:
            if damager is not None and not same_actor(damaging, damager):
                child = damaging
            elif damager is None and is_projectile(damaging):
                child = damaging
            if child is not None:
                tracked = p.projectiles.get(damaging.id)
                child_pos = pos_of(damaging)
                if damager is None and tracked is not None:
                    damager = p.resolve(tracked.owner)

        involves_player = is_player(victim) or is_player(damager)
        if not involves_player:
            return
        ev = DamageEv(event, victim, damager, child, cause, tracked, child_pos)
        if is_player(victim):
            p.engine.attempt(victim, ev)
        if ev.by_entity and is_player(damager):
            p.engine.attempt(damager, ev)

    @event_handler(priority=EventPriority.HIGHEST, ignore_cancelled=True)
    @guarded
    def on_knockback(self, event: ActorKnockbackEvent):
        victim = event.actor
        if is_player(victim):
            self.plugin.engine.attempt(victim, KnockbackEv(event))

    # world interaction
    @event_handler(priority=EventPriority.HIGHEST, ignore_cancelled=True)
    @guarded
    def on_break(self, event: BlockBreakEvent):
        p = self.plugin
        magma = p.manager.get("magmawalker")
        if magma is not None and magma.handle_break(event):
            return
        player, block = event.player, event.block
        ev = BreakEv(event, player, block, held_item(player))
        p.engine.attempt(player, ev)
        if ev.drop_ops and not event.is_cancelled:
            center = Vec3(block.x + 0.5, block.y + 0.5, block.z + 0.5)
            schedule_drop_ops(p, player, ev.dimension, center, 2.5, ev.drop_ops, {ev.block_id}, ev.pos)

    @event_handler(priority=EventPriority.HIGHEST)
    @guarded
    def on_interact(self, event: PlayerInteractEvent):
        p = self.plugin
        player = event.player
        action = getattr(event.action, "name", str(event.action))
        if action == "LEFT_CLICK_BLOCK":
            normal = FACE_NORMALS.get(getattr(event.block_face, "name", ""))
            if normal is not None:
                p.break_faces[player.name] = normal
        elif action.startswith("RIGHT_CLICK"):
            p.try_apply_book(player)
        p.engine.attempt(player, InteractEv(event))

    @event_handler(priority=EventPriority.HIGHEST, ignore_cancelled=True)
    @guarded
    def on_move(self, event: PlayerMoveEvent):
        p = self.plugin
        player = event.player
        if not p.nofall.should_take(player):
            x, y, z = pos_of(player).floor()
            if p.world.block_id(player.dimension, x, y - 1, z) != "minecraft:air" and p.nofall.remaining(player) <= 0:
                p.nofall.set(player, True)
            else:
                p.nofall.extend(player, 1)
        origin, target = vec_of(event.from_location), vec_of(event.to_location)
        if origin.floor() == target.floor():
            return
        p.engine.attempt(player, MoveEv(origin, target))

    @event_handler
    @guarded
    def on_jump(self, event: PlayerJumpEvent):
        spider = self.plugin.manager.get("spider")
        if spider is not None and self.plugin.manager.is_enabled(spider):
            spider.on_jump(event.player)

    @event_handler
    @guarded
    def on_held(self, event: PlayerItemHeldEvent):
        p = self.plugin
        player = event.player
        p.engine.invalidate(player)
        if not p.cfg("enchants.show-switch-popup", True):
            return
        item = player.inventory.get_item(event.new_slot)
        text = p.manager.popup_text(item)
        if text is not None:
            player.send_popup(text)

    # projectiles
    @event_handler(priority=EventPriority.MONITOR)
    @guarded
    def on_spawn(self, event: ActorSpawnEvent):
        actor = event.actor
        if isinstance(actor, ItemActor):
            return
        self.plugin.projectiles.on_actor_spawn(actor)

    # player lifecycle
    @event_handler
    @guarded
    def on_join(self, event: PlayerJoinEvent):
        self.plugin.engine.invalidate(event.player)

    @event_handler
    @guarded
    def on_quit(self, event: PlayerQuitEvent):
        p = self.plugin
        player = event.player
        p.restore_soulbound(player)
        p.engine.release(player)
        p.engine.forget(player)
        p.effects.forget(player)
        p.nofall.clear(player)
        p.break_faces.pop(player.name, None)

    @event_handler(priority=EventPriority.HIGHEST)
    @guarded
    def on_death(self, event: PlayerDeathEvent):
        p = self.plugin
        player = event.player
        ev = DeathEv(event, player)
        death_pos = pos_of(player)
        p.engine.attempt(player, ev, full=True)
        p.keep_soulbound(player, ev.kept, death_pos)
        p.effects.forget(player)
        p.nofall.clear(player)
        p.engine.invalidate(player)

    @event_handler
    @guarded
    def on_respawn(self, event: PlayerRespawnEvent):
        p = self.plugin
        player = event.player
        p.engine.invalidate(player)
        uid = player.unique_id

        def restore():
            target = p.server.get_player(uid)
            if target is not None:
                p.restore_soulbound(target)

        p.later(restore, 2)
