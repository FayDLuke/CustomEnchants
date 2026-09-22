from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Iterable

from endstone import Player
from endstone.actor import Item as ItemActor
from endstone.actor import Mob
from endstone.level import Location

from .constants import COLOR_CODES, PROJECTILE_TYPES

_ROMAN = (
    ("M", 1000), ("CM", 900), ("D", 500), ("CD", 400), ("C", 100), ("XC", 90),
    ("L", 50), ("XL", 40), ("X", 10), ("IX", 9), ("V", 5), ("IV", 4), ("I", 1),
)


def roman(value: int) -> str:
    out = ""
    for sym, num in _ROMAN:
        while value >= num:
            value -= num
            out += sym
    return out


def normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch not in " _-").replace("minecraft:", "")


def color_code(name: str) -> str:
    return COLOR_CODES.get(name.lower(), "§7")


@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, k: float) -> "Vec3":
        return Vec3(self.x * k, self.y * k, self.z * k)

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def horizontal_length(self) -> float:
        return math.sqrt(self.x * self.x + self.z * self.z)

    def normalized(self) -> "Vec3":
        n = self.length()
        return Vec3(self.x / n, self.y / n, self.z / n) if n > 1e-9 else Vec3()

    def dot(self, o: "Vec3") -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def distance(self, o: "Vec3") -> float:
        return (self - o).length()

    def floor(self) -> tuple[int, int, int]:
        return math.floor(self.x), math.floor(self.y), math.floor(self.z)


def vec_of(obj: Any) -> Vec3:
    return Vec3(float(obj.x), float(obj.y), float(obj.z))


def pos_of(actor: Any) -> Vec3:
    return vec_of(actor.location)


def direction_of(actor: Any) -> Vec3:
    return vec_of(actor.location.direction)


def yaw_pitch_for(direction: Vec3) -> tuple[float, float]:
    yaw = math.degrees(math.atan2(-direction.x, direction.z))
    pitch = -math.degrees(math.atan2(direction.y, direction.horizontal_length()))
    return yaw, pitch


def make_location(dimension: Any, pos: Vec3, pitch: float = 0.0, yaw: float = 0.0) -> Location:
    return Location(dimension, pos.x, pos.y, pos.z, pitch, yaw)


def teleport_to(actor: Any, pos: Vec3, yaw: float | None = None, pitch: float | None = None) -> bool:
    loc = actor.location
    loc.x, loc.y, loc.z = pos.x, pos.y, pos.z
    if yaw is not None:
        loc.yaw = yaw
    if pitch is not None:
        loc.pitch = pitch
    return actor.teleport(loc)


def is_player(actor: Any) -> bool:
    return isinstance(actor, Player)


def is_living(actor: Any) -> bool:
    return isinstance(actor, Mob)


def is_item_entity(actor: Any) -> bool:
    return isinstance(actor, ItemActor)


def is_projectile(actor: Any) -> bool:
    return getattr(actor, "type", "") in PROJECTILE_TYPES


def actor_alive(actor: Any) -> bool:
    try:
        return bool(actor.is_valid) and not actor.is_dead
    except Exception:
        return False


_HEIGHTS = {
    "minecraft:chicken": 0.7, "minecraft:pig": 0.9, "minecraft:cow": 1.4, "minecraft:sheep": 1.3,
    "minecraft:spider": 0.9, "minecraft:cave_spider": 0.5, "minecraft:creeper": 1.7,
    "minecraft:enderman": 2.9, "minecraft:wolf": 0.85, "minecraft:cat": 0.7, "minecraft:rabbit": 0.5,
    "minecraft:bat": 0.9, "minecraft:silverfish": 0.3, "minecraft:endermite": 0.3, "minecraft:squid": 0.8,
    "minecraft:villager_v2": 1.95, "minecraft:zombie": 1.95, "minecraft:skeleton": 1.99, "minecraft:witch": 1.95,
    "minecraft:iron_golem": 2.7, "minecraft:horse": 1.6, "minecraft:blaze": 1.8, "minecraft:ghast": 4.0,
    "minecraft:slime": 0.5, "minecraft:parrot": 0.9, "minecraft:llama": 1.87, "minecraft:fox": 0.7,
}


def entity_height(actor: Any) -> float:
    if isinstance(actor, Player):
        return 1.8
    return _HEIGHTS.get(getattr(actor, "type", ""), 1.8)


def nearby_actors(dimension: Any, center: Vec3, radius: float, exclude: Iterable[Any] = ()) -> list[Any]:
    excluded = {getattr(a, "id", None) for a in exclude if a is not None}
    r2 = radius * radius
    out = []
    for actor in dimension.actors:
        try:
            if actor.id in excluded:
                continue
            p = actor.location
            dx, dy, dz = p.x - center.x, p.y - center.y, p.z - center.z
            if dx * dx + dy * dy + dz * dz <= r2:
                out.append(actor)
        except Exception:
            continue
    return out


def find_actor(level: Any, actor_id: int) -> Any | None:
    for actor in level.actors:
        try:
            if actor.id == actor_id:
                return actor
        except Exception:
            continue
    return None


def same_actor(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return False
    if a is b:
        return True
    try:
        return a.id == b.id
    except Exception:
        return False


class ActorRef:
    """Stable handle to an actor; never keep raw actor wrappers across ticks."""

    __slots__ = ("uid", "player")

    def __init__(self, actor: Any) -> None:
        self.player = isinstance(actor, Player)
        self.uid = actor.unique_id if self.player else actor.id

    def __hash__(self) -> int:
        return hash((self.player, self.uid))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ActorRef) and (self.player, self.uid) == (other.player, other.uid)


def uvarint(n: int) -> bytes:
    n &= 0xFFFFFFFF
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def varint(n: int) -> bytes:
    return uvarint(((n << 1) ^ (n >> 31)) & 0xFFFFFFFF)


def now() -> float:
    return time.time()


class Cooldowns:
    """Per-player cooldowns in seconds, keyed by player name."""

    def __init__(self) -> None:
        self._until: dict[str, float] = {}

    def remaining(self, player: Player) -> float:
        return self._until.get(player.name, 0.0) - now()

    def set(self, player: Player, seconds: float) -> None:
        self._until[player.name] = now() + seconds


class NoFallDamage:
    """Port of Utils::shouldTakeFallDamage and friends."""

    def __init__(self) -> None:
        self._until: dict[str, float] = {}

    def should_take(self, player: Player) -> bool:
        return player.name not in self._until

    def set(self, player: Player, should_take: bool, duration: float = 1) -> None:
        self._until.pop(player.name, None)
        if not should_take:
            self._until[player.name] = now() + duration

    def remaining(self, player: Player) -> float:
        return self._until.get(player.name, now()) - now()

    def extend(self, player: Player, duration: float = 1) -> None:
        if player.name in self._until:
            self._until[player.name] += duration

    def clear(self, player: Player) -> None:
        self._until.pop(player.name, None)
