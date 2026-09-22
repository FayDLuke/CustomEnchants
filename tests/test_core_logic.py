"""Pure-logic unit tests, run with `python3 -m unittest` from this directory.

These do NOT talk to a real Bedrock server: `fake_pkg/endstone` is a minimal stand-in just so the plugin
package imports cleanly and its non-server logic (NBT storage, enchant registry, per-slot bookkeeping in
Engine) can be exercised. They do not prove the mod behaves correctly in-game.
"""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "fake_pkg"))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from endstone.inventory import ItemStack, PlayerInventory  # noqa: E402
from endstone import Player  # noqa: E402

from endstone_piggy_custom_enchants import storage  # noqa: E402
from endstone_piggy_custom_enchants.util import roman, normalize_name  # noqa: E402
from endstone_piggy_custom_enchants.items import is_sword, is_bow, item_matches_kind  # noqa: E402
from endstone_piggy_custom_enchants.constants import Kind  # noqa: E402


class FakePlugin:
    """Just enough of PiggyCustomEnchants for EnchantData / CustomEnchantManager / Engine to run."""

    def __init__(self, tmp_dir):
        import types
        from endstone_piggy_custom_enchants.enchant import EnchantData
        from endstone_piggy_custom_enchants.manager import CustomEnchantManager

        self.tick_count = 0
        self.disabled_enchants = set()
        self.rarity_colors = {"common": "yellow", "uncommon": "blue", "rare": "gold", "mythic": "light_purple"}
        self._cfg = {}
        self.logger = types.SimpleNamespace(info=lambda *a: None, warning=lambda *a: None, error=lambda *a: None)
        self.enchant_data = EnchantData(tmp_dir)
        self.manager = CustomEnchantManager(self)
        self.manager.register_all()
        self.enchant_data.flush()

    def cfg(self, key, default=None):
        return self._cfg.get(key, default)

    def is_disabled_in_world(self, key, player):
        return False

    def debug(self, *a):
        pass


class StorageTests(unittest.TestCase):
    def test_roundtrip(self):
        item = ItemStack("minecraft:diamond_sword")
        item.nbt["Unrelated"] = __import__("endstone.nbt", fromlist=["IntTag"]).IntTag(5)
        storage.write_enchants(item, {"sharpness_x": 3}, ["§7Sharpness X 3"])
        self.assertEqual(storage.read_enchants(item), {"sharpness_x": 3})
        self.assertIn("Unrelated", item.nbt.to_dict())
        self.assertEqual(item.nbt.to_dict()["display"]["Lore"], ["§7Sharpness X 3"])

    def test_clear(self):
        item = ItemStack("minecraft:diamond_sword")
        storage.write_enchants(item, {"lifesteal": 1}, ["§eLifesteal 1"])
        storage.write_enchants(item, {}, [])
        self.assertEqual(storage.read_enchants(item), {})
        self.assertNotIn("display", item.nbt.to_dict())

    def test_preserves_existing_lore(self):
        item = ItemStack("minecraft:diamond_sword")
        from endstone.nbt import CompoundTag, ListTag, StringTag

        disp = CompoundTag()
        lore = ListTag()
        lore.append(StringTag("A custom lore line"))
        disp["Lore"] = lore
        item.nbt["display"] = disp
        storage.write_enchants(item, {"lifesteal": 2}, ["§eLifesteal II"])
        final_lore = item.nbt.to_dict()["display"]["Lore"]
        self.assertIn("A custom lore line", final_lore)
        self.assertIn("§eLifesteal II", final_lore)


class UtilTests(unittest.TestCase):
    def test_roman(self):
        self.assertEqual(roman(1), "I")
        self.assertEqual(roman(4), "IV")
        self.assertEqual(roman(9), "IX")
        self.assertEqual(roman(58), "LVIII")

    def test_normalize(self):
        self.assertEqual(normalize_name("Anti Knockback"), "antiknockback")
        self.assertEqual(normalize_name("Wither Skull"), "witherskull")


class ItemKindTests(unittest.TestCase):
    def test_sword_bow(self):
        self.assertTrue(is_sword(ItemStack("minecraft:diamond_sword")))
        self.assertFalse(is_sword(ItemStack("minecraft:bow")))
        self.assertTrue(is_bow(ItemStack("minecraft:bow")))

    def test_matches_kind(self):
        self.assertTrue(item_matches_kind(ItemStack("minecraft:diamond_sword"), Kind.WEAPON))
        self.assertTrue(item_matches_kind(ItemStack("minecraft:bow"), Kind.WEAPON))
        self.assertFalse(item_matches_kind(ItemStack("minecraft:diamond_pickaxe"), Kind.WEAPON))
        self.assertTrue(item_matches_kind(ItemStack("minecraft:enchanted_book"), Kind.WEAPON))


class ManagerTests(unittest.TestCase):
    def setUp(self):
        import pathlib
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.plugin = FakePlugin(self.tmp)

    def test_registered_all_ids(self):
        from endstone_piggy_custom_enchants.constants import ENCHANT_IDS

        self.assertEqual(len(self.plugin.manager.all()), len(ENCHANT_IDS))
        for name in ENCHANT_IDS:
            self.assertIsNotNone(self.plugin.manager.get(name), f"{name} not registered")

    def test_incompatibility(self):
        item = ItemStack("minecraft:bow")
        blaze = self.plugin.manager.get("blaze")
        porkified = self.plugin.manager.get("porkified")
        self.plugin.manager.add_enchant(item, blaze, 1)
        self.assertFalse(self.plugin.manager.can_apply(item, porkified))

    def test_add_enchant_writes_lore(self):
        item = ItemStack("minecraft:diamond_sword")
        lifesteal = self.plugin.manager.get("lifesteal")
        self.assertTrue(self.plugin.manager.add_enchant(item, lifesteal, 2))
        self.assertEqual(self.plugin.manager.level_on(item, lifesteal), 2)
        lore = item.nbt.to_dict()["display"]["Lore"]
        self.assertEqual(len(lore), 1)
        self.assertIn("Lifesteal", lore[0])

    def test_popup_text_none_without_enchants(self):
        item = ItemStack("minecraft:diamond_sword")
        self.assertIsNone(self.plugin.manager.popup_text(item))

    def test_popup_text_includes_name_and_enchant(self):
        item = ItemStack("minecraft:diamond_pickaxe")
        driller = self.plugin.manager.get("driller")
        self.plugin.manager.add_enchant(item, driller, 1)
        text = self.plugin.manager.popup_text(item)
        self.assertIsNotNone(text)
        self.assertIn("Diamond Pickaxe", text)
        self.assertIn("Driller", text)


class EngineTests(unittest.TestCase):
    def setUp(self):
        import pathlib
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.plugin = FakePlugin(self.tmp)
        from endstone_piggy_custom_enchants.engine import Engine

        self.plugin.engine = Engine(self.plugin)

    def make_player(self):
        p = Player("Alex")
        p.inventory = PlayerInventory(4)
        return p

    def test_gather_hand_only_enchant_on_held_slot(self):
        player = self.make_player()
        sword = ItemStack("minecraft:diamond_sword")
        lifesteal = self.plugin.manager.get("lifesteal")  # Usage.HAND
        self.plugin.manager.add_enchant(sword, lifesteal, 1)
        player.inventory.set_item(0, sword)
        player.inventory.held_item_slot = 0
        entries = self.plugin.engine.gather(player, full=True)
        self.assertTrue(any(e.enchant is lifesteal for e in entries))

        player.inventory.held_item_slot = 1
        entries = self.plugin.engine.gather(player, full=True)
        self.assertFalse(any(e.enchant is lifesteal for e in entries))

    def test_gather_armor_slot(self):
        player = self.make_player()
        boots = ItemStack("minecraft:iron_boots")
        gears = self.plugin.manager.get("gears")  # Usage.BOOTS
        self.plugin.manager.add_enchant(boots, gears, 1)
        player.inventory.boots = boots
        entries = self.plugin.engine.gather(player, full=True)
        self.assertTrue(any(e.enchant is gears for e in entries))

    def test_toggle_reconciliation(self):
        player = self.make_player()
        boots = ItemStack("minecraft:iron_boots")
        gears = self.plugin.manager.get("gears")
        self.plugin.manager.add_enchant(boots, gears, 1)
        player.inventory.boots = boots

        calls = []
        gears.toggle = lambda p, item, slot, level, toggle: calls.append(toggle)

        self.plugin.engine.reconcile_toggles(player, self.plugin.engine.state(player))
        self.assertEqual(calls, [True])

        player.inventory.boots = None
        self.plugin.engine.reconcile_toggles(player, self.plugin.engine.state(player))
        self.assertEqual(calls, [True, False])


if __name__ == "__main__":
    unittest.main()
