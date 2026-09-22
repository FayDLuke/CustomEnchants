# CustomEnchants — EndstoneMC Port

**Official code:** https://github.com/DaPigGuy/PiggyCustomEnchants

## Commands

`/ce` (aliases: `/customenchants`, `/customenchant`):

| Subcommand | Purpose | Permission |
|---|---|---|
| `/ce about` | Show plugin version information | `piggycustomenchants.command.ce.about` |
| `/ce list` | List all enchants by category | `piggycustomenchants.command.ce.list` |
| `/ce info <enchant>` | Show details for one enchant | `piggycustomenchants.command.ce.list` |
| `/ce enchant <enchant> [level] [player]` | Apply an enchant to the item in hand | `piggycustomenchants.command.ce.enchant` (default: op) |
| `/ce remove <enchant> [player]` | Remove an enchant from the item in hand | `piggycustomenchants.command.ce.remove` (default: op) |
| `/ce nbt` | Display the NBT of the item in hand (debug) | `piggycustomenchants.command.ce.nbt` (default: op) |

Set `forms.enabled = true` in `config.toml` to use a GUI form like the original version.


## Fidelity Matrix

**Full** — behavior is identical to the original version (using Endstone APIs directly, without
emulation):

Anti Knockback, Armored, Attacker Deterrent (Cursed/Drunk/Frozen/Hardened/Poisoned/Revulsion),
Berserker, Blessed, Cactus, Chicken, Cloaking, Conditional Multiplier (Aerial/Backstab/Charge),
Deathbringer, Deep Wounds, Disarming, Disarmor, Driller, Endershift, Energizing, Enlighted,
Explosive, Farmer, Fertilizer, Gooey, Harvest, Headhunter, Healing, Heavy, Implants, Jackpot,
Laced Weapon (Blind/Cripple/Poison/Wither), Lifesteal, Lightning, Lucky Charm, Lumberjack,
Meditation, Molten, Overload, Parachute, Piercing, Poisonous Cloud, Quickening, Revive,
Self Destruct, Shielded, Shuffle, Smelting, Soulbound, Stomp, Tank, Telepathy, Toggleable Effect
(Enraged/Gears/Glowing/Haste/Obsidian Shield/Oxygenate/Springs), Vampire.

**Emulated** — the final behavior is as close as possible, but replacement techniques are used
because Endstone does not have equivalent events or setters. The details are documented in
comments in the relevant source files:

| Enchant | Replacement technique |
|---|---|
| Blaze, Wither Skull, Porkified, Homing | Projectiles are simulated directly (position and velocity are integrated each tick and collisions are checked manually), rather than using native Minecraft projectile entities with the `onHitEntity` hook |
| Bombardment, Missile | Native TNT is spawned and then detonated through a custom explosion engine (a PocketMine-style block ray cast) |
| Volley | Additional arrows are simulated rather than represented as native arrow entities |
| Grappling | Pulling is simulated through incremental teleportation because Endstone has no velocity setter |
| Forcefield | Entities are pushed through teleportation; incoming projectiles are **destroyed** rather than redirected |
| Jetpack, Auto Aim | Flight and incoming-shot movement are simulated through per-tick teleportation |
| Radar | A compass is used, but its target location is sent through a raw `SetSpawnPosition` packet — **risky**, see the warning above |
| Hallucination | A block illusion is sent to one client through a raw `UpdateBlock` packet |
| Antitoxin, Focused | There is no "effect added" event; poison and nausea effects are removed every few ticks after they appear |
| Magma Walker | Lava detection and obsidian creation are handled manually, without a targeted `BlockUpdateEvent` |
| Molotov | Fire areas are placed and removed automatically rather than using burning `FallingBlock` entities |
| Prowl | Since Endstone has no `hidePlayer`/`showPlayer`, only invisibility and slowness are used; other players can still see a transparent outline instead of the player disappearing completely |
| Spider | Since `setCanClimbWalls` is unavailable, jumps into walls are detected and the player is "stuck" to the wall by teleporting upward for several seconds |

**Unsupported** — disabled by default (`enable-unsupported = false` in the config) because
Endstone 0.11 has no API for changing entity sizes:

- **Grow** and **Shrink** (require `Actor.setScale()`, for which no equivalent endpoint exists)

The enchants remain registered and can be applied with `/ce enchant --override`, but they do
nothing until Endstone adds the required API.

**Intentionally not ported** (not gameplay mechanics; PocketMine-specific):

- The `isCoolKid()` anti-tamper system and remote disable through the original author's Gist.
- The update checker.
- The dependency on PocketMine's virion library.

## Additional settings for this port

The `[endstone]` section in `config.toml` contains settings that do not exist in the original
version and are required because of architectural differences:

- `inventory-scan-interval` — how often (in ticks) the entire inventory is rescanned for new
  enchants; armor and the held item are always checked every tick.
- `emulate-ignite` — Endstone cannot call `setOnFire()`, so enchants such as Molten briefly
  place a fire block at the target's feet. This can be disabled.
- `explosion-max-size` / `explosion-max-blocks` — limits for custom explosion size (Explosive,
  TNT) and the number of blocks it may remove, preventing server lag at very high enchant levels.
- `debug` — when `true`, all failed operations (failed vanilla commands, missing actors, etc.)
  are written to the server log.

## Project structure

```
src/endstone_piggy_custom_enchants/
  plugin.py        # main Plugin class, lifecycle, command/effect/damage utilities
  engine.py         # player equipment scanning, reaction dispatch, tick, toggle
  manager.py        # enchant registry, compatibility, applying/removing enchants from items
  storage.py        # reading/writing enchant data in item NBT (the "PiggyCE" tag)
  compat.py         # bridge to vanilla commands (/effect, /damage, /setblock)
  projectiles.py    # custom arrow detection and custom projectile simulation
  motion.py         # teleport-based movement (Jetpack, Grappling, etc.)
  explosion.py      # PiggyExplosion engine (ray cast + damage + drops)
  enchants/         # each enchant implementation, grouped like the original structure
tests/
  test_core_logic.py  # unit tests (see the testing status section)
  fake_pkg/endstone/  # minimal Endstone API mock used only for unit tests
```

## License

As with the original project: Apache License 2.0 (see `LICENSE`). Original copyright 2017
DaPigGuy.
