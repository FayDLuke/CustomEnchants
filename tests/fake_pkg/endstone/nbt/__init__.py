"""Fake NBT layer. Real Endstone NBT tags behave like a dict; we mimic the subset the plugin uses:
CompoundTag (get/set/pop/__contains__/__len__/to_dict), ListTag (append), IntTag/StringTag (scalar wrappers)."""
from __future__ import annotations


class Tag:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return repr(self.value)


class IntTag(Tag):
    pass


class StringTag(Tag):
    pass


class ListTag:
    def __init__(self):
        self._items = []

    def append(self, tag):
        self._items.append(tag)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def to_list(self):
        return [t.value if isinstance(t, Tag) else t for t in self._items]


class CompoundTag:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def pop(self, key, default=None):
        return self._data.pop(key, default)

    def to_dict(self):
        return {k: _unwrap(v) for k, v in self._data.items()}

    def __str__(self):
        return str(self.to_dict())


def _unwrap(value):
    if isinstance(value, Tag):
        return value.value
    if isinstance(value, ListTag):
        return value.to_list()
    if isinstance(value, CompoundTag):
        return value.to_dict()
    return value
