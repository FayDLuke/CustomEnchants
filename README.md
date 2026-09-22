# CustomEnchants — EndstoneMC Port

**Official code:** https://github.com/DaPigGuy/PiggyCustomEnchants

## Commands

`/ce` (aliases: `/customenchants`, `/customenchant`

| Subcommand | Purpose | Permission |
|---|---|---|
| `/ce about` | Show plugin version information | `piggycustomenchants.command.ce.about` |
| `/ce list` | List all enchants by category | `piggycustomenchants.command.ce.list` |
| `/ce info <enchant>` | Show details for one enchant | `piggycustomenchants.command.ce.list` |
| `/ce enchant <enchant> [level] [player]` | Apply an enchant to the item in hand | `piggycustomenchants.command.ce.enchant` (default: op) |
| `/ce remove <enchant> [player]` | Remove an enchant from the item in hand | `piggycustomenchants.command.ce.remove` (default: op) |
| `/ce nbt` | Display the NBT of the item in hand (debug) | `piggycustomenchants.command.ce.nbt` (default: op) |

Set `forms.enabled = true` in `config.toml` to use a GUI form like the original version.


## Additional settings

The `[endstone]` section in `config.toml` contains settings that do not exist in the original
version and are required because of architectural differences:

- `inventory-scan-interval` how often (in ticks) the entire inventory is rescanned for new
  enchants; armor and the held item are always checked every tick.
- `emulate-ignite` Endstone cannot call `setOnFire()`, so enchants such as Molten briefly
  place a fire block at the target's feet. This can be disabled.
- `explosion-max-size` / `explosion-max-blocks` limits for custom explosion size (Explosive,
  TNT) and the number of blocks it may remove, preventing server lag at very high enchant levels.
- `debug` when `true`, all failed operations (failed vanilla commands, missing actors, etc.)
  are written to the server log.

## License

As with the original project: Apache License 2.0 (see `LICENSE`). Original copyright 2017
DaPigGuy.
