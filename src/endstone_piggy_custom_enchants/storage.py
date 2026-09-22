from __future__ import annotations

import uuid
from typing import Any

from endstone.inventory import ItemStack
from endstone.nbt import CompoundTag, IntTag, ListTag, StringTag

TAG = "PiggyCE"
LORE_TAG = "PiggyCELore"
VERSION_TAG = "PiggyCEItemVersion"
BOOK_UUID_TAG = "PiggyCEBookUUID"
ITEM_VERSION = 1


def _dict(item: ItemStack | None) -> dict[str, Any]:
    if item is None:
        return {}
    try:
        return item.nbt.to_dict()
    except Exception:
        return {}


def read_enchants(item: ItemStack | None) -> dict[str, int]:
    raw = _dict(item).get(TAG)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        try:
            level = int(value)
        except (TypeError, ValueError):
            continue
        if level > 0:
            out[str(key)] = level
    return out


def has_enchants(item: ItemStack | None) -> bool:
    return bool(read_enchants(item))


def _pop(tag: Any, key: str) -> None:
    if key in tag:
        tag.pop(key)


def write_enchants(item: ItemStack, enchants: dict[str, int], lines: list[str]) -> None:
    """Store enchants on the item (in place) and refresh the managed lore lines."""
    nbt = item.nbt
    data = nbt.to_dict()
    old_lines = [str(x) for x in data.get(LORE_TAG, [])] if isinstance(data.get(LORE_TAG), list) else []

    _pop(nbt, TAG)
    _pop(nbt, LORE_TAG)
    if enchants:
        comp = CompoundTag()
        for key, level in enchants.items():
            comp[key] = IntTag(int(level))
        nbt[TAG] = comp
        managed = ListTag()
        for line in lines:
            managed.append(StringTag(line))
        nbt[LORE_TAG] = managed
        if VERSION_TAG not in nbt:
            nbt[VERSION_TAG] = IntTag(ITEM_VERSION)
    else:
        _pop(nbt, VERSION_TAG)

    display = data.get("display")
    current = [str(x) for x in display.get("Lore", [])] if isinstance(display, dict) else []
    for old in old_lines:
        if old in current:
            current.remove(old)
    new_lore = (list(lines) if enchants else []) + current

    if new_lore:
        disp = nbt["display"] if "display" in nbt else CompoundTag()
        lore_tag = ListTag()
        for line in new_lore:
            lore_tag.append(StringTag(line))
        disp["Lore"] = lore_tag
        nbt["display"] = disp
    elif "display" in nbt:
        disp = nbt["display"]
        _pop(disp, "Lore")
        if len(disp) == 0:
            nbt.pop("display")
        else:
            nbt["display"] = disp

    item.nbt = nbt if len(nbt) > 0 else CompoundTag()


def ensure_book_uuid(item: ItemStack) -> None:
    nbt = item.nbt
    nbt[BOOK_UUID_TAG] = StringTag(str(uuid.uuid4()))
    item.nbt = nbt


def nbt_text(item: ItemStack | None) -> str:
    if item is None:
        return "{}"
    try:
        return str(item.nbt)
    except Exception:
        return "{}"
