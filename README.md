# PiggyCustomEnchants — Port untuk EndstoneMC

Ini adalah hasil porting plugin **PiggyCustomEnchants** (PocketMine-MP, oleh DaPigGuy) ke
[Endstone](https://endstone.dev/) 0.11.x untuk Minecraft: Bedrock Edition. Plugin ditulis ulang total
dari PHP ke Python karena kedua platform tidak kompatibel secara biner maupun API.

Semua 91 custom enchant dari plugin asli **terdaftar** dan bisa dipasang lewat `/ce enchant`. Sebagian
besar bekerja persis seperti aslinya; sebagian lain diemulasikan karena Endstone 0.11 belum punya API
yang setara PocketMine (lihat [Matriks Fidelity](#matriks-fidelity) di bawah). Tidak ada yang dihapus
diam-diam — enchant yang tidak bisa diemulasikan tetap terdaftar tapi ditandai "unsupported" dan bisa
dimatikan lewat config.

## ⚠️ Status pengujian — baca ini dulu

Saya (asisten yang membuat porting ini) **tidak punya akses ke server Bedrock Dedicated Server** di
lingkungan kerja saya, jadi kode ini **belum pernah dijalankan di server Endstone sungguhan**. Yang sudah
saya verifikasi:

- Seluruh kode berhasil di-*compile* (`python3 -m py_compile`) tanpa syntax error.
- 13 unit test (`tests/test_core_logic.py`) lulus, mencakup: penyimpanan NBT (baca/tulis/pertahankan lore
  lain), registrasi seluruh 91 enchant tanpa `KeyError`, pengecekan incompatibility antar enchant,
  klasifikasi jenis item (pedang/bow/dst), dan logika `Engine` yang memindai equipment pemain (armor +
  held item) serta rekonsiliasi toggle on/off.
- Modul `plugin.py`, `listeners.py`, dan `commands.py` berhasil di-*import* penuh melawan modul `endstone`
  tiruan (`tests/fake_pkg`), jadi tidak ada `ImportError`/`AttributeError` pada saat pemanggilan atribut
  API yang saya asumsikan ada.

Yang **belum** bisa saya verifikasi (perlu kamu tes langsung di server):
- Apakah command vanilla yang dipakai sebagai jembatan (`/effect`, `/damage`, `/setblock ... destroy`)
  benar-benar berperilaku seperti yang saya asumsikan di versi Bedrock yang kamu pakai.
- Apakah paket mentah `RadarEnchant` (SetSpawnPosition) dan `HallucinationEnchant` (UpdateBlock) diterima
  klien tanpa membuatnya disconnect — ini teknik yang paling berisiko di seluruh porting ini.
- Timing/rasa gerakan hasil emulasi teleport (Jetpack, Grappling, Forcefield, dll) — nilai kecepatan sudah
  disalin dari rumus aslinya tapi belum dirasakan langsung.
- Performa saat banyak pemain memakai enchant tick-heavy (Forcefield, PoisonousCloud, Vacuum) sekaligus.

Mohon laporkan bug/rasa yang aneh supaya bisa diperbaiki lebih lanjut.

## Instalasi

1. Salin folder `endstone-piggy-custom-enchants/` ke server dengan Python 3.10+ dan Endstone 0.11 terpasang.
2. Build wheel-nya:
   ```bash
   cd endstone-piggy-custom-enchants
   pip install build
   python -m build
   ```
3. Salin file `.whl` hasilnya ke folder `plugins/` server Endstone-mu, lalu jalankan server.
4. Saat pertama kali menyala, plugin membuat `plugins/PiggyCustomEnchants/config.toml` beserta file data
   `rarities.json`, `max_levels.json`, `display_names.json`, `descriptions.json`, `extra_data.json`,
   `cooldowns.json`, dan `chances.json` — persis seperti versi PocketMine, jadi bisa kamu tuning tanpa
   menyentuh kode.

## Perintah

`/ce` (alias `/customenchants`, `/customenchant`):

| Subcommand | Kegunaan | Permission |
|---|---|---|
| `/ce about` | Info versi plugin | `piggycustomenchants.command.ce.about` |
| `/ce list` | Daftar semua enchant per kategori | `piggycustomenchants.command.ce.list` |
| `/ce info <enchant>` | Detail satu enchant | `piggycustomenchants.command.ce.list` |
| `/ce enchant <enchant> [level] [player]` | Pasang enchant ke item di tangan | `piggycustomenchants.command.ce.enchant` (default: op) |
| `/ce remove <enchant> [player]` | Lepas enchant dari item di tangan | `piggycustomenchants.command.ce.remove` (default: op) |
| `/ce nbt` | Tampilkan NBT item di tangan (debug) | `piggycustomenchants.command.ce.nbt` (default: op) |

Set `forms.enabled = true` di `config.toml` untuk memakai form GUI seperti versi asli.

### Buku enchant

Sama seperti aslinya: pegang buku (polos/enchanted) berisi enchant custom di tangan utama, taruh item
target di tangan kedua (off-hand), lalu klik kanan. Ini menggantikan mekanisme "drag item ke book" di
PocketMine yang tidak punya event setara di Endstone.

## Matriks Fidelity

**Penuh** — perilaku sama persis dengan versi asli (memakai API Endstone langsung, tanpa emulasi):

Anti Knockback, Armored, Attacker Deterrent (Cursed/Drunk/Frozen/Hardened/Poisoned/Revulsion), Berserker,
Blessed, Cactus, Chicken, Cloaking, Conditional Multiplier (Aerial/Backstab/Charge), Deathbringer,
Deep Wounds, Disarming, Disarmor, Driller, Endershift, Energizing, Enlighted, Explosive, Farmer,
Fertilizer, Gooey, Harvest, Headhunter, Healing, Heavy, Implants, Jackpot, Laced Weapon
(Blind/Cripple/Poison/Wither), Lifesteal, Lightning, Lucky Charm, Lumberjack, Meditation, Molten,
Overload, Parachute, Piercing, Poisonous Cloud, Quickening, Revive, Self Destruct, Shielded, Shuffle,
Smelting, Soulbound, Stomp, Tank, Telepathy, Toggleable Effect (Enraged/Gears/Glowing/Haste/Obsidian
Shield/Oxygenate/Springs), Vampire.

**Diemulasikan** — perilaku akhirnya semirip mungkin, tapi memakai teknik pengganti karena API Endstone
tidak punya event/setter yang setara. Detail teknik ada sebagai komentar di kode masing-masing:

| Enchant | Teknik pengganti |
|---|---|
| Blaze, Wither Skull, Porkified, Homing | Proyektil disimulasikan sendiri (posisi/kecepatan diintegrasikan per tick, tabrakan dicek manual), bukan entity proyektil asli Minecraft dengan hook `onHitEntity` |
| Bombardment, Missile | TNT asli di-spawn lalu diledakkan lewat mesin ledakan buatan sendiri (ray-cast blok ala PocketMine `Explosion`) |
| Volley | Anak panah tambahan disimulasikan (bukan entity panah asli) |
| Grappling | Tarikan disimulasikan lewat teleport bertahap (tidak ada setter velocity di Endstone) |
| Forcefield | Entitas didorong lewat teleport; proyektil masuk **dihancurkan** (tidak bisa membalik arah geraknya) |
| Jetpack, Auto Aim | Gerak terbang/incoming-shot disimulasikan lewat teleport per tick |
| Radar | Memakai compass, tapi menunjuk lokasi lewat paket mentah `SetSpawnPosition` — **berisiko**, lihat peringatan di atas |
| Hallucination | Ilusi blok dikirim lewat paket mentah `UpdateBlock` ke satu klien saja |
| Antitoxin, Focused | Tidak ada event "efek ditambahkan"; efek racun/mual dihapus lagi tiap beberapa tick setelah muncul |
| Magma Walker | Deteksi lava & pembentukan obsidian manual (tanpa `BlockUpdateEvent` bertarget) |
| Molotov | Area api dipasang & dihapus otomatis, bukan entity `FallingBlock` yang terbakar |
| Prowl | Karena `hidePlayer`/`showPlayer` tidak ada di Endstone, disiasati dengan invisibility + slowness saja (pemain lain tetap melihat outline transparan, bukan benar-benar hilang) |
| Spider | `setCanClimbWalls` tidak ada; disiasati dengan mendeteksi lompat ke tembok lalu "menempel" lewat teleport ke atas selama beberapa detik |

**Tidak didukung** — dinonaktifkan secara default (`enable-unsupported = false` di config) karena Endstone
0.11 tidak punya API untuk mengubah ukuran entitas:

- **Grow** dan **Shrink** (butuh `Actor.setScale()`, belum ada endpoint setara)

Enchant tetap terdaftar dan bisa dipasang lewat `/ce enchant --override`, tapi tidak melakukan apa-apa
selama Endstone belum menambah API-nya.

**Sengaja tidak diporting** (bukan mekanisme gameplay, spesifik ke PocketMine):
- Sistem anti-tamper `isCoolKid()` dan remote-disable via Gist milik penulis asli.
- Update checker.
- Ketergantungan pada library virion PocketMine.

## Konfigurasi tambahan khusus port ini

Bagian `[endstone]` di `config.toml` berisi pengaturan yang tidak ada di versi asli karena memang
dibutuhkan akibat perbedaan arsitektur:

- `inventory-scan-interval` — seberapa sering (tick) seluruh inventory dipindai ulang untuk enchant baru;
  armor dan item yang sedang dipegang selalu dicek tiap tick.
- `emulate-ignite` — Endstone tidak punya `setOnFire()`, jadi enchant seperti Molten menyalakan blok api
  sesaat di kaki target. Bisa dimatikan.
- `explosion-max-size` / `explosion-max-blocks` — batas ukuran ledakan buatan (Explosive, TNT) supaya
  server tidak lag saat level enchant sangat tinggi.
- `debug` — jika `true`, semua kegagalan operasi (command vanilla gagal, aktor tidak ditemukan, dst)
  dicatat ke log server.

## Struktur proyek

```
src/endstone_piggy_custom_enchants/
  plugin.py        # kelas Plugin utama, siklus hidup, util command/effect/damage
  engine.py         # pemindaian equipment pemain, dispatch reaksi, tick, toggle
  manager.py        # registry enchant, kompatibilitas, terapkan/lepas enchant di item
  storage.py        # baca/tulis data enchant di NBT item (tag "PiggyCE")
  compat.py         # jembatan ke command vanilla (/effect, /damage, /setblock)
  projectiles.py    # deteksi panah custom & simulasi proyektil custom
  motion.py         # gerak berbasis teleport (Jetpack, Grappling, dll)
  explosion.py      # ulang mesin ledakan PiggyExplosion (ray-cast + damage + drop)
  enchants/         # implementasi tiap enchant, dikelompokkan seperti struktur asli
tests/
  test_core_logic.py  # unit test (lihat bagian status pengujian)
  fake_pkg/endstone/  # tiruan minimal API Endstone, hanya untuk keperluan unit test
```

## Lisensi

Sama seperti proyek asli: Apache License 2.0 (lihat `LICENSE`). Hak cipta asli 2017 DaPigGuy.
