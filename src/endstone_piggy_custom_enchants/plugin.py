from __future__ import annotations

import random
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from endstone import Player
from endstone.plugin import Plugin

from . import storage
from .allies import AllyChecks
from .commands import CommandHandler
from .compat import Combat, Commands, EffectManager, WorldOps
from .constants import DEFAULT_RARITY_COLORS, PROJECTILE_TYPES, UNBREAKABLE_BLOCKS
from .drops import schedule_drop_ops
from .enchant import EnchantData
from .engine import Engine
from .explosion import explosion_effects
from .items import Slot, held_item, is_air, is_book, item_matches_kind
from .manager import CustomEnchantManager
from .motion import MotionManager
from .projectiles import ProjectileManager
from .util import ActorRef, NoFallDamage, Vec3, direction_of, is_item_entity, normalize_name, pos_of

RESOURCES = Path(__file__).parent / "resources"


class DamageContext:
    def __init__(self, mode: str, tracked: Any = None, owner: Any = None) -> None:
        self.mode = mode  # "suppress" | "child"
        self.tracked = tracked
        self.owner = owner


class PiggyCustomEnchants(Plugin):
    prefix = "PiggyCustomEnchants"
    api_version = "0.11"
    version = "3.0.12"
    description = "Custom enchantments for Endstone (port of DaPigGuy's PiggyCustomEnchants)"
    authors = ["DaPigGuy (original plugin)", "Endstone port"]
    website = "https://github.com/DaPigGuy/PiggyCustomEnchants"

    commands = {
        "customenchants": {
            "description": "Manage PiggyCustomEnchants custom enchantments",
            "usages": [
                "/customenchants",
                "/customenchants <about|list|nbt>",
                "/customenchants info [enchantment: string]",
                "/customenchants enchant [enchantment: string] [level: int] [player: player]",
                "/customenchants remove [enchantment: string] [player: player]",
            ],
            "aliases": ["ce", "customenchant"],
            "permissions": ["piggycustomenchants.command.ce"],
        }
    }

    permissions = {
        "piggycustomenchants.command.ce": {"description": "Allows using /ce", "default": True},
        "piggycustomenchants.command.ce.about": {"description": "Allows /ce about", "default": True},
        "piggycustomenchants.command.ce.list": {"description": "Allows /ce list and /ce info", "default": True},
        "piggycustomenchants.command.ce.enchant": {"description": "Allows /ce enchant", "default": "op"},
        "piggycustomenchants.command.ce.remove": {"description": "Allows /ce remove", "default": "op"},
        "piggycustomenchants.command.ce.nbt": {"description": "Allows /ce nbt", "default": "op"},
        "piggycustomenchants.overridecheck": {
            "description": "Ignore item type / max level / incompatibility checks when enchanting", "default": "op",
        },
    }

    def __init__(self) -> None:
        super().__init__()
        self.tick_count = 0
        self._cfg: dict[str, Any] = {}
        self.disabled_enchants: set[str] = set()
        self.rarity_colors: dict[str, str] = dict(DEFAULT_RARITY_COLORS)
        self.recursion: set[str] = set()
        self.damage_ctx: DamageContext | None = None
        self.break_faces: dict[str, tuple[int, int, int]] = {}
        self.soulbound_kept: dict[Any, list[tuple[Any, Any]]] = {}
        self._debug = False
        self._actor_stamp = -1
        self._actors: dict[str, list[Any]] = {}
        self._index_stamp = -1
        self._index: dict[int, Any] = {}
        self.allies = AllyChecks()
        self.nofall = NoFallDamage()
        self.projectile_types = PROJECTILE_TYPES

    # lifecycle
    def on_enable(self) -> None:
        try:
            self.save_default_config()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"Could not write the default config: {exc}")
        self._load_config()
        self.runner = Commands(self)
        self.effects = EffectManager(self)
        self.combat = Combat(self)
        self.world = WorldOps(self)
        self.motion = MotionManager(self)
        self.projectiles = ProjectileManager(self)
        self.engine = Engine(self)
        self.manager = CustomEnchantManager(self)
        self.enchant_data = EnchantData(Path(self.data_folder), RESOURCES)
        self.manager.register_all()
        self.enchant_data.flush()
        self.command_handler = CommandHandler(self)

        from .listeners import PiggyListener

        self.register_events(PiggyListener(self))
        self.server.scheduler.run_task(self, self._tick, delay=1, period=1)
        supported = [e for e in self.manager.all() if self.manager.is_enabled(e)]
        self.logger.info(
            f"Loaded {len(self.manager.all())} custom enchants ({len(supported)} active). "
            "Endstone cannot run the unsupported ones, see /ce list."
        )
        for player in self.server.online_players:
            self.engine.invalidate(player)

    def on_disable(self) -> None:
        try:
            for player in self.server.online_players:
                self.restore_soulbound(player)
                self.engine.release(player)
            self.manager.disable_all()
            self.motion.clear()
            self.projectiles.clear()
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"Error while disabling: {exc!r}")
        self.server.scheduler.cancel_tasks(self)

    def on_command(self, sender: Any, command: Any, args: list[str]) -> bool:
        return self.command_handler.run(sender, args)

    # config
    def _load_config(self) -> None:
        try:
            cfg = self.reload_config()
            self._cfg = cfg.unwrap() if hasattr(cfg, "unwrap") else dict(cfg)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"Using built-in defaults, config could not be read: {exc}")
            self._cfg = {}
        self._debug = bool(self.cfg("debug", False))
        self.disabled_enchants = {normalize_name(str(n)) for n in self._cfg.get("disabled-enchants", [])}
        colors = dict(DEFAULT_RARITY_COLORS)
        colors.update({str(k): str(v) for k, v in self._cfg.get("rarity-colors", {}).items()})
        self.rarity_colors = colors

    def cfg(self, key: str, default: Any = None) -> Any:
        cfg = self._cfg
        if "." in key:
            node: Any = cfg
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return node
        for table in ("endstone", "enchants"):
            section = cfg.get(table)
            if isinstance(section, dict) and key in section:
                return section[key]
        return cfg.get(key, default)

    def forms_enabled(self) -> bool:
        return bool(self.cfg("forms.enabled", False))

    def is_disabled_in_world(self, key: str, player: Any) -> bool:
        table = self._cfg.get("per-world-disabled-enchants", {})
        if not table:
            return False
        try:
            names = {player.level.name, player.dimension.name}
        except Exception:  # noqa: BLE001
            return False
        for name in names:
            if key in {normalize_name(str(e)) for e in table.get(name, [])}:
                return True
        return False

    # logging / scheduling
    def debug(self, message: str) -> None:
        if self._debug:
            self.logger.info(f"[debug] {message}")

    def debug_trace(self) -> None:
        if self._debug:
            self.logger.error(traceback.format_exc())

    def later(self, fn: Callable[[], Any], ticks: int = 1) -> Any:
        def run() -> None:
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                self.logger.error(f"Scheduled task failed: {exc!r}")
                self.debug_trace()

        return self.server.scheduler.run_task(self, run, delay=max(1, int(ticks)))

    def repeat(self, fn: Callable[[], Any], delay: int, period: int) -> Any:
        """Repeating task; `fn` returns False to stop it."""
        holder: dict[str, Any] = {}

        def run() -> None:
            keep = True
            try:
                keep = fn() is not False
            except Exception as exc:  # noqa: BLE001
                self.logger.error(f"Repeating task failed: {exc!r}")
                self.debug_trace()
                keep = False
            if not keep and "task" in holder:
                holder["task"].cancel()

        holder["task"] = self.server.scheduler.run_task(self, run, delay=max(1, int(delay)), period=max(1, int(period)))
        return holder["task"]

    # main tick
    def _tick(self) -> None:
        self.tick_count += 1
        for player in list(self.server.online_players):
            try:
                self.engine.tick_player(player)
            except Exception as exc:  # noqa: BLE001
                self.logger.error(f"Tick failed for {player.name}: {exc!r}")
                self.debug_trace()
        self.projectiles.tick()
        self.motion.tick()
        for enchant in self.manager.all():
            hook = getattr(enchant, "global_tick", None)
            if hook is not None:
                try:
                    hook(self.tick_count)
                except Exception as exc:  # noqa: BLE001
                    self.logger.error(f"[{enchant.name}] global tick failed: {exc!r}")

    # actor lookup
    def actors_in(self, dimension: Any) -> list[Any]:
        if self._actor_stamp != self.tick_count:
            self._actors.clear()
            self._actor_stamp = self.tick_count
        key = dimension.name
        if key not in self._actors:
            self._actors[key] = list(dimension.actors)
        return self._actors[key]

    def _actor_index(self) -> dict[int, Any]:
        if self._index_stamp != self.tick_count:
            self._index = {}
            try:
                for dim in self.server.level.dimensions:
                    for actor in self.actors_in(dim):
                        self._index[actor.id] = actor
            except Exception as exc:  # noqa: BLE001
                self.debug(f"actor index failed: {exc}")
            self._index_stamp = self.tick_count
        return self._index

    def find_actor(self, actor_id: int) -> Any | None:
        return self._actor_index().get(actor_id)

    def resolve(self, ref: ActorRef | None) -> Any | None:
        if ref is None:
            return None
        if ref.player:
            try:
                return self.server.get_player(ref.uid)
            except Exception:  # noqa: BLE001
                return None
        return self.find_actor(ref.uid)

    # damage context
    @contextmanager
    def suppress_damage(self) -> Iterator[None]:
        previous = self.damage_ctx
        self.damage_ctx = DamageContext("suppress")
        try:
            yield
        finally:
            self.damage_ctx = previous

    @contextmanager
    def damage_as_child(self, tracked: Any, owner: Any) -> Iterator[None]:
        previous = self.damage_ctx
        self.damage_ctx = DamageContext("child", tracked, owner)
        try:
            yield
        finally:
            self.damage_ctx = previous

    # world helpers used by enchants
    def break_normal(self, player: Player) -> tuple[int, int, int]:
        """Normal of the face the player last started breaking (points towards the player)."""
        normal = self.break_faces.get(player.name)
        if normal is not None:
            return normal
        d = direction_of(player)
        axis = max(("x", abs(d.x)), ("y", abs(d.y)), ("z", abs(d.z)), key=lambda t: t[1])[0]
        sign = -1 if getattr(d, axis) > 0 else 1
        return (sign if axis == "x" else 0, sign if axis == "y" else 0, sign if axis == "z" else 0)

    def break_blocks(
        self,
        player: Player,
        dimension: Any,
        positions: list[tuple[int, int, int]],
        tool: Any,
        region_radius: float | None = None,
        center: Vec3 | None = None,
        drop_chance: float = 1.0,
    ) -> int:
        """useBreakOn() for a batch of blocks: destroy with drops, then run Telepathy/Smelting/Jackpot."""
        broken: list[tuple[int, int, int]] = []
        ids: set[str] = set()
        for pos in positions:
            block_id = self.world.block_id(dimension, *pos)
            if block_id in UNBREAKABLE_BLOCKS:
                continue
            ids.add(block_id)
            if drop_chance >= 1.0 or random.random() < drop_chance:
                self.world.destroy_block(dimension, *pos)
            else:
                self.world.set_block(dimension, pos[0], pos[1], pos[2], "minecraft:air")
            broken.append(pos)
        if not broken:
            return 0
        ops = []
        for enchant, level in self.manager.enchants_of(tool).items():
            make_op = getattr(enchant, "make_op", None)
            if make_op is not None and self.manager.is_enabled(enchant):
                ops.append((enchant.priority, make_op(player, level)))
        if ops:
            if center is None:
                xs, ys, zs = zip(*broken)
                center = Vec3((min(xs) + max(xs)) / 2 + 0.5, (min(ys) + max(ys)) / 2 + 0.5, (min(zs) + max(zs)) / 2 + 0.5)
                region_radius = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2 + 2.5
            schedule_drop_ops(self, player, dimension, center, region_radius or 3.0, ops, ids, broken[0])
        return len(broken)

    def explosion_effects(self, dimension: Any, center: Vec3, size: float, owner: Any) -> None:
        explosion_effects(self, dimension, center, size, owner)

    # soulbound
    def keep_soulbound(self, player: Player, kept: list[tuple[Any, Any]], death_pos: Vec3) -> None:
        if not kept:
            return
        self.soulbound_kept[player.unique_id] = kept
        dimension = player.dimension
        before = {a.id for a in self.actors_in(dimension) if is_item_entity(a)}

        def sweep() -> None:
            # if the death handler ran after the inventory was already dropped, remove the duplicates
            for actor in self.actors_in(dimension):
                try:
                    if not is_item_entity(actor) or actor.id in before:
                        continue
                    if pos_of(actor).distance(death_pos) > 6:
                        continue
                    if storage.read_enchants(actor.item_stack).get("soulbound", 0) > 0:
                        actor.remove()
                except Exception:  # noqa: BLE001
                    continue

        self.later(sweep, 1)
        self.later(sweep, 4)

    def restore_soulbound(self, player: Player) -> None:
        kept = self.soulbound_kept.pop(player.unique_id, None)
        if not kept:
            return
        for (kind, index), item in kept:
            slot = Slot(player, kind, index)
            if slot.get() is None:
                slot.set(item)
            else:
                leftover = player.inventory.add_item(item)
                for rest in (leftover or {}).values():
                    player.dimension.drop_item(player.location, rest)
        self.engine.invalidate(player)

    # books
    def try_apply_book(self, player: Player) -> None:
        """Enchant book in the main hand + target item in the off hand, then right click."""
        if not self.cfg("books", True):
            return
        book = held_item(player)
        target = player.inventory.item_in_off_hand
        if book is None or is_air(target) or not is_book(book) or is_book(target):
            return
        book_enchants = storage.read_enchants(book)
        if not book_enchants:
            return
        if target.amount != 1:
            player.send_message("§cYou can only enchant one item at a time.")
            return
        applied = []
        for key, level in book_enchants.items():
            enchant = self.manager.enchants.get(key)
            if enchant is None or not self.manager.is_enabled(enchant):
                continue
            existing = storage.read_enchants(target).get(key, 0)
            if existing >= level or not item_matches_kind(target, enchant.item_kind):
                continue
            if not self.manager.is_compatible(target, enchant):
                continue
            self.manager.add_enchant(target, enchant, level, check_compatibility=False)
            applied.append(enchant.display_name)
        if not applied:
            player.send_message("§cNothing could be applied to the item in your off hand.")
            return
        player.inventory.item_in_off_hand = target
        if book.amount > 1:
            book.amount -= 1
            player.inventory.set_item(player.inventory.held_item_slot, book)
        else:
            player.inventory.set_item(player.inventory.held_item_slot, None)
        self.engine.invalidate(player)
        player.send_message("§aApplied: " + ", ".join(applied))
