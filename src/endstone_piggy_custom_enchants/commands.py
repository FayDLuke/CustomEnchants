from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from endstone import Player
from endstone.form import ActionForm, Button, ModalForm, TextInput
from endstone.inventory import ItemStack

from . import storage
from .constants import RARITIES, TYPE_NAMES, Kind
from .items import is_air, item_matches_kind

if TYPE_CHECKING:
    from .plugin import PiggyCustomEnchants

PERM = "piggycustomenchants.command.ce"


class CommandHandler:
    def __init__(self, plugin: "PiggyCustomEnchants") -> None:
        self.plugin = plugin

    # routing
    def run(self, sender: Any, args: list[str]) -> bool:
        sub = args[0].lower() if args else ""
        rest = args[1:]
        handlers = {
            "about": self.about, "list": self.list_cmd, "info": self.info, "enchant": self.enchant,
            "remove": self.remove, "nbt": self.nbt,
        }
        if sub in ("", "help"):
            if isinstance(sender, Player) and self.plugin.forms_enabled():
                self.main_form(sender)
            else:
                sender.send_message(self.usage(sender))
            return True
        handler = handlers.get(sub)
        if handler is None:
            sender.send_error_message(f"Unknown subcommand '{sub}'.")
            sender.send_message(self.usage(sender))
            return True
        if not sender.has_permission(f"{PERM}.{'list' if sub == 'info' else sub}"):
            sender.send_error_message("You do not have permission to use this subcommand.")
            return True
        handler(sender, rest)
        return True

    def usage(self, sender: Any) -> str:
        lines = ["§aPiggyCustomEnchants", "§7/ce about", "§7/ce list", "§7/ce info <enchantment>"]
        if sender.has_permission(f"{PERM}.enchant"):
            lines.append("§7/ce enchant <enchantment> [level] [player]")
        if sender.has_permission(f"{PERM}.remove"):
            lines.append("§7/ce remove <enchantment> [player]")
        if sender.has_permission(f"{PERM}.nbt"):
            lines.append("§7/ce nbt")
        return "\n".join(lines)

    # helpers
    def find_player(self, sender: Any, name: str | None) -> Player | None:
        if not name:
            return sender if isinstance(sender, Player) else None
        if name.startswith("@s"):
            return sender if isinstance(sender, Player) else None
        lowered = name.lower()
        matches = [p for p in self.plugin.server.online_players if p.name.lower().startswith(lowered)]
        exact = [p for p in matches if p.name.lower() == lowered]
        return (exact or matches or [None])[0]

    def describe(self, enchant: Any) -> str:
        extra = "" if enchant.unsupported_reason is None else f"\n§cUnsupported: {enchant.unsupported_reason}"
        return (
            f"§a{enchant.display_name}\n§rID: {enchant.id}\nDescription: {enchant.description}\n"
            f"Type: {TYPE_NAMES.get(enchant.item_kind, 'Unknown')}\nRarity: {enchant.rarity.capitalize()}\n"
            f"Max Level: {enchant.max_level}{extra}"
        )

    def by_type(self) -> dict[Kind, list[Any]]:
        out: dict[Kind, list[Any]] = {}
        for enchant in self.plugin.manager.all():
            out.setdefault(enchant.item_kind, []).append(enchant)
        for group in out.values():
            group.sort(key=lambda e: e.display_name)
        return out

    def list_text(self) -> str:
        groups = self.by_type()
        text = ""
        for kind, name in TYPE_NAMES.items():
            if kind in groups:
                names = ", ".join(
                    e.display_name + ("" if self.plugin.manager.is_enabled(e) else " §8(off)§r") for e in groups[kind]
                )
                text += f"\n§a§l{name}§r\n{names}"
        return text

    # subcommands
    def about(self, sender: Any, args: list[str]) -> None:
        message = (
            f"§aPiggyCustomEnchants version §6{self.plugin.version}\n"
            "§aA versatile custom enchantments plugin by DaPigGuy (MCPEPIG) and Aericio, ported to Endstone.\n"
            "More information: §6https://piggydocs.aericio.net/§a.\n"
            "§7Copyright 2017 DaPigGuy; Licensed under the Apache License."
        )
        if isinstance(sender, Player) and self.plugin.forms_enabled():
            self.simple_form(sender, "§aAbout PiggyCustomEnchants", message, "Back", lambda p: self.main_form(p))
            return
        sender.send_message(message)

    def list_cmd(self, sender: Any, args: list[str]) -> None:
        if isinstance(sender, Player) and self.plugin.forms_enabled():
            self.types_form(sender)
            return
        sender.send_message(self.list_text())

    def info(self, sender: Any, args: list[str]) -> None:
        name = " ".join(args)
        if not name:
            if isinstance(sender, Player) and self.plugin.forms_enabled():
                self.info_input_form(sender)
            else:
                sender.send_message("/ce info <enchantment>")
            return
        enchant = self.plugin.manager.get(name)
        if enchant is None:
            self.fail(sender, "Invalid enchantment.")
            return
        if isinstance(sender, Player) and self.plugin.forms_enabled():
            self.simple_form(sender, f"§a{enchant.display_name} Enchantment", self.describe(enchant), "Back",
                             lambda p: self.main_form(p))
            return
        sender.send_message(self.describe(enchant))

    def nbt(self, sender: Any, args: list[str]) -> None:
        if not isinstance(sender, Player):
            sender.send_error_message("Please use this in-game.")
            return
        sender.send_message(storage.nbt_text(sender.inventory.item_in_main_hand))

    def enchant(self, sender: Any, args: list[str], form_data: tuple[str, str, str] | None = None) -> None:
        if form_data is None and isinstance(sender, Player) and self.plugin.forms_enabled() and not args:
            self.enchant_form(sender)
            return
        if form_data is not None:
            enchant_name, level_text, player_name = form_data
        else:
            enchant_name = args[0] if args else ""
            level_text = args[1] if len(args) > 1 else "1"
            player_name = args[2] if len(args) > 2 else ""
        if not enchant_name or (not isinstance(sender, Player) and not player_name):
            sender.send_message("Usage: /ce enchant <enchantment> [level] [player]")
            return
        try:
            level = int(level_text or 1)
        except ValueError:
            self.fail(sender, "Enchantment level must be an integer")
            return
        target = self.find_player(sender, player_name)
        if target is None:
            self.fail(sender, "Invalid player.")
            return
        manager = self.plugin.manager
        enchant = manager.get(enchant_name)
        if enchant is None:
            self.fail(sender, "Invalid enchantment.")
            return
        inv = target.inventory
        item = inv.item_in_main_hand
        if is_air(item):
            self.fail(sender, "The target must hold an item.")
            return
        override = sender.has_permission("piggycustomenchants.overridecheck")
        if not override:
            if not manager.is_enabled(enchant):
                self.fail(sender, "This enchant is disabled" + (f": {enchant.unsupported_reason}" if enchant.unsupported_reason else "."))
                return
            if not item_matches_kind(item, enchant.item_kind):
                self.fail(sender, "The item is not compatible with this enchant.")
                return
            if level > enchant.max_level:
                self.fail(sender, f"The max level is {enchant.max_level}.")
                return
            existing = storage.read_enchants(item).get(enchant.key, 0)
            if existing > level:
                self.fail(sender, "The enchant has already been applied with a higher level on the item.")
                return
            if item.amount > 1:
                self.fail(sender, "You can only enchant one item at a time.")
                return
            if not manager.is_compatible(item, enchant):
                self.fail(sender, "This enchant is not compatible with another enchant.")
                return
        if item.type.id == "minecraft:book":
            book = ItemStack("minecraft:enchanted_book", item.amount)
            item = book
        if item.type.id in ("minecraft:enchanted_book", "minecraft:book"):
            storage.ensure_book_uuid(item)
        manager.add_enchant(item, enchant, level, check_compatibility=False)
        inv.set_item(inv.held_item_slot, item)
        self.plugin.engine.invalidate(target)
        sender.send_message("§aItem successfully enchanted.")

    def remove(self, sender: Any, args: list[str], form_data: tuple[str, str] | None = None) -> None:
        if form_data is None and isinstance(sender, Player) and self.plugin.forms_enabled() and not args:
            self.remove_form(sender)
            return
        enchant_name, player_name = form_data if form_data else (args[0] if args else "", args[1] if len(args) > 1 else "")
        if not enchant_name or (not isinstance(sender, Player) and not player_name):
            sender.send_message("Usage: /ce remove <enchantment> [player]")
            return
        target = self.find_player(sender, player_name)
        if target is None:
            self.fail(sender, "Invalid player.")
            return
        enchant = self.plugin.manager.get(enchant_name)
        if enchant is None:
            self.fail(sender, "Invalid enchantment.")
            return
        inv = target.inventory
        item = inv.item_in_main_hand
        if is_air(item) or storage.read_enchants(item).get(enchant.key, 0) == 0:
            self.fail(sender, "Item does not have specified enchantment.")
            return
        self.plugin.manager.remove_enchant(item, enchant)
        inv.set_item(inv.held_item_slot, item)
        self.plugin.engine.invalidate(target)
        sender.send_message("§aEnchantment successfully removed.")

    def fail(self, sender: Any, message: str) -> None:
        if isinstance(sender, Player) and self.plugin.forms_enabled():
            self.simple_form(sender, "§cError", f"§c{message}", "Back", lambda p: self.main_form(p))
        else:
            sender.send_message(f"§c{message}")

    # forms
    def simple_form(self, player: Player, title: str, content: str, button: str, on_back: Any) -> None:
        player.send_form(ActionForm(title=title, content=content, buttons=[Button(button, on_click=on_back)]))

    def main_form(self, player: Player) -> None:
        entries = [
            ("About", "about"), ("List", "list"), ("Info", "info"), ("Enchant", "enchant"), ("Remove", "remove"),
            ("NBT", "nbt"),
        ]
        buttons = []
        for label, sub in entries:
            perm = "list" if sub == "info" else sub
            if player.has_permission(f"{PERM}.{perm}"):
                buttons.append(Button(label, on_click=lambda p, s=sub: self.run(p, [s])))
        player.send_form(ActionForm(title="§aPiggyCustomEnchants", content="", buttons=buttons))

    def types_form(self, player: Player) -> None:
        groups = self.by_type()
        buttons = []
        for kind, name in TYPE_NAMES.items():
            if kind in groups:
                buttons.append(Button(name, on_click=lambda p, k=kind: self.enchants_form(p, k)))
        buttons.append(Button("Back", on_click=lambda p: self.main_form(p)))
        player.send_form(ActionForm(title="§aCustom Enchants List", content="", buttons=buttons))

    def enchants_form(self, player: Player, kind: Kind) -> None:
        buttons = [
            Button(e.display_name, on_click=lambda p, en=e: self.simple_form(
                p, f"§a{en.display_name} Enchantment", self.describe(en), "Back", lambda q: self.enchants_form(q, kind)))
            for e in self.by_type().get(kind, [])
        ]
        buttons.append(Button("Back", on_click=lambda p: self.types_form(p)))
        player.send_form(ActionForm(title=f"§a{TYPE_NAMES[kind]} Enchants", content="", buttons=buttons))

    def _modal(self, player: Player, title: str, controls: list[TextInput], on_values: Any) -> None:
        def submit(p: Player, data: str) -> None:
            try:
                values = [str(v) for v in json.loads(data)]
            except ValueError:
                return
            on_values(p, values)

        player.send_form(ModalForm(title=title, controls=controls, on_submit=submit))

    def info_input_form(self, player: Player) -> None:
        self._modal(player, "§aCustom Enchant Info", [TextInput("Enchantment")],
                    lambda p, v: self.info(p, [v[0]]) if v and v[0] else None)

    def enchant_form(self, player: Player) -> None:
        self._modal(player, "§aApply Custom Enchantment",
                    [TextInput("Enchantment"), TextInput("Level", "", "1"), TextInput("Player", "", player.name)],
                    lambda p, v: self.enchant(p, [], (v[0], v[1], v[2])))

    def remove_form(self, player: Player) -> None:
        self._modal(player, "§aRemove Custom Enchantment", [TextInput("Enchantment"), TextInput("Player", "", player.name)],
                    lambda p, v: self.remove(p, [], (v[0], v[1])))


_ = RARITIES  # re-exported for the docs / tests
