# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

**Start with [`README.md`](README.md).** It's the entry point for everything in this
repo — an overview of the two bodies of work here (the Node Standard and the
EventScript Architecture), how they relate, and where to go next for each.

## If you're doing Node Standard work

Read [`LCC_NODE_STANDARD.md`](LCC_NODE_STANDARD.md) — the cross-project source of
truth for hardware/board conventions, file layout, the dual-core contract,
CDI/EEPROM handling, and naming, referenced by every `LCC_RPiPico_*` node repo's own
`CLAUDE.md`. Its §13 changelog is the append-only record of every change to the
standard to date; keep it in sync with `StandardVersion.h` (§7.3, §13's header note).

## If you're doing EventScript work

Read the four documents in this order — each builds on the last, and skipping ahead
will leave you missing context the later documents assume:

1. [`lcc_event_script_architecture.md`](lcc_event_script_architecture.md) — the why
   and the shape: language/VM choice rationale, execution model, NVM layout, loading
   transport, event binding model, the M1–M8 roadmap, open risks, and §8's external-
   coordination contracts.
2. [`eventscript_spec.md`](eventscript_spec.md) — the language itself: lexical rules,
   grammar, execution semantics, the bytecode ISA and slot image format, limits, and
   compile-error categories. Check its header changelog first — it's the coordination
   channel for in-flight spec changes until the v1.0 freeze.
3. [`eventscript_examples.md`](eventscript_examples.md) — worked programs with
   binding tables and behavior notes that become M2's golden tests.
4. [`eventscript_cdi_sketch.md`](eventscript_cdi_sketch.md) — pinned byte layouts for
   the config-space slot structure, the status/monitor space, the CDI XML skeleton,
   and the firmware-hook checklist.

`lcc_event_script_architecture_1.md` is a superseded earlier draft, kept for history
— don't read it for current design intent; use document 1 above instead.

M1 (design) is complete; M2 (host-side compiler + VM, no hardware) is next — see
architecture doc §6 for the full roadmap.
