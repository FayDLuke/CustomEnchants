class EventPriority:
    LOWEST = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    HIGHEST = 4
    MONITOR = 5


def event_handler(func=None, *, priority=EventPriority.NORMAL, ignore_cancelled=False):
    def deco(f):
        f._is_event_handler = True
        f._priority = priority
        f._ignore_cancelled = ignore_cancelled
        return f
    return deco(func) if func else deco


class _Event:
    def __init__(self):
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @property
    def is_cancelled(self):
        return self._cancelled


class ActorDamageEvent(_Event): pass
class ActorKnockbackEvent(_Event): pass
class ActorSpawnEvent(_Event): pass
class BlockBreakEvent(_Event): pass
class PlayerDeathEvent(_Event): pass
class PlayerInteractEvent(_Event): pass
class PlayerItemHeldEvent(_Event): pass
class PlayerJoinEvent(_Event): pass
class PlayerJumpEvent(_Event): pass
class PlayerMoveEvent(_Event): pass
class PlayerQuitEvent(_Event): pass
class PlayerRespawnEvent(_Event): pass
