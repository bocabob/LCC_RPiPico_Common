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
`LCC_RPiPico_Clock_Lights`, `LCC_RPiPico_PixelLights`.

---

## Index

1. [Purpose & Scope](#1-purpose--scope)
2. [Fixed Toolchain & Libraries](#2-fixed-toolchain--libraries)
3. [Reference Node Architecture](#3-reference-node-architecture)
4. [Board Versioning Convention](#4-board-versioning-convention)
5. [Pin Assignment Registry](#5-pin-assignment-registry)
6. [Breakout Board Catalog](#6-breakout-board-catalog)
7. [Configuration Memory (CDI/EEPROM) Conventions](#7-configuration-memory-cdieeprom-conventions)
8. [Dual-Core Contract](#8-dual-core-contract)
9. [Naming Conventions](#9-naming-conventions)
10. [OpenLCB Integration Rules](#10-openlcb-integration-rules)
11. [Serial CLI Conventions](#11-serial-cli-conventions)
12. [Per-Project CLAUDE.md Template](#12-per-project-claudemd-template)
13. [Change Log](#13-change-log)

---

## 1. Purpose & Scope

Every node in this family shares one base hardware platform (the RPi Pico
"Node board," currently at revisions v2.5–v2.95) plus a swappable breakout
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
  the breakout combination (`NODE` for the generic node board with no
  dedicated breakout, `STEPPER` for Node board + TMC2209/stepper breakout,
  and so on as new families are added), and `<NN>` is the board revision
  (`25`, `26`, `27`, `28`, `29`, `295` for v2.95).
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

| Function | v2.5 | v2.6 | v2.7 | v2.8 | v2.9 |
|---|---|---|---|---|---|
| CAN (MCP2517/18, SPI) | gp16-20 | gp16-20 | gp16-20 | gp0-4 | gp0-4 |
| I2C storage (EEPROM) | I2C1 gp26/27 | gp26/27 | — | I2C1 gp6/7 | I2C1 gp6/7 |
| Secondary I2C | — | — | — | I2C0 gp16/17 | — |
| Dedicated NeoPixel pins | gp2/3/6/7 | gp2/3/6/7 | none (I/O headers only) | none | none |
| Dedicated servo pins | — | — | — | — | none (v2.9 removed) |
| Buttons (Blue/Gold) | gp21/gp22 | gp21/gp22 | gp21/gp22 | gp21/gp22 | gp21/gp22 (shared w/ IO2 pins 8/9) |

> Fill in v2.5–v2.8 columns from each board's `BoardPins_Node_v*.h` as they're
> revisited; v2.9 is current as of this writing (see
> `LCC_RPiPico_PixelLights/board_configs/BoardPins_Node_v29.h`).

### Stepper family (Node board + stepper breakout)

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
- `<manufacturer>`/`<model>` fields in `CDI.xml` are currently placeholder
  (`MANU`/`MODEL`) — fill in per node before any CDI XML is finalized for a
  real deployment; `<hardwareVersion>` should track the `LCC_BOARD_*` macro
  in use.
- Storage backend selection (`USE_I2C_STORAGE` vs `USE_INTERNAL_FLASH_STORAGE`,
  `EXTERNAL_EEPROM` vs `EXTERNAL_FRAM`, `USE_TILLAART` vs Adafruit) lives in
  `BoardSettings.h` next to the board dispatch — keep this block in sync
  across projects unless a node has a specific reason to diverge.

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

| Date | Change |
|---|---|
| 2026-06-20 | Initial version, derived from Turntable, Roundhouse, Clock_Lights, PixelLights as they exist today |
