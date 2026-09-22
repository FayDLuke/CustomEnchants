from __future__ import annotations

from enum import Enum, IntEnum


class Usage(IntEnum):
    HAND = 0
    ANY_INVENTORY = 1
    INVENTORY = 2
    ARMOR_INVENTORY = 3
    HELMET = 4
    CHESTPLATE = 5
    LEGGINGS = 6
    BOOTS = 7


class Kind(IntEnum):
    GLOBAL = 0
    DAMAGEABLE = 1
    WEAPON = 2
    SWORD = 3
    BOW = 4
    TOOLS = 5
    PICKAXE = 6
    AXE = 7
    SHOVEL = 8
    HOE = 9
    ARMOR = 10
    HELMET = 11
    CHESTPLATE = 12
    LEGGINGS = 13
    BOOTS = 14
    COMPASS = 15


class Trigger(Enum):
    DAMAGE = "damage"
    DAMAGE_BY_ENTITY = "damage_by_entity"
    DAMAGE_BY_CHILD = "damage_by_child"
    KNOCKBACK = "knockback"
    BLOCK_BREAK = "block_break"
    INTERACT = "interact"
    MOVE = "move"
    SNEAK = "sneak"
    DEATH = "death"
    SHOOT_BOW = "shoot_bow"
    PROJECTILE_HIT_BLOCK = "projectile_hit_block"


TYPE_NAMES: dict[Kind, str] = {
    Kind.ARMOR: "Armor",
    Kind.HELMET: "Helmet",
    Kind.CHESTPLATE: "Chestplate",
    Kind.LEGGINGS: "Leggings",
    Kind.BOOTS: "Boots",
    Kind.WEAPON: "Weapon",
    Kind.SWORD: "Sword",
    Kind.BOW: "Bow",
    Kind.TOOLS: "Tools",
    Kind.PICKAXE: "Pickaxe",
    Kind.AXE: "Axe",
    Kind.SHOVEL: "Shovel",
    Kind.HOE: "Hoe",
    Kind.DAMAGEABLE: "Damageable",
    Kind.GLOBAL: "Global",
    Kind.COMPASS: "Compass",
}

RARITIES = ("common", "uncommon", "rare", "mythic")

ENCHANT_IDS: dict[str, int] = {
    "autorepair": 108, "soulbound": 118, "aerial": 114, "backstab": 122, "blessed": 120, "blind": 101,
    "charge": 113, "cripple": 109, "deathbringer": 102, "deepwounds": 112, "disarming": 117, "disarmor": 121,
    "gooey": 103, "hallucination": 119, "lifesteal": 100, "lightning": 123, "luckycharm": 124, "poison": 104,
    "vampire": 111, "wither": 115, "autoaim": 306, "blaze": 311, "bombardment": 300, "bountyhunter": 309,
    "grappling": 313, "headhunter": 312, "healing": 310, "homing": 316, "missile": 315, "molotov": 304,
    "paralyze": 303, "piercing": 307, "porkified": 314, "shuffle": 308, "volley": 305, "witherskull": 301,
    "driller": 206, "energizing": 202, "explosive": 200, "haste": 207, "jackpot": 212, "oxygenate": 211,
    "quickening": 203, "smelting": 201, "telepathy": 205, "lumberjack": 204, "farmer": 209, "fertilizer": 208,
    "harvest": 210, "molten": 400, "enlighted": 401, "hardened": 402, "poisoned": 403, "frozen": 404,
    "obsidianshield": 405, "revulsion": 406, "selfdestruct": 407, "cursed": 408, "endershift": 409,
    "drunk": 410, "berserker": 411, "cloaking": 412, "revive": 413, "shrink": 414, "grow": 415,
    "cactus": 416, "antiknockback": 417, "forcefield": 418, "overload": 419, "armored": 420, "tank": 421,
    "heavy": 422, "shielded": 423, "poisonouscloud": 424, "antitoxin": 604, "focused": 603, "glowing": 601,
    "implants": 600, "meditation": 602, "chicken": 801, "enraged": 804, "parachute": 800, "prowl": 802,
    "spider": 803, "vacuum": 805, "gears": 500, "jetpack": 503, "magmawalker": 504, "springs": 501,
    "stomp": 502, "radar": 700,
}

INCOMPATIBLE_ENCHANTS: dict[str, tuple[str, ...]] = {
    "blaze": ("porkified", "witherskull"),
    "grappling": ("volley",),
    "grow": ("shrink",),
    "homing": ("blaze", "porkified", "witherskull"),
    "porkified": ("witherskull",),
}

COLOR_CODES: dict[str, str] = {
    "black": "§0", "dark_blue": "§1", "dark_green": "§2", "dark_aqua": "§3", "dark_red": "§4",
    "dark_purple": "§5", "gold": "§6", "gray": "§7", "dark_gray": "§8", "blue": "§9", "green": "§a",
    "aqua": "§b", "red": "§c", "light_purple": "§d", "yellow": "§e", "white": "§f",
}

DEFAULT_RARITY_COLORS = {"common": "yellow", "uncommon": "blue", "rare": "gold", "mythic": "light_purple"}

# Effects PocketMine flags as "bad" (Effect::isBad).
BAD_EFFECTS = (
    "slowness", "mining_fatigue", "instant_damage", "nausea", "blindness", "hunger", "weakness", "poison",
    "wither", "levitation", "fatal_poison", "darkness", "bad_omen",
)

INFINITE_TICKS = 2147483647
INFINITE_SECONDS = 1000000

# Blocks a projectile / motion emulation can pass through.
PASSABLE_BLOCKS = frozenset(
    "minecraft:" + n
    for n in (
        "air", "cave_air", "void_air", "water", "flowing_water", "lava", "flowing_lava", "short_grass",
        "tallgrass", "tall_grass", "fern", "large_fern", "deadbush", "fire", "soul_fire", "vine",
        "torch", "soul_torch", "redstone_torch", "snow_layer", "double_plant", "yellow_flower",
        "red_flower", "light_block", "structure_void", "web_placeholder", "sapling", "wheat", "carrots",
        "potatoes", "beetroot", "sugar_cane", "reeds", "glow_lichen", "hanging_roots", "seagrass",
        "kelp", "dandelion", "poppy", "sweet_berry_bush", "wall_sign", "standing_sign", "rail",
        "golden_rail", "detector_rail", "activator_rail", "lever", "stone_button", "wooden_button",
    )
)

# Never broken by the multi-block enchants (setblock ... destroy would happily delete them).
UNBREAKABLE_BLOCKS = frozenset(
    "minecraft:" + n
    for n in (
        "bedrock", "barrier", "end_portal_frame", "end_portal", "end_gateway", "portal", "command_block",
        "chain_command_block", "repeating_command_block", "structure_block", "structure_void", "jigsaw",
        "light_block", "reinforced_deepslate", "allow", "deny", "border_block", "moving_block",
        "unknown", "water", "flowing_water", "lava", "flowing_lava", "air", "cave_air", "void_air",
    )
)

# Rough blast resistance used by the explosion emulation (default is 3.0).
BLAST_RESISTANCE = {
    "minecraft:bedrock": 3600000.0, "minecraft:barrier": 3600000.0, "minecraft:obsidian": 1200.0,
    "minecraft:crying_obsidian": 1200.0, "minecraft:respawn_anchor": 1200.0,
    "minecraft:reinforced_deepslate": 3600000.0, "minecraft:ancient_debris": 1200.0,
    "minecraft:netherite_block": 1200.0, "minecraft:enchanting_table": 1200.0,
    "minecraft:ender_chest": 600.0, "minecraft:anvil": 1200.0, "minecraft:water": 100.0,
    "minecraft:flowing_water": 100.0, "minecraft:lava": 100.0, "minecraft:flowing_lava": 100.0,
    "minecraft:end_portal_frame": 3600000.0, "minecraft:command_block": 3600000.0,
    "minecraft:dirt": 0.5, "minecraft:grass_block": 0.6, "minecraft:sand": 0.5, "minecraft:gravel": 0.6,
    "minecraft:glass": 0.3, "minecraft:leaves": 0.2, "minecraft:tnt": 0.0, "minecraft:air": 0.0,
}

# Vanilla furnace results for the common Smelting drops.
SMELTING_RESULTS = {
    "minecraft:raw_iron": "minecraft:iron_ingot", "minecraft:raw_gold": "minecraft:gold_ingot",
    "minecraft:raw_copper": "minecraft:copper_ingot", "minecraft:iron_ore": "minecraft:iron_ingot",
    "minecraft:gold_ore": "minecraft:gold_ingot", "minecraft:copper_ore": "minecraft:copper_ingot",
    "minecraft:deepslate_iron_ore": "minecraft:iron_ingot",
    "minecraft:deepslate_gold_ore": "minecraft:gold_ingot",
    "minecraft:deepslate_copper_ore": "minecraft:copper_ingot",
    "minecraft:ancient_debris": "minecraft:netherite_scrap", "minecraft:cobblestone": "minecraft:stone",
    "minecraft:cobbled_deepslate": "minecraft:deepslate", "minecraft:sand": "minecraft:glass",
    "minecraft:red_sand": "minecraft:glass", "minecraft:clay_ball": "minecraft:brick",
    "minecraft:netherrack": "minecraft:netherbrick", "minecraft:cactus": "minecraft:green_dye",
    "minecraft:kelp": "minecraft:dried_kelp", "minecraft:wet_sponge": "minecraft:sponge",
    "minecraft:stone_bricks": "minecraft:cracked_stone_bricks", "minecraft:potato": "minecraft:baked_potato",
    "minecraft:beef": "minecraft:cooked_beef", "minecraft:porkchop": "minecraft:cooked_porkchop",
    "minecraft:chicken": "minecraft:cooked_chicken", "minecraft:mutton": "minecraft:cooked_mutton",
    "minecraft:rabbit": "minecraft:cooked_rabbit", "minecraft:cod": "minecraft:cooked_cod",
    "minecraft:salmon": "minecraft:cooked_salmon", "minecraft:chorus_fruit": "minecraft:popped_chorus_fruit",
    "minecraft:oak_log": "minecraft:charcoal", "minecraft:spruce_log": "minecraft:charcoal",
    "minecraft:birch_log": "minecraft:charcoal", "minecraft:jungle_log": "minecraft:charcoal",
    "minecraft:acacia_log": "minecraft:charcoal", "minecraft:dark_oak_log": "minecraft:charcoal",
    "minecraft:mangrove_log": "minecraft:charcoal", "minecraft:cherry_log": "minecraft:charcoal",
}

# Jackpot: (surface ore id, deepslate variant id) pairs, indexed the same as ORE_DROPS below.
ORE_TIERS = (
    ("minecraft:coal_ore", "minecraft:deepslate_coal_ore"),
    ("minecraft:iron_ore", "minecraft:deepslate_iron_ore"),
    ("minecraft:gold_ore", "minecraft:deepslate_gold_ore"),
    ("minecraft:diamond_ore", "minecraft:deepslate_diamond_ore"),
    ("minecraft:emerald_ore", "minecraft:deepslate_emerald_ore"),
)
ORE_DROPS = ("minecraft:coal", "minecraft:raw_iron", "minecraft:raw_gold", "minecraft:diamond", "minecraft:emerald")

CROP_BLOCKS = {
    "minecraft:wheat": "minecraft:wheat_seeds",
    "minecraft:carrots": "minecraft:carrot",
    "minecraft:potatoes": "minecraft:potato",
    "minecraft:beetroot": "minecraft:beetroot_seeds",
}

PROJECTILE_TYPES = frozenset(
    "minecraft:" + n
    for n in (
        "arrow", "fireball", "small_fireball", "wither_skull", "wither_skull_dangerous", "snowball", "egg",
        "ender_pearl", "thrown_trident", "xp_bottle", "splash_potion", "lingering_potion", "fishing_hook",
        "llama_spit", "shulker_bullet", "dragon_fireball", "wind_charge_projectile", "breeze_wind_charge_projectile",
    )
)
