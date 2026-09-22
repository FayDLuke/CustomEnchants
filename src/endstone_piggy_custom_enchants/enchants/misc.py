from __future__ import annotations

from typing import Any

from endstone.nbt import IntTag

from ..constants import Kind, Trigger, Usage
from ..enchant import CustomEnchant
from ..events import DeathEv, MoveEv
from ..items import Slot, is_durable, max_durability
from ..util import actor_alive, pos_of, same_actor, uvarint, varint


class AutoRepairEnchant(CustomEnchant):
    name = "Autorepair"
    rarity = "uncommon"
    usage = Usage.ANY_INVENTORY
    item_kind = Kind.DAMAGEABLE
    reactive = True
    reagents = (Trigger.MOVE,)

    def default_extra(self) -> dict[str, Any]:
        return {"baseRepair": 1, "repairMultiplier": 1}

    def react(self, player, item, slot: Slot, event, level, stack):
        if not isinstance(event, MoveEv) or not is_durable(item):
            return
        nbt = item.nbt
        damage = int(nbt.to_dict().get("Damage", 0))
        if damage <= 0:
            return
        new = max(0, damage - (int(self.extra["baseRepair"]) + int(self.extra["repairMultiplier"]) * level))
        nbt["Damage"] = IntTag(min(new, max_durability(item)))
        item.nbt = nbt
        slot.set(item)


class LuckyCharmEnchant(CustomEnchant):
    name = "Lucky Charm"
    rarity = "mythic"
    max_level = 3
    usage = Usage.INVENTORY
    item_kind = Kind.GLOBAL
    toggleable = True

    def default_extra(self) -> dict[str, Any]:
        return {"additionalMultiplier": 0.05}

    def toggle(self, player, item, slot, level, toggle):
        for enchant in self.plugin.manager.all():
            if enchant.reactive:
                enchant.set_chance_multiplier(
                    player,
                    enchant.get_chance_multiplier(player) + (1 if toggle else -1) * level * self.extra["additionalMultiplier"],
                )


def _block_pos(x: int, y: int, z: int) -> bytes:
    return varint(x) + uvarint(y) + varint(z)


SET_SPAWN_POSITION_ID = 43


def set_spawn_payload(x: int, y: int, z: int, dimension: int = 0) -> bytes:
    """SetSpawnPositionPacket.worldSpawn(): spawn type 1 = world spawn."""
    return varint(1) + _block_pos(x, y, z) + varint(dimension) + _block_pos(x, y, z)


class RadarEnchant(CustomEnchant):
    """Points the compass at the nearest player through a raw SetSpawnPosition packet (experimental)."""

    name = "Radar"
    usage = Usage.INVENTORY
    item_kind = Kind.COMPASS
    ticking = True
    toggleable = True

    def default_extra(self) -> dict[str, Any]:
        return {"radiusMultiplier": 50}

    def find_nearest_player(self, player: Any, radius: float) -> Any | None:
        best, best_d = None, radius
        me = pos_of(player)
        for other in self.plugin.server.online_players:
            try:
                if same_actor(other, player) or other.dimension.name != player.dimension.name or not actor_alive(other):
                    continue
                d = pos_of(other).distance(me)
                if d <= radius and d < best_d:
                    best, best_d = other, d
            except Exception:  # noqa: BLE001
                continue
        return best

    def _spawn_of(self, player: Any) -> tuple[int, int, int]:
        try:
            spawn = player.location.dimension.level.spawn_location  # not present on every build
            return int(spawn.x), int(spawn.y), int(spawn.z)
        except Exception:  # noqa: BLE001
            return 0, 64, 0

    def set_compass(self, player: Any, x: int, y: int, z: int) -> None:
        try:
            player.send_packet(SET_SPAWN_POSITION_ID, set_spawn_payload(x, y, z, 0))
        except Exception as exc:  # noqa: BLE001
            self.plugin.debug(f"radar packet failed: {exc}")

    def tick(self, player, item, slot, level):
        detected = self.find_nearest_player(player, level * self.extra["radiusMultiplier"])
        if detected is not None:
            x, y, z = pos_of(detected).floor()
        else:
            x, y, z = self._spawn_of(player)
        self.set_compass(player, x, y, z)
        if slot.is_held:
            if detected is None:
                player.send_tip("§cNo players found.")
            else:
                player.send_tip(f"§aNearest player {round(pos_of(player).distance(pos_of(detected)), 1)} blocks away.")

    def toggle(self, player, item, slot, level, toggle):
        if not toggle:
            self.set_compass(player, *self._spawn_of(player))


class SoulboundEnchant(CustomEnchant):
    name = "Soulbound"
    rarity = "mythic"
    usage = Usage.ANY_INVENTORY
    item_kind = Kind.GLOBAL
    reactive = True
    reagents = (Trigger.DEATH,)

    def react(self, player, item, slot: Slot, event, level, stack):
        if not isinstance(event, DeathEv):
            return
        kept = item
        mgr = self.plugin.manager
        if level > 1:
            mgr.add_enchant(kept, self, level - 1, check_compatibility=False)
        else:
            mgr.remove_enchant(kept, self)
        event.kept.append((slot.key(), kept))
        slot.set(None)
