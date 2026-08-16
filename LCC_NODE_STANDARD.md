# LCC RPi Pico Node — Architectural Standard

This document is the cross-project source of truth for every LCC (OpenLCB) node
built on Bob Gamble's RPi Pico node board family. It governs conventions that
must stay consistent across repos so that any Claude Code session — in this
repo or any other node repo — produces code that fits the established
architecture instead of reinventing it per-project.

**Audience**: Claude Code sessions (and human contributors) working in any
`LCC_RPiPico_*` repository.

**Scope**: hardware/board conventions, file layout, the dual-core contract,
configuration-memory handling, and naming rules that apply to *every* node.
Per-project `CLAUDE.md` files document only what is specific to that node
(its purpose, its module list, its data flow) and should link back here
rather than restate these rules.

**Current node projects**: `LCC_RPiPico_Turntable`, `LCC_RPiPico_Roundhouse`,
`LCC_RPiPico_Clock_Lights`, `LCC_RPiPico_PixelLights`, `LCC_RPiPico_CommandStation`,
`LCC_RPiPico_Booster`.

> `LCC_RPiPico_CommandStation` and `LCC_RPiPico_Booster` are listed as of
> Rev 15 but haven't yet reached the implementation phases (LCC/CAN
> integration, CDI/EEPROM config memory) that this document's §7–§7.3
> conventions govern — their own `work_plan.md`s track that separately.
> Don't assume either one is compliant with §7.1's protected NVM region,
> §7.3's SNIP derivation, etc. yet; check their own repos' status before
> relying on it.

---

## Index

1. [Purpose & Scope](#1-purpose--scope)
2. [Fixed Toolchain & Libraries](#2-fixed-toolchain--libraries)
3. [Reference Node Architecture](#3-reference-node-architecture)
4. [Board Versioning Convention](#4-board-versioning-convention)
5. [Pin Assignment Registry](#5-pin-assignment-registry)
6. [Breakout Board Catalog](#6-breakout-board-catalog)
7. [Configuration Memory (CDI/EEPROM) Conventions](#7-configuration-memory-cdieeprom-conventions)
   - [7.1 Protected NVM Region (above CONFIG_MEM_SIZE)](#71-protected-nvm-region-above-config_mem_size)
   - [7.2 Factory Reset Button Gesture](#72-factory-reset-button-gesture)
   - [7.3 SNIP Identity Fields (hardware_version / software_version)](#73-snip-identity-fields-hardware_version--software_version)
8. [Dual-Core Contract](#8-dual-core-contract)
9. [Naming Conventions](#9-naming-conventions)
10. [OpenLCB Integration Rules](#10-openlcb-integration-rules)
11. [Serial CLI Conventions](#11-serial-cli-conventions)
12. [Per-Project CLAUDE.md Template](#12-per-project-claudemd-template)
13. [Change Log](#13-change-log)

---

## 1. Purpose & Scope

Every node in this family shares one base hardware platform (the RPi Pico
"Node board," currently at revisions v2.5–v3.0) plus a swappable breakout
board for the node's specific job (stepper driver, servo driver, display,
NeoPixel strip, etc.). The software stack on top is the same OpenLCB C
library and the same handful of Arduino libraries on every node. What varies
is: which board revision, which breakout, which pins, and what the node
*does*.

This document exists so that variance is captured in **data** (board headers,
tables) rather than in divergent **architecture**. A Claude session reading
only this file and a project's own `CLAUDE.md` should be able to add a new
node, a new board revision, or a new breakout without guessing at conventions
already established elsewhere in the family.

What this document does **not** cover: node-specific business logic
(turntable phase switching, servo door sequencing, clock face rendering).
That belongs in the owning project's `CLAUDE.md` and source comments.

## 2. Fixed Toolchain & Libraries

These are fixed across the family — do not propose alternatives unless the
user explicitly asks to evaluate a replacement.

- **IDE**: Arduino IDE (primary) or VS Code with Arduino extension
- **Board package**: Raspberry Pi Pico 2, `rp2040:rp2040:rpipico2`, via
  [Philhower's RP2040 core](https://github.com/earlephilhower/arduino-pico#installation)
  — **never** the Mbed-based core
- **C++ standard**: `gnu++17`
- **Build config**: `sketch.yaml` per project (4MB flash, optimization: small)
- **OpenLCB stack**: MustangPeak `OpenLcbClib` — vendored under `src/openlcb/`
  and `src/drivers/canbus/` in every project; treated as a fixed external
  dependency (see [§10](#10-openlcb-integration-rules))

**Library set** (install via Arduino Library Manager unless noted):

| Library | Role | Notes |
|---|---|---|
| `ACAN2517` (Pierre Molinaro) | CAN transceiver driver (MCP2517/18) | fixed, never substitute |
| `I2C_eeprom` (Rob Tillaart) | External EEPROM/FRAM read-write | fixed; `USE_TILLAART` selects this over the Adafruit alternative |
| `Wire`, `SPI` | I2C/SPI buses | Arduino core, fixed |
| `AccelStepper` | Stepper motion control | **local customized copy** under `src/application_drivers/` — do not replace with the stock library; only Turntable currently uses it |
| `PCA9685_servo_driver` / `PCA9685_servo` | I2C PWM servo control | used by Roundhouse-class (servo) nodes |
| `NeoPixelBus` | NeoPixel type definitions / strip control | used wherever NeoPixel output is required |
| `NeoPixelConnect` | Alternate NeoPixel driver (seen in Roundhouse `TTcomms.cpp`) | only when `NeoPixelBus` doesn't fit the use site |
| `TFT_eSPI` / native `RA8876_RP2040` | Display driving | display driver selection is a `ProjectConfig.h` choice — see [§4](#4-board-versioning-convention) |
| `LibPrintf` | `printf()` over Serial | optional, debug convenience |

When a new node needs a capability not in this table, add the library here
with the same row format before using it in more than one project — that's
the signal it has graduated from "node-specific" to "family-standard."

## 3. Reference Node Architecture

Every node should be assembled from these named pieces. This is not
aspirational — it's the pattern already implemented in Turntable, Roundhouse,
Clock_Lights, and PixelLights; new nodes should match it from the start.

```
ProjectConfig.h          ← single switch: pick ONE board macro, ONE display driver macro
        │
        ▼
BoardSettings.h           ← #include "ProjectConfig.h"; dispatches on the board
        │                    macro to the matching board_configs/ header; also
        │                    holds NVM/storage size selection and global tuning
        │                    constants (EEPROM_VERSION, FREQUENCY, etc.)
        ▼
board_configs/
  BoardPins_<Family>_v<NN>.h   ← PHYSICAL pin topology only, one file per
                                  hardware revision. No functional meaning —
                                  just "this GPIO is connector X pin Y"
        │
        ▼
NodeConfig.h (optional)    ← FUNCTIONAL pin assignment layer, present when a
                               node needs to map physical connector pins to
                               roles (NeoPixel string A/B/C/D, button pins)
                               independent of board revision
        │
        ▼
<NodeName>.cpp / .h        ← the node's actuation/sensing logic (Turntable.cpp,
                               Roundhouse.cpp, NPlights.cpp, ClockDisplay.cpp)
callbacks.cpp / .h         ← the ONLY place OpenLCB consumers/producers are
                               registered and dispatched; bridges LCC events
                               to the node logic above
config_mem_helper.cpp/.h   ← CDI-driven EEPROM/FRAM config storage
mdebugging.h               ← shared dP()/dPH()/dPS() debug macro family,
                               compiled to no-ops unless DEBUG is defined
<NodeName>.ino             ← entry point: node init, consumer/producer
                               registration, serial CLI, setup()/loop()
```

**Rule of thumb when adding a file**: pin *topology* goes in
`board_configs/`, pin *function* goes in `NodeConfig.h` or the relevant
`BoardSettings.h` define, and node *behavior* goes in the node's own
`.cpp`/`.h` pair. Never hardcode a GPIO number outside `board_configs/`.

## 4. Board Versioning Convention

- `ProjectConfig.h` is **the single file to edit** when switching hardware
  target or display driver for a given project. It is "Step 1 (required):
  uncomment exactly one `LCC_BOARD_<FAMILY>_V<NN>` line. Step 2 (when the
  board has a display header): uncomment exactly one `DISPLAY_DRIVER_*` line."
- Board macro naming: `LCC_BOARD_<FAMILY>_V<NN>`, where `<FAMILY>` identifies
  the breakout combination and `<NN>` is the board revision (`25`, `26`,
  `27`, `28`, `29`, `295` for v2.95, `30`). `NODE` is the generic node board
  with no dedicated breakout — this is the only family going forward as of
  v3.0 (see [§5](#5-pin-assignment-registry)). `STEPPER` (Node board +
  integrated TMC2209/display, v2.4–v2.95) is **legacy and frozen** — do not
  add new `STEPPER` revisions; new stepper nodes use a generic `NODE` board
  plus the TMC2209 breakout (see [§6](#6-breakout-board-catalog)).
- Each macro maps to exactly one `board_configs/BoardPins_<Family>_v<NN>.h`,
  selected via `#if defined(...) / #elif / #error` chain in `BoardSettings.h`.
  The `#error` fallback is mandatory — a project must fail to compile rather
  than silently pick a default board.
- `BoardSettings.h` includes `ProjectConfig.h` itself (not the other way
  around) so every translation unit gets consistent defines through its own
  `#include "BoardSettings.h"`, not just the `.ino`.
- Display driver selection (`DISPLAY_DRIVER_RA8876_NATIVE` vs
  `DISPLAY_DRIVER_RA8876_TFTESPI` vs `DISPLAY_DRIVER_SSD1963_PARALLEL`) is
  independent of board selection but constrained by it — document in the
  `BoardPins_*.h` header comment which display drivers a given board
  revision supports, and `#error`/no-op stub boards that don't have a
  display header at all.
- **New board revision checklist**:
  1. Add `board_configs/BoardPins_<Family>_v<NN>.h` with a header comment
     describing the physical hardware (base board + breakout combination)
     and how it differs from the nearest prior revision.
  2. Add the `#elif defined(LCC_BOARD_<FAMILY>_V<NN>)` arm in every
     `BoardSettings.h` across projects that share the family (a new Node
     board revision affects PixelLights, Clock_Lights, Roundhouse, *and*
     Turntable simultaneously — update all four, even if only tested on one).
  3. Add the new line (commented out) to every project's `ProjectConfig.h`
     header comment table.
  4. Note shared/conflicting pins explicitly (e.g. "gp21/gp22 shared with
     Blue/Gold buttons — unavailable on this variant") — this has bitten
     past revisions (v2.95 stepper) and is the single most important thing
     to get right in a new board header.

## 5. Pin Assignment Registry

Maintain one table per board family. Treat **fixed-function traces** (CAN,
primary I2C storage bus) as identical across all revisions of a family
unless a board header explicitly says otherwise; treat **connector pins**
(IO1/IO2/IO3) as available for whatever breakout is attached.

### Node board family (generic; no dedicated breakout)

| Function | v2.5 | v2.6 | v2.7 | v2.8 | v2.9 | v3.0 |
|---|---|---|---|---|---|---|
| CAN (MCP2517/18, SPI) | gp16-20 | gp16-20 | gp16-20 | gp0-4 | gp0-4 | gp0-4 |
| I2C storage (EEPROM) | I2C1 gp26/27 | gp26/27 | — | I2C1 gp6/7 | I2C1 gp6/7 | I2C1 gp6/7 |
| Secondary I2C | I2C0 gp4/5 | I2C0 gp4/5 | I2C0 gp4/5 | I2C0 gp16/17 | none | none |
| Dedicated NeoPixel pins | gp2/3/6/7 | gp2/3/6/7 | none (I/O headers only) | none | none | none |
| Buttons (Blue/Gold) | gp21/gp22 | gp21/gp22 | gp21/gp22 | gp21/gp22 | gp21/gp22 (shared w/ IO2 pins 8/9) | gp5 (shared w/IO2 pin 10)/gp28 (shared w/IO3 pin 5)|
| I/O - 1 | gp15-8 |gp15-8|gp0-7|gp8-15|gp8-15|gp8-15|
| I/O - 2 | none |none|gp8-15|gp18-28|gp16-26|gp16-22, 5|
| I/O - 3 |none|none|none|none|gp26-28|gp26-28|

> Fill in v2.5–v2.8 columns from each board's `BoardPins_Node_v*.h` as they're
> revisited; v3.0 is current as of this writing (see
> `BoardPins_Node_v30.h` once added per project — not yet created in any repo).

### Stepper family (Node board w/ integrated stepper & display or breakout)
Stepper family nodes are depreciated with v3.0 adopting a generic node with functional breakout boards.
| Function | v2.4 | v2.7 | v2.9 | v2.95 |
|---|---|---|---|---|
| Display controller | SSD1963 (8-bit parallel, 800×480) | RA8876 (SPI, 1024×600) | RA8876 (SPI, 1024×600) | RA8876/LT7381 native (SPI1, 1024×600) |
| CAN | — | gp16-20 | gp0-4 | gp0-4 |
| Display bus | parallel | SPI (shared w/ CAN bus pins on v2.7) | SPI | SPI1 gp8-11 (no conflict with CAN SPI0) |
| Stepper breakout location | on-board | I/O-1 | I/O-1 | I/O-2 (TMC2209) |
| Stepper EN/STEP/DIR | board-specific | — | — | gp21/gp22/gp26 (EN+STEP share Blue/Gold buttons — **unavailable** on v2.95) |
| Touch controller | — | — | — | gp12/13 (I2C0/Wire) |

Always cross-reference the header comment in the relevant
`board_configs/BoardPins_*.h` file — it documents pin sharing and conflicts
in more detail than a table can carry, and is the authoritative source if
this table and the header ever disagree.

**Reserved sentinel values** (defined once in each project's
`BoardSettings.h`, used by board headers): `UNUSED_PIN = 127`,
`PWR_VCC = 126`, `PWR_GND = 125`, `PWR_AGND = 124`, `PWR_VREF = 123`. Use
these rather than `-1` or `0` for connector pins that carry power/ground
instead of a GPIO signal.

## 6. Breakout Board Catalog

| Breakout | Bus | Typical address/CS | Used by | Notes |
|---|---|---|---|---|
| TMC2209 stepper breakout | step/dir GPIO + I2C passthrough | n/a (GPIO) | Turntable (Stepper family) | Provides EN/STEP/DIR, home/bridge sensors, NeoPixel pass-through; plugs into I/O-1 (v2.7/v2.9) or I/O-2 (v2.95) |
| PCA9685 servo driver | I2C | `0x40` (`SERVO_ADDRESS`) | Roundhouse | Up to 16 channels; callback always reports address 0 — node code must poll, not rely on the callback (see Roundhouse `CLAUDE.md`) |
| 24LC256 EEPROM (or 24LC512/128/64/...) | I2C | `0x50` (`STORAGE_ADDR`) | All nodes | Size selected via `I2C_DEVICESIZE` in `BoardSettings.h`; must match `CONFIG_MEM_SIZE` |
| RA8876/LT7381 display | SPI (native) or SPI via TFT_eSPI | `DISPLAY_CS` per board header | Turntable, Clock_Lights | LT7381 is register-compatible with RA8876 — native library works unchanged |
| SSD1963 display | 8-bit parallel | n/a | Turntable v2.4 only | Legacy; superseded by RA8876-based boards |
| XPT2046 touch controller | SPI or I2C depending on board | `TOUCH_SDA`/`TOUCH_SCL` or SPI pins | Turntable, Clock_Lights (v2.95) | v2.95 wires touch via I2C0 (Wire) regardless of display bus |
| NeoPixel strip (direct GPIO) | single-wire | n/a | PixelLights, Clock_Lights, Roundhouse (optional) | Pin(s) named `NeoPixel_PinA/B/C/D`, defined per board header or `NodeConfig.h` |

### 6.1 Breakout Pin Assignments
#### TMC2209 stepper breakout
| Pin | Signal |
|---|---|
| I/O-2:Pin1 | SDA |
| I/O-2:Pin2 | SCL |
| I/O-2:Pin3 | Bridge Sensor |
| I/O-2:Pin4 | Home Sensor |
| I/O-2:Pin5 | Ground |
| I/O-2:Pin6 | +3.3 Vin |
| I/O-2:Pin7 | NeoPixel Data |
| I/O-2:Pin8 | Stepper Enable |
| I/O-2:Pin9 | Stepper Step |
| I/O-2:Pin10 | Stepper Direction |

#### SPI Display — XPT2046 Resistive Touch
| Pin | Signal |
|---|---|
| I/O-1:Pin1 | D_SDO/RX |
| I/O-1:Pin2 | D_CS |
| I/O-1:Pin3 | D_CLK |
| I/O-1:Pin4 | D_SDI/TX |
| I/O-1:Pin5 | Ground |
| I/O-1:Pin6 | + Vin (3.3 or 5V) |
| I/O-1:Pin7 | RTP_DOUT |
| I/O-1:Pin8 | RTP_CS |
| I/O-1:Pin9 | D_RST |
| I/O-1:Pin10 | open |

#### SPI Display — Capacitive Touch
| Pin | Signal |
|---|---|
| I/O-1:Pin1 | D_SDO/RX |
| I/O-1:Pin2 | D_CS |
| I/O-1:Pin3 | D_CLK |
| I/O-1:Pin4 | D_SDI/TX |
| I/O-1:Pin5 | Ground |
| I/O-1:Pin6 | + Vin (3.3 or 5V) |
| I/O-1:Pin7 | T_SDA |
| I/O-1:Pin8 | T_SCL |
| I/O-1:Pin9 | D_RST / T_RST |
| I/O-1:Pin10 | D_BL / T_RST / T_INT |

> **Shared RST gotcha** (found during Turntable v3.0 bring-up, 2026-06-21):
> `D_RST`/`T_RST` are the *same physical pin* on this breakout. The touch
> library's chip-type auto-detection (`BBCapTouch::reset()` in
> `my_bb_captouch.cpp`) issues real 100ms-low/250ms-high reset pulses on
> `TOUCH_RST` while probing for GT911/CHSC6540/AXS15231 — and since that's
> the same pin as `DISPLAY_RST`, it also resets the RA8876/LT7381 display
> controller back to power-on defaults. If touch init (`tp.init()`) runs
> *after* display init (`tft.init()`), as it normally does, every subsequent
> draw call succeeds (no error, no hang — the SPI bus and register-write
> protocol still work) but produces **nothing visible**, because the
> display chip's own timing/enable registers were silently reset.
>
> **Fix**: re-run `tft.init()` (and `tft.setRotation()`) immediately after
> `tp.init()` returns, whenever `TOUCH_RST == DISPLAY_RST`. See
> `LCC_RPiPico_Turntable/UserInterface.cpp`'s `setupDisplay()` for the
> guarded (`#if (TOUCH_RST == DISPLAY_RST)`) implementation — apply the same
> pattern to any other project/combo that shares these pins on this
> breakout. Symptom to watch for: display reports a clean init (correct
> chip ID, "Display initialization complete!") and the app's own setup
> functions all return normally with no hang, but the screen stays
> completely blank (not even a black-on-black ambiguity — diagnostic fills
> in *non-black* colors, tested **before** touch init, also fail to show
> once the page-drawing code runs **after** touch init).

> **Stray "CDI text on screen" bug — a long misdiagnosis before the real
> cause** (found during the same bring-up, 2026-06-21, once the blank-screen
> issue above was fixed). Symptom: a line of text resembling fragments of
> the node's own CDI XML (e.g. `</name></eventid></group></segment></cdi>`,
> later `wValue='yes'></slider></hints></int><eventid><name>Low-Luminosity On`)
> appeared during the homing animation, partially overwritten as later
> graphics drew on top of it, never recurring once homing completed.
>
> **Four theories were tried and disproven** before the real cause was
> found — recorded here so they aren't re-tried:
> 1. Scroll/margin window unset to the real panel size — wrong; this
>    library's `HDW`/`VDH` globals are already hardcoded to 1024/600.
> 2. `fillScreen()` bypassing the hardened `fillRect()` and failing on an
>    unverified full-panel GE call — the override is still good practice
>    (kept in `TT_Display::fillScreen()`) but changed nothing.
> 3. Unclamped `TrackCount` causing an out-of-bounds read in `drawTracks()`
>    — a *real* bug (now fixed, see §6.1's other entry on this), but not
>    *this* symptom; clamping it changed nothing either.
> 4. Network/CDI-stream crosstalk on a shared CAN bus — invalidated
>    immediately: the node under test had no CAN connection at all, only USB.
>
> The breakthrough was timing, not content: the artifact appeared **after**
> the home page finished drawing but **before** homing completed — i.e.
> during repeated calls to `drawBridge()` (invoked from `updateBridgeAnimation()`
> on Core 0 as the stepper visually moves toward home), not during the
> one-time initial page draw every earlier theory assumed.
>
> **Actual root cause**: `drawBridge()` (`UserInterface.cpp`) does
> `tft.drawString(TrackName[ConfigMemHelper_config_data.CurrentTrack], ...)`
> with no bounds check. `CurrentTrack` is a **top-level** `config_mem_t`
> field — not under `.attributes` — so it's runtime state, not a CDI-defined
> value, and **none** of the `_load_defaults_*` functions ever set it. An
> `'r'` (wipe to `0xFF`) + `'i'` (write CDI defaults) reset therefore left it
> at **255**. `TrackName[255]` reads 6375 bytes past the 20-entry
> (`MAX_TRACKS`), flash-resident (`const`) array — landing on whatever the
> linker placed next, which in this build was close enough to the embedded
> `_cdi_data[]` (also `const`/flash) to render genuine, readable CDI text.
> Deterministic stale byte → same landing spot every boot; `drawBridge()`
> called repeatedly during homing → exactly the observed window;
> `MoveToTrack()` later setting `CurrentTrack` legitimately → why it stopped
> once homing finished and a real track move occurred.
>
> **Fix**: same pattern as the `TrackCount`/`DoorCount` fix, applied to this
> field too — `config->CurrentTrack` is now explicitly defaulted in
> `_load_defaults_attributes()` and clamped to `MAX_TRACKS-1` once inside
> `ConfigMemHelper_read()`, plus a belt-and-suspenders local clamp at the
> `drawBridge()` call site itself.
>
> **The general lesson, twice-confirmed now**: any `config_mem_t` field used
> as an array index or loop bound — whether under `.attributes` (CDI-defined)
> or a top-level field (runtime state) — needs (a) an explicit default in the
> loader so a factory reset actually initializes it, and (b) a clamp at the
> NVM-read boundary, not at each use site. Top-level fields are easy to miss
> precisely *because* they're not CDI-defined — nothing on the JMRI/config-tool
> side will ever validate them, so a missing default is invisible until
> something indexes an array with the stale value.

#### Parallel Display — Capacitive Touch
| Pin | Signal |
|---|---|
| I/O-1:Pin1 | DB0 |
| I/O-1:Pin2 | DB1 |
| I/O-1:Pin3 | DB2 |
| I/O-1:Pin4 | DB3 |
| I/O-1:Pin5 | Ground |
| I/O-1:Pin6 | + 5V |
| I/O-1:Pin7 | DB4 |
| I/O-1:Pin8 | DB5 |
| I/O-1:Pin9 | DB6 |
| I/O-1:Pin10 | DB7 |
| I/O-2:Pin1 | T_SDA |
| I/O-2:Pin2 | T_SCL |
| I/O-2:Pin3 | Bridge Sensor |
| I/O-2:Pin4 | Home Sensor / D_RST |
| I/O-2:Pin5 | Ground |
| I/O-2:Pin6 | + 3.3 V |
| I/O-2:Pin7 | NeoPixel Data |
| I/O-2:Pin8 | Stepper Enable |
| I/O-2:Pin9 | Stepper Step |
| I/O-2:Pin10 | Stepper Direction |
| I/O-3:Pin1 | Stepper Direction (common w/IO2-10)|
| I/O-3:Pin2 | D_WR |
| I/O-3:Pin3 | AGND |
| I/O-3:Pin4 | VREF |
| I/O-3:Pin5 | D_D/C |
| I/O-3:Pin6 | Ground |

> Corrected 2026-06-20: the original breakout design had Pin4/Pin5 transposed
> (D_D/C was assigned to the VREF pin). The table above now matches the v3.0
> board's actual I/O-3 wiring: Pin4 stays VREF (analog reference, not used by
> this breakout) and Pin5 carries D_D/C (gp28, shared with `GOLD_BUTTON_PIN`
> — Gold button is unavailable when this breakout is in use). See §3's
> Turntable `NodeConfig.h` for the implemented mapping.

When a new breakout is introduced, add a row here and reference it from the
new board family's `LCC_BOARD_<FAMILY>_V<NN>` naming.

## 7. Configuration Memory (CDI/EEPROM) Conventions

- Config is persisted to external I2C EEPROM (or FRAM), described by a CDI
  XML descriptor, with memory layout and defaults code-generated from it.
  Three generated artifacts live in each project's `Documentation/`:
  - `config_mem_map.h` — memory layout (**do not hand-edit**)
  - `config_mem_reset.c` / `.h` — generated defaults (**do not hand-edit**)
  - `openlcb-config-<date>.xml` — the CDI descriptor that generated the above
- Config structs use `#pragma pack(push, 1)` for exact, predictable memory
  layout — required because the layout must match the generated map exactly.
- `EEPROM_VERSION` (in `BoardSettings.h`) gates whether stored config is
  considered valid; bump it whenever the CDI/struct layout changes, so a
  stale EEPROM gets reset to defaults rather than misread.
- **Deferred writes**: direct EEPROM writes from an event callback block
  Core 0 for 200–500ms and stall CAN processing. The established pattern is:
  set a `_config_dirty` flag on any state change, and flush from the 100ms
  timer after a quiet period (Roundhouse uses 30 ticks ≈ 3 seconds). New
  nodes should reuse this pattern rather than writing to EEPROM synchronously
  in a callback.
- `CDI.xml`'s `<manufacturer>/<model>/<hardwareVersion>/<softwareVersion>`
  must mirror `openlcb_user_config.c`'s `.snip.name/model/hardware_version/
  software_version` exactly — see §7.3 for how those SNIP fields themselves
  are derived/composed.
- Storage backend selection (`USE_I2C_STORAGE` vs `USE_INTERNAL_FLASH_STORAGE`,
  `EXTERNAL_EEPROM` vs `EXTERNAL_FRAM`, `USE_TILLAART` vs Adafruit) lives in
  `BoardSettings.h` next to the board dispatch — keep this block in sync
  across projects unless a node has a specific reason to diverge.
- **Regenerating the CDI byte array**: `openlcb_user_config.c`'s
  `static const uint8_t _cdi_data[] = { ... }` must be kept in sync with
  `CDI.xml` by hand any time the XML changes (there is no build-time
  codegen step for it). Use `LCC_RPiPico_Common/cdi_to_c_array.py` rather
  than editing the array by hand or using the browser-based
  `cdi_fdi_wizard.html` tool's "Array" tab, which requires more manual
  copy/paste:
  ```
  python cdi_to_c_array.py <project>/CDI.xml -o out.txt
  ```
  Splice the byte-array body (between `.cdi = {` and the closing `},`) from
  `out.txt` into `_cdi_data[]`, preserving that project's existing
  formatting immediately before the first byte line (some projects have a
  `// CDI byte array.` comment there, some just a blank line — match
  whichever file you're editing). Fields that use `sizeof(_cdi_data)`
  (e.g. `.address_space_configuration_definition.highest_address`) update
  automatically; the `#define USER_CDI_ARRAY_SIZE` the script prints is
  informational only — separately confirm `CONFIG_MEM_SIZE` (driven by
  `I2C_DEVICESIZE` in `BoardSettings.h`) is still large enough to hold the
  new array, since the script does not check this.

### 7.1 Protected NVM Region (above `CONFIG_MEM_SIZE`)

CDI-driven config memory (above) is wiped wholesale by the `c`/`r` serial
commands and by a CDI/struct layout change bumping `EEPROM_VERSION`. Some
data must survive *both* of those — most importantly the node's own LCC
identity — so it lives in a **separate, protected region** above
`CONFIG_MEM_SIZE`, out of reach of the config wipe/reset bounds checks.

**Size constraint**: `CONFIG_MEM_SIZE` must be **less than** `I2C_DEVICESIZE`
(or the internal-flash-emulation size) by enough bytes to fit the protected
region. The existing driver bounds check
(`if (address > CONFIG_MEM_SIZE - 1)`) already keeps config-memory wipes from
reaching anything above it — that's the mechanism this region relies on; do
not change the wipe commands or `config_mem_helper.cpp` bounds checks to
"fix" this, they're protecting the gap by design.

**Standard definition**: define `CONFIG_MEM_SIZE` in `BoardSettings.h` as
`#define CONFIG_MEM_SIZE (I2C_DEVICESIZE-64)` — a formula off the active
`I2C_DEVICESIZE`, not a separate hardcoded literal that has to be
remembered and kept in sync by hand whenever `I2C_DEVICESIZE` changes.
**The parentheses are required, not stylistic**: an unparenthesized
`I2C_DEVICESIZE-64` expands wrong wherever `CONFIG_MEM_SIZE` is used in a
division elsewhere in the codebase — e.g. `CONFIG_MEM_SIZE / sizeof(buffer)`
becomes `I2C_DEVICESIZE-64 / sizeof(buffer)` = `I2C_DEVICESIZE -
(64/sizeof(buffer))`, not `(I2C_DEVICESIZE-64) / sizeof(buffer)`. This exact
bug was found in `LCC_RPiPico_Turntable` on 2026-06-28: it silently made
`ConfigMemHelper_reset_config_mem()`/`_clear_config_mem()` (the `'r'`/`'c'`
serial commands) loop roughly 32767 times instead of 511, hammering the
same clamped address with rapid-fire writes and producing consistent I2C
Wire timeouts (error code 5). Fixed there and standardized across all four
projects (Turntable, Roundhouse, PixelLights, Clock_Lights) on 2026-07-08.

Reserve **64 bytes** above `CONFIG_MEM_SIZE` for this region (not just the 12
bytes the identity block needs) so future protected items — calibration
constants that shouldn't reset with config, a provisioning/lock flag, a
per-node serial number distinct from the LCC node ID, etc. — have a place to
go without another `CONFIG_MEM_SIZE` shrink and a `NODE_IDENTITY_ADDR`
renumbering. Lay it out as a fixed registry, append-only, each item at a
defined offset/size so the offsets never shift as new items get added:

| Offset (from `CONFIG_MEM_SIZE`) | Size | Item | Status |
|---|---|---|---|
| `+0` | 12 bytes | Node identity block (`node_identity_t` — magic, 6-byte node ID, CRC) | implemented (PixelLights) |
| `+12` | 1 byte | `EEPROM_VERSION` marker — records which layout version last wrote real config-memory defaults (see the `EEPROM_VERSION` gap note below) | implemented (Booster) |
| `+13` | 51 bytes | Reserved for future protected items | unallocated |

**`EEPROM_VERSION` was defined but never actually checked anywhere in this
family until Booster's Phase 2** — worth knowing if working in any other
project here. `BoardSettings.h`'s own comment describes its intended
purpose ("bump it whenever the CDI/struct layout changes, so a stale EEPROM
gets reset to defaults rather than misread"), but `_check_for_nvm_initialization()`
in every existing `.ino` only checks whether config-memory byte 0 is `0xFF`
— it never compares a stored version marker against the firmware's own
`EEPROM_VERSION`. A chip already initialized under an *older, smaller*
`config_mem_t` still passes that "byte 0 isn't blank" check after a firmware
update adds new struct fields, leaving the new fields as uninitialized
leftover bytes rather than real defaults — this is exactly the bug that
surfaced on Booster's own Phase 2 (`+12`'s new marker, above, plus the
matching `_check_for_nvm_initialization()` logic in that project's `.ino`,
is the fix; not yet backported to the other four projects).

When a new protected item is needed, claim the next unused offset, document
it in this table with its status, and shrink the "Reserved" row accordingly.
Never reuse or repack existing offsets — that's what makes the layout safe
to share across a fleet of nodes provisioned at different firmware versions.

**Node identity block structure** (current implementation, validated in
PixelLights — see that project's memory for full design rationale):

```c
// NodeIdentity.h
#define NODE_IDENTITY_MAGIC  0xDEADBEEF
#define NODE_IDENTITY_ADDR   CONFIG_MEM_SIZE  // first address above config space

#pragma pack(push, 1)
typedef struct {
    uint32_t magic;      // NODE_IDENTITY_MAGIC when provisioned
    uint8_t  node_id[6]; // 6-byte big-endian node ID
    uint16_t crc;        // simple XOR checksum over magic + node_id
} node_identity_t;       // 12 bytes
#pragma pack(pop)
```

**Write-then-verify, not write-then-trust**: `NodeIdentity_write()` must not return success based solely on the I2C write call returning — EEPROM chips need a few milliseconds after the transaction to internally commit the page. Since the `'Y'` provisioning command reboots immediately on success, a write that hasn't actually committed yet gets read back as blank/corrupt on the very next boot (observed in practice: first reboot after provisioning came up with the fallback default ID; the second reboot read the correct one). `NodeIdentity_write()` therefore: writes, `delay(20)`, then calls `NodeIdentity_read()` and only returns true if the read-back matches what was written. The `.ino`'s own `delay(100)` before `rp2040.reboot()` is additional margin on top of this, not a substitute for it.

**Startup flow** (replaces a hardcoded `#define NODE_ID`):

```c
uint64_t node_id = NodeIdentity_read();  // reads NVM at NODE_IDENTITY_ADDR
if (node_id == 0) {
    Serial.println("*** Node identity not provisioned in protected NVM ***");
    Serial.println("Using built-in default ID for this boot. Provision a permanent ID with 'N<12-hex-digit-id>' then 'Y' to confirm.");
    node_id = NODE_ID_DEFAULT;   // legacy hardcoded ID this project shipped with previously
}
OpenLcbUserConfig_node_id = OpenLcbConfig_create_node(node_id, &OpenLcbUserConfig_node_parameters);
```

**Deviation from the original design**: the design session this section is
based on called for halting in a `while(true)` loop until provisioned, to
force deliberate provisioning during multi-node batch flashing. The shipped
implementation instead **falls back to a legacy `NODE_ID_DEFAULT` constant
and warns, without halting**. Reason: every existing node in this family
already runs with a real, assigned hardcoded ID — the first boot after this
firmware update would find the identity block unprovisioned (blank EEPROM
region) on every one of them, and halting would silently turn a routine
firmware update into a fleet-wide outage requiring serial intervention on
each node. The warn-and-continue fallback preserves continuity for already-
deployed nodes while still gaining survive-a-wipe protection going forward.
When flashing a *new* batch of boards from one compiled image, give each a
distinct `NODE_ID_DEFAULT` before compiling, or provision each via `'N'`
immediately after first boot — don't rely on the shared fallback ID for more
than one node at a time.

**`'N'` provisioning command** (serial handler, always available — not just
on first boot, so a mis-provisioned node can be corrected without a factory
reset) — two-step with confirmation to prevent accidental node ID changes:

```
N050101019422        → node replies "Confirm with 'Y' to write 05:01:01:01:94:22"
Y                    → node writes identity block, reboots
(anything else)      → cancelled
```

This `'N'` command joins the serial CLI letters in [§11](#11-serial-cli-conventions)
and must not collide with the existing table there.

**NVM survival by storage type**:

| Storage | Survives UF2 reflash? | Survives `picotool` full-chip write? |
|---|---|---|
| External I2C EEPROM/FRAM | Yes — physically separate chip | Yes |
| Internal flash EEPROM emulation | Yes — Arduino EEPROM region excluded from UF2 | No |

**Multi-node flashing workflow**:

1. Compile **once** — the same `.uf2` flashes onto every board in a batch.
2. For each board: BOOTSEL+USB → drag UF2 (or `picotool load`) → board boots
   and prints "NODE ID NOT PROVISIONED" → send `N<nodeid>` → confirm `Y` →
   board writes the identity block and reboots → verify it appears on LCC
   with the correct ID → increment the last byte(s) for the next board.
3. Future firmware updates: flash the new UF2 — the node ID survives, the
   board comes up normally without re-provisioning.

A `provision_nodes.py` script that auto-increments the node ID and sends the
provisioning command to each serial port in sequence is the natural tool to
build once more than a couple of nodes need flashing in one sitting.

**Files to create/modify per codebase**:

- **New**: `NodeIdentity.h` / `NodeIdentity.cpp` — read/write the identity
  block (and any other protected-region items) via the existing NVM driver
- **Modify**: `BoardSettings.h` — reduce `CONFIG_MEM_SIZE` to leave room for
  the protected region
- **Modify**: main `.ino` — replace `#define NODE_ID` with `NodeIdentity_read()`
- **Modify**: serial handler in `loop()` — add the `'N'` command with
  two-step confirm
- **Do not change**: `config_mem_helper.cpp`, the wipe commands, or the
  driver's bounds checks

**Status**: implemented in all four current node projects (Turntable,
Roundhouse, Clock_Lights, PixelLights) as of 2026-06-20. New OpenLcbClib-based
nodes should include this from the start rather than adding it later.

### 7.2 Factory Reset Button Gesture

A hardware equivalent of the `'r'`+`'i'` serial commands: **hold Blue + Gold
together for 2 seconds at boot** to wipe configuration memory and reinitialize
it to CDI defaults — useful when a node has no convenient serial connection
in the field (already installed under a layout, etc.).

**Implementation** (`_check_factory_reset_gesture()` in the `.ino`, called
once in `setup()` right after `OpenLcbConfig_create_node()` and before
`_check_for_nvm_initialization()`):

```c
void _check_factory_reset_gesture(void) {
#if defined(BLUE_BUTTON_PIN) && defined(GOLD_BUTTON_PIN)
  pinMode(BLUE_BUTTON_PIN, INPUT_PULLUP);
  pinMode(GOLD_BUTTON_PIN, INPUT_PULLUP);

  if (digitalRead(BLUE_BUTTON_PIN) != LOW || digitalRead(GOLD_BUTTON_PIN) != LOW) {
    return;  // not held — normal boot
  }

  Serial.println("Blue+Gold held at boot — hold 2s to wipe and reinitialize NVM (release to cancel)...");
  uint32_t startMs = millis();
  while (digitalRead(BLUE_BUTTON_PIN) == LOW && digitalRead(GOLD_BUTTON_PIN) == LOW) {
    if (millis() - startMs >= 2000) {
      Serial.println("Wiping configuration memory to factory defaults...");
      ConfigMemHelper_reset_config_mem();
      ConfigMemHelper_reset_and_write_default(OpenLcbUserConfig_node_id);
      Serial.println("NVM wiped and reinitialized. Continuing boot...");
      return;
    }
    delay(20);
  }
  Serial.println("Released early — factory reset cancelled.");
#endif
}
```

**Design notes**:

- **Active-low, `INPUT_PULLUP`**: buttons are assumed wired as a momentary
  switch to ground, matching how Blue/Gold are described everywhere else in
  this family (§5, §6). No existing project code read these pins before this
  feature, so there was no prior convention to break.
- **2-second hold, not a tap**: a brief press (e.g. accidentally bumping both
  pads while handling the board) must not wipe a configured node. The hold
  loop polls every 20ms and bails immediately on early release, with no
  partial/in-between state.
- **Does not touch the protected identity region**: `ConfigMemHelper_reset_config_mem()`
  and `ConfigMemHelper_reset_and_write_default()` only operate within
  `CONFIG_MEM_SIZE` bounds (§7.1's whole point) — node ID survives this
  gesture exactly like it survives `'r'`/`'i'`.
- **Silently unavailable when the pins are shared away**: on board/breakout
  combos where `BLUE_BUTTON_PIN`/`GOLD_BUTTON_PIN` are reassigned to another
  function (e.g. Turntable's v3.0 combos share `BLUE_BUTTON_PIN` with
  `STEPPER_DIR_PIN`, and the parallel-display combo shares `GOLD_BUTTON_PIN`
  with `DISPLAY_DC_PIN` — see §6.1), the macros are still `#define`d (just
  pointing at a repurposed pin), so the `#if defined(...)` guard does not
  actually skip the gesture on these combos today. Holding the underlying pins
  low during boot on such a combo will still trigger the wipe, and doing so
  may also interfere with whatever the breakout is doing with that pin at
  power-up. **Don't rely on this gesture being safe to use on a combo where
  Blue/Gold are documented as "unavailable"** — it works mechanically but
  isn't a clean button press in that case.
- **Repurposing Blue/Gold for a node's own signals is fine, with one
  ordering rule**: `gp5`/`gp28` only need to *be* Blue/Gold for the brief
  window `_check_factory_reset_gesture()` runs — called once, at the very
  start of `setup()`, before anything else touches those pins. Once it
  returns (held-both/held-one branches to reset handling; otherwise normal
  init proceeds), both pins are free to repurpose for the node's own
  signals, same as any other GPIO. **The only rule is ordering**: any
  repurposed use of `gp5`/`gp28` must happen *after* the gesture check
  returns, not before — initializing them for another role first would make
  the reset gesture unreliable. This is a different (and generally
  preferable, when the pin budget is tight) choice than giving up the
  button entirely and documenting the pin as "unavailable" (§6.1's
  `MAIN_nFAULT`/`RAILCOM_RX_PIN` on `LCC_RPiPico_CommandStation` do this) —
  both are valid, pick whichever fits the node; this bullet just makes
  explicit what was previously only implicit.

**Status**: implemented in all four current node projects as of 2026-06-21.

### 7.3 SNIP Identity Fields (`hardware_version` / `software_version`)

`openlcb_user_config.c`'s `node_parameters_t.snip` fields are the node's
self-reported identity over LCC (SNIP = Simple Node Information Protocol).
Two of the four fields were being hand-maintained and had already drifted
from reality in every one of the four projects (stale `hardware_version`
strings left over from a previous board revision, and `CDI.xml`'s
identification block disagreeing with the `.snip` values it should mirror —
two projects still had it at its original `MANU`/`MODEL` placeholder). Fixed
per the convention below as of Rev 14.

- **`hardware_version`** is derived, never hand-typed. Each project's
  `BoardSettings.h`, right next to its `#if defined(LCC_BOARD_*)` board
  dispatch, defines a matching `BOARD_HARDWARE_VERSION_STR`:
  ```c
  #if defined(LCC_BOARD_NODE_V25)
    #define BOARD_HARDWARE_VERSION_STR "2.5"
  #elif defined(LCC_BOARD_NODE_V26)
    #define BOARD_HARDWARE_VERSION_STR "2.6"
  ...
  #elif defined(LCC_BOARD_NODE_V30)
    #define BOARD_HARDWARE_VERSION_STR "3.0"
  #endif
  ```
  `openlcb_user_config.c` then just does
  `.snip.hardware_version = BOARD_HARDWARE_VERSION_STR,` — it is now
  physically impossible for this field to disagree with the board macro
  actually selected in `ProjectConfig.h`. (Known gap: this does not yet
  distinguish v3.0 breakout/display *combo* variants from each other, e.g.
  the SPI-display vs parallel-display Turntable builds — if that distinction
  ever needs to show up in `hardware_version`, extend the string in
  `NodeConfig.h` after this macro is defined, don't hand-edit the result.)
- **`software_version`** is composed as `"<LCC_NODE_STANDARD_REVISION>.<patch>"`
  using `LCC_NODE_STANDARD_REVISION_STR` from the new
  `LCC_RPiPico_Common/StandardVersion.h`:
  ```c
  .snip.software_version = LCC_NODE_STANDARD_REVISION_STR ".1",  // patch 1 against this revision
  ```
  `<patch>` is a plain per-project literal, bumped by that project whenever
  it re-releases without the standard itself having changed. Bump
  `LCC_NODE_STANDARD_REVISION`/`_STR` in `StandardVersion.h` by exactly one
  for every row added to §13's changelog (the two are meant to stay
  1:1 — see the note at the top of §13); a project picking up a new
  revision resets its own patch counter back to 1.
- **`CDI.xml` must mirror both**: since `_cdi_data[]` is a compiled byte
  array (§7's "Regenerating the CDI byte array" bullet above), the human-
  readable `<manufacturer>/<model>/<hardwareVersion>/<softwareVersion>` in
  `CDI.xml`'s `<identification>` block do not update themselves. Any time
  `.snip.name/model/hardware_version/software_version` changes (including
  just a routine `software_version` patch bump), update `CDI.xml` to match
  and rerun `cdi_to_c_array.py` — an easy step to forget since nothing
  fails to compile if you don't.
- Canonical `manufacturer`/`model` values as of this revision (previously
  inconsistent across projects — e.g. `"Gamble"` vs `"Bob Gamble"`,
  `"Roundhouse"` vs `"Roundhouse Controller"`): manufacturer is `"Gamble"`
  everywhere; model is each project's own descriptive name (`"Turntable
  Controller"`, `"Roundhouse Controller"`, `"Lighting Controller"`,
  `"Fastclock & Lights"`).

## 8. Dual-Core Contract

- **Core 0** (`setup()`/`loop()`): OpenLCB protocol, CAN comms, event
  consumer/producer handling, serial CLI, UI rendering/touch. This is the
  *only* core that talks to the LCC bus or touches CAN.
- **Core 1** (`setup1()`/`loop1()`): timing-critical, non-blocking actuation
  only — stepper stepping (Turntable), servo polling (Roundhouse). Core 1
  must never block on `delay()`, EEPROM I/O, or CAN traffic.
- **Handshake pattern** (Roundhouse): `setup1()` delays briefly then sets
  `setup1Complete = true`; Core 0 spins on `while(!setup1Complete)` before
  registering consumers/producers; Core 1 then waits on `node_initiated`
  before entering `loop1()`. New nodes with a Core 1 actuation loop should
  use this same two-flag handshake rather than inventing a new
  synchronization scheme.
- Cross-core communication is via plain flags/structs (e.g.
  `_pending_door_pcer[]`), not queues or locks — keep it that simple unless
  a node has a concrete reason to need more.
- All motor/LED/calibration logic must be non-blocking — `millis()`-based
  timers only, never `delay()`, on either core.

## 9. Naming Conventions

Consistent across all four current projects:

- Functions: `camelCase` (`moveToPosition`, `driveServos`); `PascalCase` is
  acceptable for a deliberately "public API" surface (`RoundhouseCallback`)
- Global variables: `camelCase` or `snake_case` — either is fine, don't mix
  within one variable's call sites
- Structs/typedefs: `PascalCase` (`TrackAddress`, `ServoAddress`, `npHead`)
- Constants/`#define`s: `UPPER_SNAKE_CASE`
- Board macros: `LCC_BOARD_<FAMILY>_V<NN>` (§4)
- Pin defines: `<FUNCTION>_PIN` or `<BUS>_<SIGNAL>` (`STEPPER_ENABLE_PIN`,
  `MCP2517_CS`, `IO1_PIN3`) — connector-relative names (`IOx_PINy`) only in
  `board_configs/`; functional names everywhere else

## 10. OpenLCB Integration Rules

- The OpenLCB stack (`src/openlcb/`, `src/drivers/canbus/`) is the vendored
  MustangPeak `OpenLcbClib` C library. **Do not modify files under `src/`.**
  If stock behavior needs to change, do it at the call site in `callbacks.cpp`
  or the node's own code, not inside the library.
- All consumer/producer registration and LCC event dispatch happens in
  `callbacks.cpp`/`.h` — this is the single integration seam between the LCC
  network and node-specific logic. Node logic files (`Turntable.cpp`,
  `Roundhouse.cpp`, etc.) should not call into `src/openlcb/` directly;
  they're driven by `callbacks.cpp`, and they report state changes back to
  it (e.g. via pending-PCER flags) rather than sending events themselves.
- The 100ms timer is the standard heartbeat for periodic work (PCER flushes,
  deferred EEPROM writes) — reuse it rather than adding a second timer if the
  cadence fits.

## 11. Serial CLI Conventions

Common debug command letters used across projects' `loop()` serial CLI —
keep these consistent and don't repurpose them for node-specific commands:

| Key | Action |
|---|---|
| `c` | Clear NVM |
| `i` | Reset to CDI defaults |
| `r` | Factory reset |
| `p` | Toggle message logging |
| `m` | Toggle config memory logging |
| `x` | Load app defaults |
| `z` | Re-apply config values from NVM |
| `N` | Provision/re-provision node identity block (see [§7.1](#71-protected-nvm-region-above-config_mem_size)) — two-step with `Y` confirm |

Node-specific commands (e.g. Roundhouse's `t`/`q` for fast-clock query) are
fine to add — just don't collide with the table above, and document new
ones in the project's own `CLAUDE.md`.

`mdebugging.h` provides the `dP()`/`dPH()`/`dPS()` family, gated on whether
`DEBUG` is `#define`d to a `Stream` (e.g. `Serial`); compiled to no-ops
otherwise. Copy this file verbatim into new projects rather than reimplementing
debug printing.

## 12. Per-Project CLAUDE.md Template

New node repos should start their `CLAUDE.md` from this skeleton, filling in
only what's specific to that node:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code when working with code in this
repository. See [LCC_NODE_STANDARD.md](../LCC_RPiPico_Common/LCC_NODE_STANDARD.md)
for cross-project conventions (toolchain, board versioning, dual-core
contract, CDI/EEPROM handling, naming). This file documents only what is
specific to this node.

## Build Environment
- Board family/revision in use: <LCC_BOARD_..._V..>
- Project-specific libraries beyond the family standard (if any)

## Architecture
This is an OpenLCB (LCC) node that <one-line purpose>.

### Key Module Responsibilities
| File | Role |
|---|---|
| ... | ... |

### Key Data Flow
1. ...

### Important Implementation Notes
- <anything surprising/non-obvious specific to this node>
```

## 13. Change Log

Each row bumps `LCC_NODE_STANDARD_REVISION` in `StandardVersion.h` by one — see §7.3. The Rev column is that revision number, assigned retroactively for rows before it existed.

| Rev | Date | Change |
|---|---|---|
| 1 | 2026-06-20 | Initial version, derived from Turntable, Roundhouse, Clock_Lights, PixelLights as they exist today |
| 2 | 2026-06-20 | Added §7.1 protected NVM region: node identity block design (from PixelLights design session) plus reserved headroom and an offset registry for future persistent items |
| 3 | 2026-06-20 | Added v3.0 generic node + breakout-pinout tables (§6.1); marked `STEPPER` family legacy/frozen in §4; cleaned up table formatting and a duplicated pin entry — ragged v2.5–v3.0 I/O-2/I/O-3 table cells in §5 still need correct values filled in |
| 4 | 2026-06-20 | `board_configs/BoardPins_Node_v30.h` added to all four projects (CONFIG_MEM_SIZE shrunk to 32704 to fit §7.1's protected region). Protected NVM identity block (§7.1) implemented in all four projects, with one deviation from the original design — warn-and-fallback instead of halt-on-unprovisioned, documented in §7.1. Turntable's v3.0 SPI-display + TMC2209 breakout combo implemented in `NodeConfig.h`. |
| 5 | 2026-06-20 | Corrected the §6.1 Parallel Display — Capacitive Touch breakout table: D_D/C and VREF were transposed on I/O-3 Pin4/Pin5 in the original breakout design (confirmed by the breakout's designer). Table and Turntable's `NodeConfig.h`/`display_configs/DisplayConfig_SSD1963_parallel_v30.h` now match the corrected wiring; the parallel-display combo (`TURNTABLE_BREAKOUT_PARALLEL_TMC2209`) is implemented and no longer blocked. |
| 6 | 2026-06-20 | Fixed `board_configs/BoardPins_Node_v30.h` in all four projects: the header comment and `IO1_PIN5/PIN6`/`IO2_PIN5/PIN6` sentinel assignments had Pin5/Pin6 backwards (claimed Pin5=VCC, Pin6=GND). Confirmed against the hardware repo's "LCC Pico Board Overview" doc: Pin5=GND, Pin6=Vselect (jumper-selectable 3.3V/5V). `LCC-RPi-Pico-Board` README's pin table already matched the correct convention. |
| 7 | 2026-07-08 | Standardized `CONFIG_MEM_SIZE` definition (§7.1) across all four projects to `#define CONFIG_MEM_SIZE (I2C_DEVICESIZE-64)` — a formula off `I2C_DEVICESIZE` instead of a separately-maintained literal. Parentheses are required (see §7.1 for the exact precedence bug this avoids, found in Turntable on 2026-06-28). Roundhouse and PixelLights switched from `LCC_BOARD_NODE_V28` to `LCC_BOARD_NODE_V30` for final v3.0 hardware testing; Roundhouse's `board_configs/BoardPins_Node_v30.h` gained the functional pin assignments (servo I2C on gp16/17, NeoPixel outputs left `UNUSED_PIN` as future scaffolding) it was missing — this project has no `NodeConfig.h` layer, so functional pins live directly in the board header, unlike Turntable/PixelLights/Clock_Lights. |
| 8 | 2026-06-21 | First hardware test of v3.0 (Clock_Lights). Fixed a `case 't':` switch-scope compile error introduced by §7.1's `'N'`/`'Y'` cases in Roundhouse/PixelLights/Clock_Lights (Turntable unaffected — no `case 't':` there); added the missing `NodeConfig.h` functional pin layer for Clock_Lights on v3.0 (carried over from `BoardPins_Node_v295.h` — display/touch/NeoPixel pins are unchanged between v2.95 and v3.0); hardened `NodeIdentity_write()` with a post-write `delay(20)` + read-back verification after observing a real EEPROM write-settling issue (first reboot after provisioning came up with the fallback default ID, second reboot read correctly). |
| 9 | 2026-06-21 | Turntable v3.0 SPI+TMC2209 bring-up: fixed `TOUCH_INT` in `NodeConfig.h` to use `-1` (the touch library's own "not connected" sentinel) instead of `UNUSED_PIN`(127) — `my_bb_captouch.cpp`'s GT911 sleep/wake path checks `_iINT != -1` specifically and would otherwise drive a nonexistent GPIO 127. Found and fixed a real hang/memory-corruption bug in `Set_Application_Values_From_Config()` (`config_mem_helper.cpp`): `TrackCount`/`DoorCount` were read from NVM with no bounds check and used directly as loop bounds/array indices into the fixed-size `Tracks[MAX_TRACKS]`/`doors[MAX_DOORS]` arrays — stale/incompatible NVM data caused an out-of-bounds write that hung the node during `setup1()`. Both counts are now clamped to their array bounds before use. |
| 10 | 2026-06-21 | Added §7.2 Factory Reset Button Gesture: hold Blue+Gold for 2s at boot to wipe and reinitialize config memory (does not touch the §7.1 protected identity region). Implemented identically in all four projects via a new `_check_factory_reset_gesture()` called from `setup()`. Flagged a real caveat: the `#if defined(...)` guard does not actually skip the gesture on combos where Blue/Gold are reassigned to another function, since the macros stay defined either way — don't rely on it being safe to use on such combos. |
| 11 | 2026-06-21 | Diagnosed Turntable v3.0 SPI+TMC2209 "blank screen" bug: `TOUCH_RST`/`DISPLAY_RST` share a physical pin on the SPI Display — Capacitive Touch breakout (§6.1), and the touch library's chip-type auto-detection resets that shared pin — silently resetting the display controller back to power-on defaults *after* `tft.init()` already configured it, with nothing re-applying that config afterward. Fixed in `UserInterface.cpp`'s `setupDisplay()` by re-running `tft.init()`/`setRotation()` right after `tp.init()` whenever the pins are shared. Documented as a gotcha under §6.1's SPI Display table for any future combo sharing these pins. |
| 12 | 2026-06-21 | Diagnosed a second Turntable v3.0 display bug, visible only after the above fix: stray CDI-XML-looking text appeared during the homing animation (not at the initial page draw, as first assumed). Four theories tried and disproven in sequence (scroll margins; unverified `fillScreen()`; unclamped `TrackCount` in `drawTracks()`; network/CAN crosstalk — invalidated immediately since the test node had no CAN connection at all) before the timing detail (appears after home page drawn, before homing completes) pointed at `drawBridge()`, called repeatedly from Core 0's `updateBridgeAnimation()` during homing. Real root cause: `drawBridge()` indexes `TrackName[ConfigMemHelper_config_data.CurrentTrack]` with no bounds check; `CurrentTrack` is a top-level `config_mem_t` field (not under `.attributes`), so none of the `_load_defaults_*` functions ever set it, leaving it at the post-`'r'`-wipe value of 255 after an `'i'` reset — 6375 bytes past the 20-entry flash-resident `TrackName[]` array, landing close enough to the embedded `_cdi_data[]` (also const/flash) to render genuine CDI text. Fixed: explicit default in `_load_defaults_attributes()`, clamp in `ConfigMemHelper_read()`, belt-and-suspenders clamp at the `drawBridge()` call site. Documented the full four-theory misdiagnosis under §6.1, with the general lesson that top-level (non-CDI) fields used as array indices are easy to miss precisely because no CDI/JMRI validation ever touches them. |
| 13 | 2026-07-11 | Added `cdi_to_c_array.py` to this directory and documented it under §7 — a standalone port of `cdi_fdi_wizard.html`'s "Array" tab codegen (`_xmlToByteRows`/`renderByteArray` from the tool's own `cdi_editor/cdi_view.html` and `js/c_target.js`), verified byte-for-byte identical against the browser tool's output on both Turntable's and Roundhouse's paired-door-events CDI.xml. Lets `_cdi_data[]` in `openlcb_user_config.c` be regenerated/checked against `CDI.xml` without the browser tool. |
| 14 | 2026-07-11 | Added §7.3 SNIP identity fields convention: `hardware_version` now derives from a `BOARD_HARDWARE_VERSION_STR` macro tied to the selected `LCC_BOARD_*` macro (defined per project in `BoardSettings.h`, next to the board dispatch) instead of being hand-maintained — eliminates a real, already-observed drift bug (all four projects' `.snip.hardware_version` and/or `CDI.xml`'s `<hardwareVersion>` had gone stale relative to the actual `LCC_BOARD_NODE_V30` in use, and two projects still had literal `MANU`/`MODEL` placeholders in `CDI.xml`). `software_version` now composed as `"<LCC_NODE_STANDARD_REVISION>.<patch>"` via the new `LCC_RPiPico_Common/StandardVersion.h`; this changelog's Rev column is that revision number. `CDI.xml`'s `<manufacturer>/<model>/<hardwareVersion>/<softwareVersion>` must mirror `.snip.name/model/hardware_version/software_version` exactly — since the CDI is a compiled byte array, changing any of these requires updating `CDI.xml` and rerunning `cdi_to_c_array.py`. Fixed the pre-existing drift in all four projects as part of adopting this. |
| 15 | 2026-08-14 | Added `LCC_RPiPico_CommandStation` and `LCC_RPiPico_Booster` to the "Current node projects" list — both are real repos now (design-stage/early-hardware-bringup, not yet at LCC/CAN integration), added as its own edit per each project's own `work_plan.md` cross-repo-housekeeping item rather than bundled into an unrelated commit. Neither has reached the implementation phases §7–§7.3 govern yet — flagged inline in the project list rather than assumed compliant. |
| 16 | 2026-08-14 | Added a §7.2 clarification, found during `LCC_RPiPico_Booster`'s Phase 0 pin-mapping session: `gp5`/`gp28` (Blue/Gold) only need to be the reset-gesture buttons for the brief window `_check_factory_reset_gesture()` runs at the very start of `setup()` — after it returns, both pins are free to repurpose for a node's own signals, provided that repurposed use happens *after* the check, not before. Previously only implicit (existing projects that share these pins away, like `LCC_RPiPico_CommandStation`'s `MAIN_nFAULT`/`RAILCOM_RX_PIN`, instead just give the button up entirely and mark it "unavailable") — now stated as an explicit, equally-valid alternative. |
| 17 | 2026-08-14 | Added §7.1 registry entry `+12`: a 1-byte `EEPROM_VERSION` marker in the protected NVM region. Found during `LCC_RPiPico_Booster`'s Phase 2: `EEPROM_VERSION` was defined in every project's `BoardSettings.h` with a comment describing its intended purpose, but no project's `_check_for_nvm_initialization()` actually checked it — only "is config-memory byte 0 blank" was checked, which a chip already initialized under an older, smaller `config_mem_t` still passes after a firmware update adds new struct fields, leaving the new fields as uninitialized leftover bytes. Fixed in Booster (marker + updated `_check_for_nvm_initialization()`); not yet backported to the other four projects. |
