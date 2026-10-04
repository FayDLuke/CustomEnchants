"""Test double for the real `endstone-inventoryui` package (not installable here: it depends on
`bedrock-protocol-packets-ng`, which needs network access this sandbox doesn't have).

MenuInventory below is lifted near-verbatim from the real library's menu/inventory.py (same get_item/
set_item/contents semantics) since that's the part our integration code touches directly. Menu/
MenuTransaction only keep the surface our code calls (set_listener, send_to, inventory, proceed/discard);
the real library's session/packet machinery is not reproduced since our tests drive the listener directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class ItemStackLike:
    """Minimal stand-in so this file doesn't depend on endstone.inventory.ItemStack."""


class MenuType(Enum):
    HOPPER = 5
    DISPENSER = 9
    CHEST = 27
    DOUBLE_CHEST = 54

    @property
    def container_size(self) -> int:
        return self.value


class MenuInventory:
    def __init__(self, size: int = 36, max_stack_size: int = 64, slot_updated=None):
        self._size = size
        self._slots: list[Any] = [None] * size
        self._slot_updated = slot_updated

    @property
    def size(self) -> int:
        return self._size

    def get_item(self, index: int):
        from endstone.inventory import ItemStack

        item = self._slots[index]
        return item if item is not None else ItemStack("minecraft:air")

    def set_item(self, index: int, item) -> None:
        self._slots[index] = item
        if self._slot_updated is not None:
            self._slot_updated(index)

    @property
    def contents(self) -> list[Any]:
        return list(self._slots)


class MenuTransactionResultType(Enum):
    CONTINUE = "continue"
    DISCARD = "discard"


@dataclass(frozen=True)
class MenuTransactionResult:
    type: MenuTransactionResultType

    @property
    def should_continue(self) -> bool:
        return self.type == MenuTransactionResultType.CONTINUE

    @property
    def should_discard(self) -> bool:
        return self.type == MenuTransactionResultType.DISCARD


@dataclass(frozen=True)
class MenuTransaction:
    player: Any
    slot: int
    item_clicked: Any = None
    item_clicked_with: Any = None
    action_type: Any = None
    source: Any = None
    destination: Any = None

    def proceed(self) -> MenuTransactionResult:
        return MenuTransactionResult(MenuTransactionResultType.CONTINUE)

    def discard(self) -> MenuTransactionResult:
        return MenuTransactionResult(MenuTransactionResultType.DISCARD)


class Menu:
    def __init__(self, type: MenuType, name: str = ""):
        self._name = name
        self._type = type
        self._inventory = MenuInventory(type.container_size)
        self._listener: Callable[[MenuTransaction], MenuTransactionResult] | None = None
        self._sent_to: list[Any] = []

    @property
    def inventory(self) -> MenuInventory:
        return self._inventory

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> MenuType:
        return self._type

    def set_listener(self, listener) -> None:
        self._listener = listener

    def set_open_listener(self, listener) -> None:
        pass

    def set_close_listener(self, listener) -> None:
        pass

    def send_to(self, player) -> None:
        self._sent_to.append(player)

    def close(self, player) -> bool:
        return False

    def close_all(self) -> None:
        pass

    def get_viewers(self) -> list[Any]:
        return list(self._sent_to)

    # test helper, not part of the real API: simulate a click without the real packet pipeline.
    def click(self, player, slot: int) -> MenuTransactionResult:
        item = self._inventory.get_item(slot)
        tr = MenuTransaction(player=player, slot=slot, item_clicked=item)
        result = self._listener(tr)
        if result.should_continue:
            pass  # a real click would now move the item; our tests only check the returned decision
        return result
