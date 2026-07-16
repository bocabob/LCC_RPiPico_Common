# LCC_RPiPico_Common

Shared foundation for a family of custom LCC (OpenLCB / NMRA S-9.7) node projects
built on Raspberry Pi Pico hardware. This repository is the standing context for
Claude Code sessions across all node projects, and it holds two distinct but related
bodies of work:

1. **The Node Standard** — the platform: how every node in the fleet is built.
2. **The EventScript Architecture** — an embedded scripting engine layered on that
   platform, currently in design (milestone M1 complete).

Everything else in a given node project is specific to that node; anything two nodes
share belongs here.

---

## 1. The Node Standard

The common platform every node firmware follows — full detail in
[`LCC_NODE_STANDARD.md`](LCC_NODE_STANDARD.md):

- **Hardware**: Raspberry Pi Pico (RP2040) and Pico 2 (RP2350) boards, custom carrier
  PCBs designed in KiCad 8 (confirmed from the `.kicad_pcb` file-format version stamped
  in the [`LCC-RPi-Pico-Board`](https://github.com/bocabob/LCC-RPi-Pico-Board) hardware
  repo) targeting JLCPCB fabrication/assembly, with a CAN transceiver (ACAN2517 driving
  an MCP2517/18) for the LCC bus, onboard QSPI flash, and external I2C EEPROM or FRAM
  for configuration storage (§2, §6).
- **Protocol stack**: OpenLcbCLib, vendored under `src/openlcb/`/`src/drivers/canbus/`
  and never modified in place (§10); non-blocking and driven entirely from Core 0's
  `setup()`/`loop()` (§8) — no RTOS, no blocking calls on the LCC-facing core. Nodes
  implement event production/consumption through the single integration seam in
  `callbacks.cpp` (§10), and CDI-described configuration edited via standard Memory
  Configuration datagrams (JMRI-compatible, §7). ACDI identification is the library's
  own fixed default (`<acdi/>` in every `CDI.xml`); SNIP identification
  (`manufacturer`/`model`/`hardware_version`/`software_version`) is *not* a library
  default — it follows the fleet's own derivation/composition convention in §7.3.
- **Configuration & NVM**: node parameters live in configuration space 0xFD backed by
  NVM (§7). EEPROM part selection defaults to a 24LC256 (32KB, `I2C_DEVICESIZE`), with
  other Microchip 24LCxxx sizes selectable per project; `CONFIG_MEM_SIZE` is always
  derived as `I2C_DEVICESIZE-64`, never a separate hardcoded literal (§7.1). Node ID
  assignment lives in a **protected NVM region** above `CONFIG_MEM_SIZE`, immune to the
  `'c'`/`'r'` config wipes and to `EEPROM_VERSION` bumps: a 12-byte node-identity block
  (magic + 6-byte node ID + CRC) at offset `+0`, provisioned/re-provisioned via the
  serial `'N'<id>` / `'Y'`-confirm command pair, with 52 bytes reserved for future
  protected items (§7.1's offset registry). An unprovisioned node falls back to a
  legacy default ID with a warning rather than halting (§7.1).
- **Conventions for Claude Code**: start at this repo's own
  [`CLAUDE.md`](CLAUDE.md), which indexes both bodies of work below. For Node Standard
  work, read [`LCC_NODE_STANDARD.md`](LCC_NODE_STANDARD.md) — the cross-project source
  of truth for board/hardware conventions, file layout, the dual-core contract,
  CDI/EEPROM handling, and naming (its own §12 gives the template every per-project
  `CLAUDE.md` should follow, and its §13 changelog is the append-only record of every
  standard change to date). Per-project `CLAUDE.md` files (in each `LCC_RPiPico_*`
  repo) document only what's specific to that node and link back here rather than
  restate these rules. For EventScript work, see the document set and read order in
  §2 below.

In short: the Node Standard defines what it means to be "one of these nodes" —
a firmware built on this stack, configured this way, on this class of hardware.

## 2. The EventScript Architecture

EventScript adds user programmability to nodes built on the Node Standard: a small
procedural language whose programs live in the node's NVM, are edited live through any
generic CDI tool (JMRI textareas, standard datagram writes — no custom tooling, no
firmware reflash), are compiled **on the node** to bytecode, and treat **LCC events as
the primary inputs and outputs**. Conceptual prior art is the RR-CirKits Tower LCC+Q
STL Logic Engine; EventScript matches its CDI-only workflow while replacing S7-style
STL with a hobbyist-readable structured language and making events, timers, and the
fast clock first-class.

Key design commitments: a ~31-opcode stack VM with per-slice instruction budgets so
user code can never starve the CAN stack; coroutine handlers (`on event`, `on
startup`, `every`, `at HH:MM`) with `wait`/`timeout` suspension; 8 independent 2 KB
program slots with per-slot fault isolation; event and parameter binding through CDI
tables (names in code, IDs in tables — preserving JMRI's event-learn workflow and
correct Producer/Consumer Identified reporting); retained and exported variables; a
local consumer clock as fast-time source of truth; and a portable C99 core behind a
five-touchpoint contract with OpenLcbCLib, targeting RP2040/RP2350 today and
ESP32-class parts and host builds tomorrow.

### Document set (read in this order)

| Document | Contents |
|---|---|
| `lcc_event_script_architecture.md` | The why and the shape: language/VM choice rationale, execution model, NVM layout, loading transport, event binding model, the M1–M8 roadmap, open risks, and §8's external-coordination contracts (OpenLcbCLib integration touchpoints; JMRI node-as-validator tooling model). |
| `eventscript_spec.md` | The language itself, v0.4: lexical rules, EBNF grammar, execution semantics (handlers, latch, wait/resume, faults, fast clock, parameters/exports), the bytecode ISA and slot image format, limits, and compile-error categories. The changelog in its header is the coordination channel until the v1.0 freeze. |
| `eventscript_examples.md` | Six worked programs (crossing gate, ABS signal, turnout interlock, route dispatcher, startup restoration, fast-clock town) with binding tables, behavior notes that become M2 golden tests, and a feature-coverage matrix. Includes one intentional compile error. |
| `eventscript_cdi_sketch.md` | Pinned byte layouts: config space 0xFD slot structure with offsets and backend-dependent strides, the read-only status/monitor space 0x50 (including engine/language version bytes), the CDI XML skeleton, and the firmware-hook checklist for OpenLcbCLib integration. |

### Status and next step

M1 (design) is complete. Next is **M2**: the host-side compiler and VM in portable C
with a CLI test harness — no hardware involved — using the spec's §9 error categories
and the example library as the initial test matrix. Development may proceed as a
portable extension to OpenLcbCLib or integrated with it (in coordination with the
library's author); the JMRI project has expressed interest in an EventScript editor
once the language reaches its v1.0 freeze (architecture doc §8, roadmap M7).

## How the two relate

The Node Standard is the platform; EventScript is an optional engine a node firmware
links in. EventScript deliberately consumes only what the standard already provides —
event callbacks, CDI/memory-configuration handling, NVM access, a timer tick — through
the explicit contract in architecture §8, so a node without EventScript loses nothing,
and a node with it remains a fully conventional citizen of the standard (same CDI
editing, same event semantics, same tools). Changes to the Node Standard that touch
those contract points should be checked against architecture §8 before landing.
