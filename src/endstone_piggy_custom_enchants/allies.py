from __future__ import annotations

from typing import Any, Callable

AllyCheck = Callable[[Any, Any], bool]


class AllyChecks:
    """Other plugins can register checks so enchants skip friendly targets (factions, parties ...)."""

    def __init__(self) -> None:
        self._checks: list[AllyCheck] = []

    def add_check(self, check: AllyCheck) -> None:
        self._checks.append(check)

    def is_ally(self, player: Any, entity: Any) -> bool:
        for check in self._checks:
            try:
                if check(player, entity):
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False
