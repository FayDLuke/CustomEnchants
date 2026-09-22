from __future__ import annotations

from endstone.nbt import CompoundTag


class ItemType:
    def __init__(self, id_):
        self.id = id_
        self.max_durability = 0 if not id_.endswith(("_sword", "_pickaxe", "_axe", "_shovel", "_hoe",
                                                      "_helmet", "_chestplate", "_leggings", "_boots")) else 250


class ItemMeta:
    def __init__(self):
        self.display_name = None
        self.lore = []


class ItemStack:
    def __init__(self, type_id="minecraft:air", amount=1):
        self.type = ItemType(type_id)
        self.amount = amount
        self._nbt = CompoundTag()
        self._meta = ItemMeta()

    @property
    def nbt(self):
        return self._nbt

    @nbt.setter
    def nbt(self, value):
        self._nbt = value if value is not None else CompoundTag()

    @property
    def item_meta(self):
        return self._meta

    def set_item_meta(self, meta):
        self._meta = meta

    def clone(self):
        clone = ItemStack(self.type.id, self.amount)
        clone._nbt = CompoundTag(dict(self._nbt._data))
        return clone


class PlayerInventory:
    def __init__(self, size=36):
        self.size = size
        self._slots = [None] * size
        self.held_item_slot = 0
        self.helmet = None
        self.chestplate = None
        self.leggings = None
        self.boots = None
        self.item_in_off_hand = None

    @property
    def contents(self):
        return list(self._slots)

    def get_item(self, index):
        return self._slots[index]

    def set_item(self, index, item):
        self._slots[index] = item

    @property
    def item_in_main_hand(self):
        return self._slots[self.held_item_slot]

    def contains(self, item):
        return any(s is not None and s.type.id == item.type.id for s in self._slots)

    def add_item(self, item):
        for i, s in enumerate(self._slots):
            if s is None:
                self._slots[i] = item
                return {}
        return {0: item}

    def remove_item(self, item):
        for i, s in enumerate(self._slots):
            if s is not None and s.type.id == item.type.id:
                self._slots[i] = None
                return
