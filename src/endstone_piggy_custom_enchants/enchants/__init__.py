from __future__ import annotations

from typing import TYPE_CHECKING

from ..constants import ENCHANT_IDS, Kind, Usage
from ..enchant import CustomEnchant
from ..util import direction_of, normalize_name
from .armor import (AntiKnockbackEnchant, ArmoredEnchant, BerserkerEnchant, CactusEnchant, CloakingEnchant,
                    EndershiftEnchant, EnlightedEnchant, ForcefieldEnchant, GrowEnchant, HeavyEnchant, MoltenEnchant,
                    OverloadEnchant, PoisonousCloudEnchant, ReviveEnchant, SelfDestructEnchant, ShieldedEnchant,
                    ShrinkEnchant, TankEnchant)
from .base import (AttackerDeterrentEnchant, ConditionalDamageMultiplierEnchant, LacedWeaponEnchant,
                   ToggleableEffectEnchant)
from .boots import JetpackEnchant, MagmaWalkerEnchant, StompEnchant
from .bows import (AutoAimEnchant, BombardmentEnchant, BountyHunterEnchant, GrapplingEnchant, HeadhunterEnchant,
                   HealingEnchant, MissileEnchant, MolotovEnchant, ParalyzeEnchant, PiercingEnchant,
                   ProjectileChangingEnchant, ShuffleEnchant, VolleyEnchant)
from .chestplate import ChickenEnchant, ParachuteEnchant, ProwlEnchant, SpiderEnchant, VacuumEnchant
from .helmet import AntitoxinEnchant, FocusedEnchant, ImplantsEnchant, MeditationEnchant
from .misc import AutoRepairEnchant, LuckyCharmEnchant, RadarEnchant, SoulboundEnchant
from .tools import (DrillerEnchant, EnergizingEnchant, ExplosiveEnchant, FarmerEnchant, FertilizerEnchant,
                    HarvestEnchant, JackpotEnchant, LumberjackEnchant, QuickeningEnchant, SmeltingEnchant,
                    TelepathyEnchant)
from .weapons import (BlessedEnchant, DeathbringerEnchant, DeepWoundsEnchant, DisarmingEnchant, DisarmorEnchant,
                      GooeyEnchant, HallucinationEnchant, LifestealEnchant, LightningEnchant, VampireEnchant)

if TYPE_CHECKING:
    from ..plugin import PiggyCustomEnchants

SIMPLE = (
    AntiKnockbackEnchant, AntitoxinEnchant, AutoAimEnchant, AutoRepairEnchant, ArmoredEnchant, BerserkerEnchant,
    BlessedEnchant, BombardmentEnchant, BountyHunterEnchant, CactusEnchant, ChickenEnchant, CloakingEnchant,
    DeathbringerEnchant, DeepWoundsEnchant, DisarmingEnchant, DisarmorEnchant, DrillerEnchant, EndershiftEnchant,
    EnergizingEnchant, EnlightedEnchant, ExplosiveEnchant, FarmerEnchant, FertilizerEnchant, FocusedEnchant,
    ForcefieldEnchant, GooeyEnchant, GrapplingEnchant, GrowEnchant, HallucinationEnchant, HarvestEnchant,
    HeadhunterEnchant, HealingEnchant, HeavyEnchant, ImplantsEnchant, JackpotEnchant, JetpackEnchant,
    LifestealEnchant, LightningEnchant, LuckyCharmEnchant, LumberjackEnchant, MagmaWalkerEnchant,
    MeditationEnchant, MissileEnchant, MolotovEnchant, MoltenEnchant, OverloadEnchant, ParachuteEnchant,
    ParalyzeEnchant, PiercingEnchant, PoisonousCloudEnchant, ProwlEnchant, QuickeningEnchant, RadarEnchant,
    ReviveEnchant, SelfDestructEnchant, ShieldedEnchant, ShrinkEnchant, ShuffleEnchant, SmeltingEnchant,
    SoulboundEnchant, SpiderEnchant, StompEnchant, TankEnchant, TelepathyEnchant, VacuumEnchant, VampireEnchant,
    VolleyEnchant,
)


def _facing_sprinting(event) -> bool:
    return event.damager is not None and bool(getattr(event.damager, "is_sprinting", False))


def build_all(plugin: "PiggyCustomEnchants") -> list[CustomEnchant]:
    ids = ENCHANT_IDS
    out: list[CustomEnchant] = []

    out += [
        AttackerDeterrentEnchant(plugin, ids["cursed"], "Cursed", ["wither"], [60], [1], "uncommon"),
        AttackerDeterrentEnchant(plugin, ids["drunk"], "Drunk", ["slowness", "mining_fatigue", "nausea"],
                                 [60, 60, 60], [1, 1, 0]),
        AttackerDeterrentEnchant(plugin, ids["frozen"], "Frozen", ["slowness"], [60], [1]),
        AttackerDeterrentEnchant(plugin, ids["hardened"], "Hardened", ["weakness"], [60], [1], "uncommon"),
        AttackerDeterrentEnchant(plugin, ids["poisoned"], "Poisoned", ["poison"], [60], [1], "uncommon"),
        AttackerDeterrentEnchant(plugin, ids["revulsion"], "Revulsion", ["nausea"], [20], [0], "uncommon"),
        ConditionalDamageMultiplierEnchant(
            plugin, ids["aerial"], "Aerial",
            lambda e: e.damager is not None and not getattr(e.damager, "is_on_ground", True), "uncommon"),
        ConditionalDamageMultiplierEnchant(
            plugin, ids["backstab"], "Backstab",
            lambda e: e.damager is not None and direction_of(e.damager).dot(direction_of(e.entity)) > 0, "uncommon"),
        ConditionalDamageMultiplierEnchant(plugin, ids["charge"], "Charge", _facing_sprinting, "uncommon"),
        LacedWeaponEnchant(plugin, ids["blind"], "Blind", "common", ["blindness"], [20], [0], [100]),
        LacedWeaponEnchant(plugin, ids["cripple"], "Cripple", "common", ["nausea", "slowness"], [100, 100], [0, 1]),
        LacedWeaponEnchant(plugin, ids["poison"], "Poison", "uncommon", ["poison"]),
        LacedWeaponEnchant(plugin, ids["wither"], "Wither", "uncommon", ["wither"]),
        ProjectileChangingEnchant(plugin, ids["blaze"], "Blaze", "blaze"),
        ProjectileChangingEnchant(plugin, ids["homing"], "Homing", "homing", 3, "mythic"),
        ProjectileChangingEnchant(plugin, ids["porkified"], "Porkified", "porkified", 3, "mythic"),
        ProjectileChangingEnchant(plugin, ids["witherskull"], "Wither Skull", "witherskull", 1, "mythic"),
        ToggleableEffectEnchant(plugin, ids["enraged"], "Enraged", 5, Usage.CHESTPLATE, Kind.CHESTPLATE, "strength", -1),
        ToggleableEffectEnchant(plugin, ids["gears"], "Gears", 1, Usage.BOOTS, Kind.BOOTS, "speed", 0, 0, "uncommon"),
        ToggleableEffectEnchant(plugin, ids["glowing"], "Glowing", 1, Usage.HELMET, Kind.HELMET, "night_vision", 0, 0, "common"),
        ToggleableEffectEnchant(plugin, ids["haste"], "Haste", 5, Usage.HAND, Kind.PICKAXE, "haste", 0, 1, "uncommon"),
        ToggleableEffectEnchant(plugin, ids["obsidianshield"], "Obsidian Shield", 1, Usage.ARMOR_INVENTORY, Kind.ARMOR,
                                "fire_resistance", 0, 0, "common"),
        ToggleableEffectEnchant(plugin, ids["oxygenate"], "Oxygenate", 1, Usage.HAND, Kind.PICKAXE, "water_breathing",
                                0, 0, "uncommon"),
        ToggleableEffectEnchant(plugin, ids["springs"], "Springs", 1, Usage.BOOTS, Kind.BOOTS, "jump_boost", 3, 0, "uncommon"),
    ]
    for cls in SIMPLE:
        out.append(cls(plugin, ids[normalize_name(cls.name)]))
    return out
