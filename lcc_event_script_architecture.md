# Embedded Event-Scripting Engine for OpenLcbCLib Nodes on RP2040/RP2350

## Architecture Design Document — v1

Target: RP2040 (264KB SRAM / 2MB QSPI flash) and RP2350 (520KB SRAM), bare-metal C firmware
built on OpenLcbCLib. Prior art baseline: RR-CirKits Tower LCC+Q STL Logic Engine
(16 × 256-char CDI MultiLines, S7-STL subset, edited live via any generic CDI tool).

Stated assumptions, in lieu of a clarifying question: OpenLcbCLib is run in its normal
cooperative main-loop configuration (CAN RX may be interrupt-assisted, but protocol
callbacks fire in main-loop context); nodes are CAN-attached (so Stream support across the
installed tool base cannot be assumed); and the audience authoring scripts is layout
builders using JMRI, not developers with a toolchain. All three assumptions shape the
recommendations below, and I flag where a different assumption would change the call.

---

## 1. Language / VM Choice

### The constraint that actually decides this

The Tower LCC+Q's most important property is not its language — STL is frankly
user-hostile — it is that **the only tool a user ever needs is a generic CDI editor**.
Text goes into a JMRI textarea, gets written to config memory over standard datagrams,
and the node does the rest. No installer, no compiler download, no version skew between
a host tool and firmware. Any design that requires a host-side compiler forfeits that,
and for a hobbyist audience that forfeiture is expensive. So the deciding constraint is:
**the compiler must run on the node**, taking source text from NVM and producing bytecode
at commit/boot time. That immediately re-ranks the candidates.

### Candidates

**MicroPython (embed port or trimmed fork).** The official RP2 port proves it runs on
this silicon, and the `embed` port exists precisely for hosting MP inside foreign
firmware. But even minimized builds want roughly 100–300KB of flash and a GC heap of
16KB+ before your program does anything, GC pauses make execution timing
non-deterministic alongside a CAN stack you must service continuously, and the
compiler+runtime is a large foreign codebase to co-own. It maps poorly onto
"wait for event" without building an async layer on top. On RP2040 sharing 264KB of SRAM
with OpenLcbCLib buffers, CAN queues, and your existing application, this is the heavy
option. Viable on RP2350 if you later want a "pro tier," but wrong as the core.

**Tiny BASIC family (uBASIC, TinyBasic Plus, MY-BASIC).** Adam Dunkels' uBASIC is a
few KB and interprets source text directly — genuinely tiny, easy to bolt primitives
onto, MIT-style licensed. Weaknesses: line-numbered GOTO dialects are dated even for
hobbyists; direct source interpretation re-tokenizes on every pass (fine at this scale,
but it makes per-statement execution cost irregular); and none has a native concept of
suspending on an external event — you'd bolt on a coroutine mechanism anyway. MY-BASIC
is more modern (structured, no line numbers) but ~10× larger and heap-centric.

**Forth-style threaded VM.** Technically the best fit for the silicon — tiny,
deterministic, trivially extensible with EVENT/PRODUCE words, and the "compiler" is
almost free. Disqualified on audience grounds: RPN and stack juggling is a harder sell
to layout builders than the S7 STL you're trying to improve on. Only worth revisiting if
you personally would be the only author.

**Purpose-built small language + bytecode VM, compiled on-device.** A single-pass
recursive-descent compiler for a small structured grammar (no line numbers; `if/elif/else`,
`while`, integer/boolean variables, named event handlers, `wait` with timeout) is on the
order of 5–10KB of code and a few KB of working RAM — very much writable and maintainable
in Claude Code sessions. The VM is a small switch-dispatch loop over a compact ISA
(~30–40 opcodes), giving you exact control over instruction budgets, suspension points,
and event primitives as first-class opcodes rather than library calls.

### Recommendation

**Build a purpose-built language — call it EventScript here — with a Python-flavored
surface syntax, compiled on the node from CDI-resident source text into bytecode held in
RAM.** Reasoning: it is the only option that simultaneously (a) preserves the
CDI-tool-only workflow, (b) fits comfortably in the RP2040 budget with room to spare,
(c) gives deterministic, budgetable execution next to a live CAN stack, and (d) makes
events first-class in the grammar instead of bolted on. The cost — owning a compiler —
is real but small at this grammar size, and it's the kind of well-specified,
exhaustively-testable component Claude Code is good at building incrementally.

Surface style matters for adoption: prefer Python-ish structure (indentation optional;
`end`-delimited blocks are easier to compile and more forgiving in a textarea) with a
deliberately tiny type system: integers, booleans, and named events. A flavor of what a
user would write:

```
on ev_east_approach:
    if gate_state == 0 then
        produce(ev_gate_lower)
        gate_state = 1
        wait ev_island_clear timeout 30s
        produce(ev_gate_raise)
        gate_state = 0
    end
end

every 500ms:
    if flashing then toggle(pin_led) end
end
```

Do not persist bytecode. Source text in NVM is the single source of truth; compile at
boot and on commit. Compilation of a few KB of source is milliseconds on a 133–150MHz
core, and it means the bytecode ISA can evolve freely between firmware versions (see §7).

If you want a running start rather than a clean sheet, uBASIC is worth reading as a
skeleton for the tokenizer/expression evaluator shape, but I'd treat it as reference,
not foundation — the coroutine suspension model in §2 wants to be designed in, not
retrofitted.

---

## 2. Execution Model

### Integration with OpenLcbCLib

OpenLcbCLib's application surface is a cooperative main loop: CAN frames may arrive under
interrupt, but event-consumed callbacks and the periodic timer tick execute in loop
context. The interpreter should live entirely in that same loop as one more cooperative
task. Concretely:

**Event inbox.** The OpenLcbCLib "event consumed" callback does exactly one thing: push
the matched event's index (not the 64-bit ID — the small table index from §5) into a
fixed-size ring buffer and return. No interpretation happens in the callback. This keeps
the callback O(1) regardless of script complexity and makes the ISR/loop boundary clean
if you ever move RX matching into interrupt context.

**Scheduler slice.** Each pass through the main loop, after servicing the protocol stack,
the VM scheduler runs: drain the inbox, mark any handlers whose trigger event arrived as
runnable, resume any suspended handler whose awaited event arrived or whose timer
expired, then execute runnable handlers under an **instruction budget** — a hard cap of
N bytecode ops per slice (start around 1,000; tune against your loop period). A handler
that exhausts the budget is preempted at the next loop back-edge and resumes next slice.
The CAN stack is therefore never starved by user code, by construction.

### Blocking and resuming: coroutine handlers

Pure run-to-completion (the Tower model, effectively) can't express the procedural
sequences you want ("lower gate, wait for island clear, raise gate"). So each handler is
a lightweight coroutine: `wait <event> [timeout <t>]` saves the handler's program counter
and its small evaluation stack into that handler's context block and yields. The
scheduler resumes it when the awaited event index appears in the inbox or the timeout
fires. Context blocks are statically allocated at compile time — the compiler knows the
maximum stack depth of every handler, so there is no dynamic allocation anywhere in the
VM. A reasonable budget: 8–16 concurrent handler contexts of ~64–128 bytes each; a few KB
total.

Two triggers exist besides events: `on startup:` (runs once after compile/boot) and
`every <t>:` periodic handlers driven off OpenLcbCLib's timer tick. That trio — startup,
event, periodic — covers the Tower's use cases and considerably more.

### Runaway protection and faults

Three layers. First, the per-slice instruction budget already guarantees loop liveness —
an infinite `while` loop degrades into a handler that consumes its slice forever but
never blocks the node. Second, a per-handler cumulative budget (e.g., 100k instructions
without a `wait` or handler completion) trips a **script fault**: the handler is
disabled, a status code and source line number are written to a read-only CDI status
field, and optionally a diagnostic event is produced so JMRI can alarm on it. Third, the
hardware watchdog stays owned by the firmware, not the VM — the VM can never be the
component that decides whether the watchdog gets fed.

### Reboot semantics

Keep this brutally simple in v1: on any reboot, all suspended handlers are cancelled,
all variables reset to their declared initial values, and `on startup:` handlers run.
In-flight `wait`s do not survive. Add a small class of **retained variables**
(`retain gate_state = 0`) persisted to NVM on change — rate-limited if the backing store
is flash, unlimited if FRAM — for state that genuinely must survive power cycles, like a
turnout's last commanded position. Do not attempt to persist coroutine continuations;
the complexity-to-value ratio is terrible and the failure modes (resuming a wait for an
event that fired during the outage) are worse than a clean restart.

One LCC-correctness note: because produced/consumed events are enumerated in CDI tables
(§5), the firmware can answer Identify Producer/Consumer and emit the boot-time
Producer/Consumer Identified reports with correct valid/invalid state from retained
variables — something script-embedded event IDs would make nearly impossible. This is a
second, independent argument for the §5 binding model.

---

## 3. NVM Layout

### Where scripts live relative to existing config

Keep script storage **inside the standard configuration address space (0xFD)** that
OpenLcbCLib already exposes for CDI-defined parameters, as a new segment appended after
your existing node configuration. This is what makes the whole Tower-style workflow fall
out for free: generic tools already know how to read and write this space with
Memory Configuration datagrams, and JMRI renders it from your CDI XML with zero custom
tooling. A custom address space (say 0xA0) is cleaner in the abstract but buys nothing
until you have a custom host tool, which is explicitly a non-goal for v1.

### Slot structure

Divide the script region into **fixed-size program slots** — recommend **8 slots of 2KB
source each** (16KB total) as the default build, configurable at compile time. That is
4× the Tower's total logic capacity per slot, 32× overall, while staying trivial in a
2MB flash or a 32KB FRAM. Fixed-size slots cost some internal fragmentation but make the
CDI XML static, the memory map stable across edits, and each slot independently
rewritable.

Per-slot layout: a small header (enable flag, 16-char name, format-version byte,
CRC32 of the source text, reserved bytes), the source text area, and a **read-only
status block** the firmware maintains — compile result, error line/column, error message
string, run state, fault code. Surfacing compile errors as a readable CDI string is the
single biggest usability win over guessing why logic silently doesn't run.

Separately: a shared **event binding table** region (§5) and a small **retained
variables** region, each with their own CRC.

### Backing store and the XIP trap

This choice has a hardware landmine. On RP2040 (and RP2350), code executes XIP from the
same QSPI flash you'd be erasing/writing; **any flash program/erase stalls all XIP
execution** for the duration — sector erases run milliseconds — during which CAN frames
can be dropped unless RX is fully interrupt-buffered from RAM-resident code. Since your
boards already support external I2C EEPROM/FRAM, **prefer external FRAM (e.g., MB85RC
series) as the script/retained-variable store**: byte-writable, effectively infinite
endurance (ideal for retained variables written on every state change), no erase stalls,
no wear leveling. If a board must use onboard flash, align each slot to a 4KB erase
sector, buffer writes in RAM and commit whole slots, run the flash-write routine from
SRAM, and accept a brief, bounded service pause at commit time only (commits are rare;
retained-variable writes to flash should be coalesced and rate-limited, e.g., one commit
per 10s max).

### One program or many?

**Multiple independent slots.** Isolation is the point: a compile error or runtime fault
in the crossing-gate script must not take down the signal ladder in the next slot. Slots
also give users a natural per-function organization, partial updates rewrite only one
sector, and per-slot status makes debugging tractable. Default to isolated variable
namespaces per slot; add an explicit `shared` variable declaration later only if real
use cases demand cross-slot state (event-based signaling between slots is the more
LCC-idiomatic coupling anyway — one slot produces, another consumes).

---

## 4. Loading / Transport Mechanism

### Recommendation: standard Memory Configuration datagrams into CDI-declared strings

The Tower approach — script text as string elements in config space, edited through a
generic CDI tool's textareas and written via standard Memory Configuration Protocol
datagram writes — is the right transport, and I'd adopt it outright with two upgrades.
What it gets right: universal tool support today (JMRI, Model Railroad System, any
future CDI tool), automatic chunking of large writes into 64-byte datagram payloads by
the protocol layer, no custom protocol to specify or maintain, and the node needs
nothing beyond the config-memory handling OpenLcbCLib already provides.

Where the Tower approach is weak and the fixes:

**Commit semantics.** The Tower recompiles implicitly; with larger multi-datagram
writes you want an explicit boundary so the compiler never sees a half-written slot.
Fix: per-slot CRC in the header plus an explicit commit trigger — a one-byte "action"
field per slot (CDI can render it as a button-like selector: Compile & Run / Stop /
Revert) written last. The Memory Config "update complete" notification, where the tool
sends it, is a belt-and-suspenders recompile hint, but don't depend on tools sending it.

**Editing ergonomics.** A JMRI textarea with no syntax highlighting and per-field size
limits is clunky at 2KB. Accept it for v1 — it is exactly the Tower's UX and it works —
and treat a nicer editor as a later, optional layer: because the transport is plain
memory-space writes, a small host-side helper (or a JMRI script) can round-trip slot
contents without any node-side changes. The architecture decision is that **any such
tool is sugar, never a requirement.**

### Rejected alternatives

**Stream protocol:** the payloads (≤2KB) don't need it, and Stream support across
CAN-attached nodes and tools is spotty enough that requiring it would shrink your
compatible-tool set to roughly zero for no benefit. **Custom datagram types:** all cost
(spec, tool support, forward compatibility) and no capability the memory protocol
doesn't already give you. **Firmware-upgrade-style transfer (space 0xEF + freeze):**
wrong semantics — scripts are configuration, not firmware, and freeze/unfreeze
reboot behavior would fight the live-edit workflow.

---

## 5. Event Binding Model

**Bind events in CDI tables; reference them by name in scripts.** Each slot's CDI
section (or one node-level table — per-slot is tidier) carries N event entries, each an
8-byte EventID element plus a short name string, e.g. 16 entries per slot. JMRI renders
EventID fields with its standard event widgets — copy/paste from other nodes, and
critically the **event capture/"learn" workflow**, where the user presses the fascia
button or throws the turnout and captures the resulting event straight into the field.
Scripts then refer to `ev_east_approach` by the name given in the table.

Why this beats event IDs in script text: it keeps 16-hex-digit IDs (with dotted-form
transcription errors) out of user code; re-binding to different hardware requires no
code edit — the same crossing-gate script drops onto a second crossing by rebinding its
table; the firmware knows the complete producer/consumer sets **without parsing user
code**, so OpenLcbCLib event registration, Identify handling, and boot-time
Producer/Consumer Identified reports (§2) work correctly and immediately, even for
slots that failed to compile; and it matches the configuration idiom every LCC user
already knows from every other node.

Direction (produced vs. consumed vs. both) can be inferred by the compiler from usage
(`on X:` / `wait X` ⇒ consumed; `produce(X)` ⇒ produced) and written into the
registration tables at commit — no need to burden the user with declaring it. Allow a
literal-EventID escape hatch in the grammar for power users, but document the table as
the intended path.

Linkage mechanics: at compile time, names resolve to table indices; the bytecode carries
indices only. Renaming or re-binding an entry therefore requires recompiling dependent
slots — handled automatically since commit recompiles, but a table edit should also
mark dependent slots for recompile (simplest rule: any table write recompiles the slot).

---

## 6. Phased Development Roadmap for Claude Code

Ordered so each milestone is independently testable, and so hardware enters as late as
possible — the compiler and VM are pure portable C and should be bulletproof on the host
before they ever see a Pico. Milestones 1–3 are also the cheapest place to change your
mind about language design; treat the spec as frozen only after M3.

**M1 — Language and VM specification (paper only).** Grammar (EBNF), the ~30–40 opcode
ISA, handler/coroutine semantics, fault codes, slot header format, event-table format,
CDI XML sketch. Deliverable: a spec document plus 5–6 worked example programs (crossing
gate with island timeout, ABS signal ladder, turnout interlock, fascia-button dispatcher,
startup state restoration) hand-checked against the grammar. This document becomes the
standing context file for every subsequent Claude Code session.

**M2 — Host-side compiler + VM, CLI harness.** Portable C99, zero hardware
dependencies, malloc-free core (static pools sized by compile-time constants). A CLI
that compiles a source file, dumps bytecode listings, and runs it against a scripted
event/timer stimulus file, logging produced events. Unit tests for the tokenizer,
parser (including every error path — error line reporting is a feature, test it),
and each opcode. Golden-file tests for the example programs from M1.

**M3 — Runtime semantics hardening on host.** Coroutine suspend/resume across `wait`,
timeout arbitration, instruction budgets and fault trips, inbox overflow policy,
retained-variable change tracking. Add a fuzzer over the compiler (random token streams
must never crash it, only produce errors) — an afternoon of Claude Code work that pays
for itself the first time a user typos a script.

**M4 — Pico bring-up without LCC.** Link the engine into a minimal RP2040/RP2350
firmware: scripts baked in as string constants, GPIO/timer primitives wired, instruction
budgets tuned against a real main-loop period, SRAM/flash footprint measured and
recorded. Validates the no-allocation claim and the slice scheduler on real silicon.

**M5 — OpenLcbCLib integration.** Event-consumed callback → inbox; `produce` → the
library's produce path; event-table-driven registration; Identify Producer/Consumer and
boot-time Identified reports from retained state. Test node on the bench against JMRI:
send events from the JMRI event tool, watch script-produced events appear.

**M6 — NVM slots + CDI.** Slot layout on FRAM (and the flash fallback with
RAM-resident write path), CRC verification, compile-on-commit, status/error fields,
full CDI XML. Test: edit a script in a JMRI textarea, commit, watch the status field
report success or a precise error line; power-cycle and confirm persistence and
retained variables.

**M7 — Workflow polish and user documentation.** Multi-slot fault isolation testing,
event-table learn-mode round trips, the Revert action, a user-facing language reference
with the example-program library, and a "porting a Tower LCC+Q STL group to EventScript"
worked example — a good adoption on-ramp for exactly your audience.

**M8 — Layout soak.** Run real jobs (your paper-mill traffic logic is a natural
candidate) on live hardware for weeks; capture faults via the diagnostic event; iterate
budgets and inbox depths from field data.

---

## 7. Open Risks

**The XIP/flash-write stall is the sharpest hardware gotcha.** If any target board
stores scripts or retained variables in onboard QSPI flash, every erase stalls code
execution unless the write path runs from SRAM and CAN RX buffering is interrupt-driven
and RAM-resident. Retained variables written on every state change would also chew
flash endurance. Mitigations are in §3; the strategic mitigation is standardizing on
FRAM for this feature's storage and treating onboard flash as the degraded path.

**RAM budget creep on RP2040.** The engine itself is small, but it sits next to
OpenLcbCLib buffers, CAN queues, your existing application, and now per-handler
contexts, inbox, compiled bytecode, and compiler working memory. Everything is statically
sized, so make the sizing knobs explicit compile-time constants from M2 onward and track
a memory map per milestone. If a squeeze comes, compiler working RAM is reclaimable
(compile one slot at a time), and bytecode for disabled slots need not be resident.

**Headless debugging.** A wrong-but-compiling script on a node with no console is the
top support burden to expect. Budget real design effort for: per-slot status strings
(current handler, last event consumed, fault + line number) in read-only CDI; a `log()`
statement that produces a designated diagnostic event or appends to a RAM ring buffer
exposed as a readable memory region; and possibly a single-step/trace mode toggled from
CDI. These are cheap on top of the architecture and transform the user experience.

**Language evolution vs. deployed scripts.** Because bytecode is never persisted, the
ISA is free to change with firmware. Source compatibility is the real contract:
grammar changes must be additive, the slot-header format-version byte gates any future
breaking change (old-version slots refuse to auto-compile and report "update script
syntax" rather than misbehaving), and the spec doc from M1 should carry a changelog from
day one. Resist per-node dialect drift across your RP2040/RP2350 fleet — one grammar,
one version number, everywhere.

**Event storms and inbox overflow.** A busy layout can burst events faster than one
scheduler slice drains them. Define the overflow policy now (drop-oldest with a fault
counter is defensible; drop-newest silently is not), size the inbox generously (it's
bytes per entry), and count drops in the status block so the failure is visible, not
mysterious.

**Timing semantics honesty.** There is no RTC and no global clock; all times are
node-local relative durations, and `every 500ms:` has jitter bounded by the main-loop
period plus budget preemption. Document this so nobody builds a fast-clock or
cross-node-synchronized animation on promises the platform can't keep. If wall-clock
behavior is ever wanted, consume the LCC clock protocol's events like any other
producer — which the architecture already supports for free.

**Scope creep toward MicroPython.** Users will eventually ask for strings, arrays, and
floats. The architecture tolerates growth (ISA versioning, on-device compiler), but each
addition erodes the determinism and footprint story that justified the custom VM.
Pre-commit to a line: integers, booleans, events, timers in v1; revisit only with field
evidence. If demand for a rich language materializes, that is the moment to evaluate a
MicroPython tier on RP2350-only hardware rather than growing EventScript into a worse
MicroPython.
