# Prompt for Fable: LCC Node Embedded Scripting Interpreter — Architecture

Paste everything below the line into Fable as a single message. It's written to get one
thorough architecture document back rather than a multi-turn interview, since the goal is
a reference you can carry into Claude Code afterward.

---

## Context

I build custom LCC (OpenLCB / NMRA S-9.7) nodes on Raspberry Pi Pico boards (RP2040 and
RP2350) using **OpenLcbCLib** as the protocol stack. My nodes already handle event
production/consumption, CDI-based configuration, and NVM storage (onboard flash and/or
external I2C EEPROM/FRAM). I do the implementation myself in Claude Code over many
sessions — what I need from you right now is a design, not code.

**Prior art I want you to reason against explicitly:** RR-CirKits' Tower LCC+Q is a
16-line LCC I/O node with a built-in "Logic Engine" that runs a Statement List (STL)
language — a subset of Siemens S7-x. The STL logic is authored entirely inside the CDI:
16 logic groups, each holding a 256-character "MultiLine" of text (4,096 characters of
logic total across the node), edited live through a JMRI CDI tool and stored in the
node's own NVM. It's proof that a real, deployed LCC node can host a live interpreter
driven entirely by CDI-resident text with no separate firmware compile step. I want to
match or exceed that capability but with events as first-class inputs/outputs to the
language rather than just line state, and via MicroPython-like or BASIC-like syntax
instead of an S7 dialect, since that's more approachable for the layout-building
audience I'd be supporting.

## Goal

Design an architecture for embedding a small interpreter into LCC node firmware
(RP2040/RP2350, OpenLcbCLib) such that:

- User-authored programs live in NVM and persist across power cycles and reboots.
- Programs can be loaded/updated over the LCC network — via datagrams, CDI memory-access
  writes, a stream transfer, or whatever combination makes sense — without reflashing
  firmware.
- Programs are procedural (sequential statements, loops, conditionals, variables), not
  declarative ladder logic.
- LCC Events are the primary I/O surface: received events are how the outside world
  drives inputs into a running program; a program calling something like `produce(event)`
  is how it acts on the world. Local GPIO/sensor access should also be possible, but
  events are the design center.
- The language is something a hobbyist could plausibly read and write — a constrained
  subset of MicroPython or BASIC, or a small custom language if you think that's the
  better call given the constraints.

## What I want from you

Work through the following and produce one structured architecture document. Where a
question has a genuinely close tradeoff, give me your recommendation with reasoning
rather than just listing options — I can push back on specific calls, but I'd rather
start from a stated position than a menu.

1. **Language / VM choice.** Compare realistic candidates given RP2040 (264KB SRAM,
   typically 2MB flash) and RP2350 (520KB SRAM) constraints: a MicroPython subset (e.g.
   trimming an existing tiny Python VM vs. writing a minimal one), a tiny BASIC dialect,
   a Forth-style threaded-code VM, or a small custom bytecode VM/language purpose-built
   for event-driven procedural logic. Consider flash/RAM footprint, determinism of
   execution time, ease of writing a byte-code compiler that could run on-device or
   host-side, and how each maps naturally onto "wait for event," "produce event,"
   "read/write variable" primitives. Name existing open-source implementations worth
   adapting rather than writing from scratch, if any fit.

2. **Execution model.** How the interpreter integrates with OpenLcbCLib's event callback
   flow — interrupt-context event arrival feeding a cooperative interpreter loop vs. a
   polling model, how a program blocks/resumes waiting on an event, watchdog/runaway-loop
   protection, and what happens to in-flight state across a node reboot.

3. **NVM layout.** How script storage coexists with existing CDI-configured node
   parameters and OpenLcbCLib's own NVM usage — segment layout, versioning/checksums,
   size budget per program, and whether multiple independent programs (e.g. per your
   "primary inputs and outputs" model, maybe one program per logical device or one big
   program) make more sense.

4. **Loading/transport mechanism.** How a program actually gets from a PC/JMRI tool onto
   the node: LCC's Configuration Memory Access datagram protocol (as CDI editing already
   uses), a custom datagram type, the Stream protocol for larger payloads, or CDI string
   elements a la Tower LCC+Q's MultiLines. Weigh against the Tower LCC+Q approach
   specifically — what it gets right for a CDI-only, tool-friendly workflow, and where a
   datagram/stream approach would do better for a more expressive language.

5. **Event binding model.** How the language names and binds to specific 64-bit Event
   IDs — variable-to-event mapping, whether binding is done in the script text itself or
   via separate CDI event-learn fields referenced by the script (matching how LCC nodes
   normally expose event configuration for learning/binding in JMRI).

6. **Phased development roadmap for Claude Code.** Break the build into milestones I
   could work through incrementally over many Claude Code sessions — e.g. language/opcode
   spec, host-side interpreter + test harness before touching hardware, OpenLcbCLib event
   hook integration, NVM storage, datagram/CDI loading path, CDI XML for configuration,
   then hardware bring-up. Order it so each milestone is independently testable.

7. **Open risks.** Flag anything you think is a real gotcha — memory budget under
   pressure, execution-safety (infinite loops, watchdog resets mid-script), debugging
   support on a headless embedded node, and how a language-spec change would be migrated
   across nodes already running an older version of a script.

## Format

One structured document, organized by the sections above. Skip code — this is a design
document I'll turn into implementation work separately. If something is genuinely
underspecified and would change your recommendation, ask a single clarifying question
before writing; otherwise state your assumption and proceed.
