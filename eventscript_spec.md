# EventScript Language Specification — v0.4 (M1 Draft)

Companion to the architecture document. This is the standing-context spec for Claude
Code sessions covering M2 (host compiler + VM) onward. Everything here is a proposal to
be argued with; decision points that most deserve pushback are marked ⚖.

Changelog — v0.4: CDI **parameters** readable by scripts (§5.7, LOADP opcode);
**export** variable modifier for application/CDI visibility (§5.7); lines confirmed
binary-only with complex actuators driven via events (§5.4); retained-variable policy
parameterized by NVM endurance class (§5.7); well-known events explicitly left to
application code (§4). v0.3: fast clock reworked around a **local consumer clock** as
the source of truth (generators broadcast only on start/set plus infrequent heartbeats;
nodes keep their own time); `at` triggers fire from local minute crossings, not network
events; registers read the local clock continuously; discontinuity policy defined in
§5.6. v0.2: added fast-clock registers and the `at HH:MM:` trigger. v0.1: initial
draft.

---

## 1. Design Ground Rules

One value type: **signed 32-bit integer**, two's-complement, wrapping arithmetic
(deterministic, no traps on overflow; division by zero is a runtime fault). Booleans are
integers — comparisons yield 0 or 1, conditionals treat any nonzero value as true.
No strings, floats, or arrays in v1. No dynamic allocation anywhere: every limit in §8
is a compile-time constant of the firmware, and the compiler rejects programs that
exceed them with a specific error and line number.

The language is line-oriented for textarea friendliness: a statement ends at a newline
or a `;`. Blocks are delimited by keywords (`then…end`, `do…end`, `:…end`) — never by
indentation, which does not survive CDI round-trips reliably. `#` starts a comment that
runs to end of line.

All time values are integers in **milliseconds**. Duration literals are lexical sugar:
`500ms` lexes as `500`, `5s` as `5000`, `2m` as `120000`. There is no wall-clock time.

---

## 2. Lexical Elements

```
IDENT     = letter | "_" , { letter | digit | "_" }        # max 24 chars
INT       = decimal digits | "0x" hex digits               # 32-bit signed range
DURATION  = INT , ( "ms" | "s" | "m" )                     # lexes to INT (milliseconds)
EVENTID   = 8 dotted hex octets, e.g. 05.01.01.01.4C.00.00.02
COMMENT   = "#" … end of line
```

Keywords (reserved, case-sensitive, all lowercase):

```
on  startup  every  at  end  if  then  elif  else  while  do
wait  timeout  sleep  produce  var  retain  export  stop
and  or  not  true  false  event  log  setline  getline
timedout  millis  fasthour  fastminute  fastrunning
```

`true` and `false` are literals for 1 and 0. `timedout` and `millis` are built-in
read-only registers (§5.4); `fasthour`, `fastminute`, and `fastrunning` are the
fast-clock registers (§5.6).

---

## 3. Grammar (EBNF)

Designed for single-pass recursive descent with one token of lookahead; no construct
requires backtracking. `NL` denotes statement termination (newline or `;`).

```
program      = { declaration | handler } ;

declaration  = [ "export" ] ( "var" | "retain" ) IDENT "=" const_expr NL ;
                 # slot scope; const_expr = literals/operators only,
                 # folded at compile time; retain ⇒ persisted to NVM;
                 # export ⇒ readable by application code and CDI monitor (§5.7)

handler      = "on" "startup" ":" block "end"
             | "on" event_ref ":" block "end"
             | "every" const_expr ":" block "end"       # period in ms, > 0
             | "at" INT ":" INT ":" block "end"         # fast-clock time; hour 0-23,
             ;                                           # minute 0-59 (§5.6)

block        = { statement } ;

statement    = assignment NL
             | if_stmt
             | while_stmt
             | "produce" "(" event_ref ")" NL
             | "wait" event_ref [ "timeout" expr ] NL
             | "sleep" expr NL
             | "setline" "(" expr "," expr ")" NL       # (line, value)
             | "log" "(" expr ")" NL
             | "stop" NL                                 # end this handler run
             ;

assignment   = IDENT "=" expr ;

if_stmt      = "if" expr "then" block
               { "elif" expr "then" block }
               [ "else" block ]
               "end" ;

while_stmt   = "while" expr "do" block "end" ;

event_ref    = IDENT                       # name from the slot's CDI binding table
             | "event" "(" EVENTID ")" ;   # literal escape hatch (discouraged)

expr         = or_expr ;
or_expr      = and_expr  { "or"  and_expr } ;            # short-circuit
and_expr     = not_expr  { "and" not_expr } ;            # short-circuit
not_expr     = [ "not" ] cmp_expr ;
cmp_expr     = add_expr  [ ( "=="|"!="|"<"|"<="|">"|">=" ) add_expr ] ;
add_expr     = mul_expr  { ( "+" | "-" ) mul_expr } ;
mul_expr     = unary     { ( "*" | "/" | "%" ) unary } ;
unary        = [ "-" ] primary ;
primary      = INT | DURATION | "true" | "false"
             | IDENT                                    # variable read
             | "timedout" | "millis"
             | "fasthour" | "fastminute" | "fastrunning"
             | "getline" "(" expr ")"
             | "(" expr ")" ;
```

Notes: comparison is non-associative (`a < b < c` is a compile error — almost always a
bug at this audience level). `and`/`or` compile to branches, not opcodes, so evaluation
is short-circuit by construction.

---

## 4. Name Resolution

**Variables** are slot-scoped statics, declared with `var`/`retain` before first use;
assignment to an undeclared name is a compile error (catches typos, the number-one bug
class in a textarea). ⚖ Alternative: BASIC-style implicit declaration on first
assignment — friendlier to beginners, but silently turns `gatestate = 1` vs
`gate_state = 1` into a mystery. Recommendation stands on explicit declaration.

**Events** resolve against the slot's CDI event-binding table by name (case-sensitive
match against the table's name strings). The compiler infers direction from usage —
`on X:` / `wait X` marks entry X consumed, `produce(X)` marks it produced, both is
legal — and emits the consumer/producer registration sets as a compile artifact so the
firmware registers with OpenLcbCLib without parsing source. An `event(…)` literal
creates an anonymous internal binding; it participates in registration but not in the
CDI table, which is why it's the discouraged path. Well-known events (Emergency Stop
and kin) get **no implicit behavior** from the interpreter: layout-safety policy
belongs to application code, though a user may bind a well-known event through the
table like any other if a script should react to it.

**Parameters** (§5.7) resolve against the slot's CDI parameter table by name, exactly
as events do against theirs. Resolution order for an identifier in expression
position: declared variable, then parameter, then compile error. Parameters are
read-only: a parameter name as an assignment target is a compile error. A declared
variable whose name collides with an event or parameter name in the same slot is a
compile error — shadowing across the three namespaces is a debugging trap, not a
feature.

There are no handler-local variables and no user-defined functions in v1. ⚖ Both are
the most likely v2 additions; the ISA below leaves room (a frame-relative load/store
pair and CALL/RET) without renumbering.

---

## 5. Execution Semantics

### 5.1 Handlers and triggers

A slot's program is a set of handlers. Exactly four trigger kinds:

`on startup:` runs once after a successful compile — at boot, and again after each
commit. `on <event>:` runs when the bound event is consumed. `every <period>:` runs on
a node-local periodic timer, first firing one period after startup completes.
`at HH:MM:` runs when the node's local fast clock reaches that time (§5.6); it enters
the scheduler like any other trigger, so §5.2–5.3 apply to it unchanged.

At most **one handler per trigger** per slot: two `on ev_x:` blocks, or two `at 6:00:`
blocks, are a compile error (compose within one handler instead). One event may,
however, trigger handlers in several different slots — slots are independent consumers.

### 5.2 Run states and the pending latch

A handler is IDLE, RUNNING, or SUSPENDED (inside `wait`/`sleep`). If its trigger fires
while it is RUNNING or SUSPENDED, one re-run is **latched**: when the current run
completes, it runs once more. Further triggers while the latch is set are dropped and
counted in the slot's status block. ⚖ Alternatives considered: unbounded queueing
(unbounded memory, rejected), restart-on-retrigger (kills in-progress sequences — wrong
default for gate logic, though a per-handler `restartable` modifier is a plausible v2),
plain drop (loses the common "button pressed again during cycle" case). The
one-deep latch is the smallest thing that handles real layouts predictably.

### 5.3 wait, sleep, timedout

`wait ev timeout t` suspends the handler until event `ev` is next consumed or `t` ms
elapse, whichever is first, then sets the `timedout` register (1 on timeout, 0 on
event) and resumes. `wait ev` with no timeout waits indefinitely. Only events consumed
**after** suspension begins can satisfy a wait — there is no event memory. `timeout 0`
is a compile error (use `getline`/variables to poll state instead). `sleep t` is pure
delay; it leaves `timedout` untouched. `timedout` is per-handler and persists until the
handler's next `wait`.

Waiting on one of several events is deliberately absent from v1. ⚖ It is the most
tempting scope add (`wait ev_a or ev_b`); it roughly doubles suspension-record
complexity. The workaround — a variable set by tiny `on` handlers, polled after a short
sleep loop — is clumsy but expressible. Flagged as the first candidate for v1.1 based
on how often the workaround shows up in real scripts.

### 5.4 Built-in registers and I/O

`millis` reads the node uptime counter (wraps at 2³²ms ≈ 49.7 days; subtraction of two
readings is wrap-safe by two's-complement arithmetic — worth one line in the user
docs). `getline(n)` / `setline(n, v)` read and write logical I/O lines 1..N; the
firmware owns the mapping from line numbers to physical GPIOs per board. An
out-of-range line index is a runtime fault, not silent truncation.

Lines are strictly **binary** — `setline` writes 0 or nonzero, `getline` returns 0
or 1. Anything richer (servos, whether direct or via I2C drivers; stepper motors;
NeoPixel strings) is deliberately outside the language: the script produces an event,
and the application layer — on this node or any other — consumes it and performs the
motion or animation. Locally produced events loop back to local consumers, so
same-board actuators need nothing special. This keeps the language surface flat while
letting boards grow arbitrarily complex I/O. A single line number may serve as both
input and output where the firmware samples the line (RR-CirKits-style shared
input/output lines); `getline` and `setline` on the same `n` are both legal, and the
sampling mechanics are the firmware's concern, invisible to the script.

### 5.5 Faults

A runtime fault disables the offending handler (not the slot, not the node), records
fault code + source line in the slot status block, and optionally produces the node's
diagnostic event. Fault codes: `DIV_ZERO`, `BUDGET_EXCEEDED` (per-run cumulative
instruction ceiling, §8), `BAD_LINE_INDEX`, `STACK_OVERFLOW` (defense in depth — the
compiler's static stack sizing should make this unreachable), `LATCH_DROPS` (informational
counter, non-fatal). Re-enabling is by recommit or reboot.

### 5.6 Fast clock (LCC Broadcast Time Protocol)

The node tracks one clock, selected by a node-level CDI setting (clock ID prefix;
default: the well-known Default Fast Clock). **The source of truth is a local consumer
clock maintained by the firmware's clock module** — synchronized whenever a Report
Time / Date / Rate / Start / Stop event arrives, and advanced between broadcasts by the
node's own timebase scaled by the last reported rate. This matches deployed generator
behavior: real generators broadcast time on start and set, then only an infrequent
heartbeat, and expect consumers to keep their own time. Nothing in the language depends
on the generator emitting per-minute events. On the network side the module sends the
protocol's Consumer Range Identified over the clock's time-event range and issues a
sync query at boot; received events only ever *correct* the local clock.

The language surface has two facilities:

**Registers (for conditions).** `fasthour` (0–23), `fastminute` (0–59), and
`fastrunning` (0/1), read from the local clock — continuously valid while the clock
runs. Before the first synchronization after boot, `fasthour` and `fastminute` read
**−1**; scripts that must be robust at power-up guard with `fasthour >= 0`. While the
clock is stopped the registers hold the last time. Range conditions are the intended
use, not equality tests:

```
# lamps on from 19:00 to 06:00 — range spanning midnight
if fasthour >= 19 or fasthour < 6 then ... end
# finer granularity: minutes since midnight
if fasthour * 60 + fastminute >= 6 * 60 + 30 then ... end
```

**`at HH:MM:` trigger (for scheduling).** Fired by the local clock crossing that minute
boundary — a firmware-internal dispatch, never a network event consumption, so it is
immune to broadcast cadence and generator implementation quality. During continuous
progression the module fires every `at` handler whose minute the local clock passes, in
time order, in either direction for backward-running clocks; at high rates several
minutes may be crossed between scheduler slices and the resulting firings are bounded
by the one-deep latch (§5.2). Triggers recur every fast day and do not fire while the
clock is stopped. Time bindings are internal: they consume handler-table entries but
**not** the slot's 16-entry CDI event table.

**Discontinuity policy (owned by this firmware, not the generator).** A received time
report that disagrees with local progression is classified by the gap: a forward
correction of at most **2 fast minutes** is treated as drift synchronization, and any
`at` triggers in the corrected-over span fire in order — routine sync must never
silently eat a scheduled action. Anything larger, in either direction, is a
**discontinuity**: the clock jumps, the registers update, and no intervening `at`
triggers fire. Rationale is the classic church-bell problem — replaying a burst of
scheduled instantaneous actions for time that "didn't happen" is worse than skipping
them. ⚖ The 2-minute threshold is a judgment call; it only needs to exceed worst-case
local drift between heartbeats, and it should be a firmware constant, not user-visible.

The scripting guidance that follows, for user docs: use `at` alone for instantaneous
actions (sound a horn, dispatch a train); derive *state* — lights, signals, anything
"on between times" — from register range-checks or from paired `at` triggers writing a
retained variable, so that a time-set converges to correct state even though the
skipped triggers never fired.

The clock module is plain C over injected time reports and an injected timebase, so it
is fully host-testable in M2–M3 alongside the VM: sync, drift correction, discontinuity
classification, stop/start, backward rates, and midnight rollover all get golden tests
before hardware.

### 5.7 Parameters and exported variables

**Parameters: CDI → script.** Each slot carries a CDI parameter table of up to 8
entries: {name (16 chars), int32 value}, sitting alongside the event-binding table.
Scripts read parameters by name like read-only variables; the compiler resolves names
to table indices (LOADP). Reads are **live**: each access fetches the current table
value, so a user tuning a debounce delay or a lamp threshold in JMRI changes behavior
on the next read with no recompile and no script edit — the whole point of separating
tunables from code. Writing a parameter's *name* field marks the slot for recompile
(same rule as the event table); writing its *value* field never does. Parameters are
runtime values and are not accepted where `const_expr` is required (`every` periods,
declaration initializers) — those remain literal-only.

**Exported variables: script → application/CDI.** The `export` modifier
(`export var throws = 0`, `export retain last_route = 0`) flags a variable as
externally visible through two windows: a firmware API for application code
(lookup by slot + name or index, returning the live int32 — this is how the node
application observes script state without any coupling to script internals), and the
slot's read-only CDI **monitor region**, which serves name/value pairs live at
memory-read time so JMRI displays current values on refresh. The monitor region
doubles as the debug-watch surface — exporting a variable is how a user instruments a
misbehaving script on a headless node. Cap: 8 exported variables per slot.

**Retained-variable persistence by endurance class.** The NVM behind `retain` is a
compile-time backend choice with very different endurance: **FRAM** writes through on
every change (effectively unlimited endurance); **EEPROM** (the current fleet) uses a
dirty-flag with coalesced flushes — default every 10 s and on clock-stop — because a
variable toggling once per second under write-through would exhaust a ~1M-cycle cell in
days; **raw flash** defers to the architecture document's sector-journal treatment. The
semantic contract stated to users is honest about this: on FRAM, retained state
survives any power loss; on EEPROM, retained state may lose up to the coalescing window
on an abrupt cut. Backends present one small interface (read, write, flush, plus
declared write-granularity and endurance class) so the core stays portable across
RP2040/RP2350, ESP32-class parts, and host builds.

---

## 6. Bytecode ISA

Stack machine, one operand stack per handler context, all values int32. Variable-length
encoding: 1 opcode byte + 0/1/2/4 operand bytes. Jump offsets are signed 16-bit,
relative to the byte after the operand. The VM decrements the slice budget on **every
instruction**, so no explicit yield opcode exists and backward jumps need no special
casing. 31 opcodes assigned; 0x20–0x3F reserved for v2 (CALL/RET, frame-relative
load/store, wait-any).

| Op   | Mnemonic  | Operand      | Stack effect        | Notes |
|------|-----------|--------------|---------------------|-------|
| 0x00 | NOP       | —            | —                   | |
| 0x01 | PUSH8     | imm8 (signed)| — → v               | |
| 0x02 | PUSH16    | imm16 (signed)| — → v              | |
| 0x03 | PUSH32    | imm32        | — → v               | |
| 0x04 | LOADV     | var idx u8   | — → v               | slot variable read |
| 0x05 | STOREV    | var idx u8   | v → —               | retained vars: same opcode; persistence is a flag on the variable table entry |
| 0x06 | LOADR     | reg u8       | — → v               | 0=timedout, 1=millis, 2=fasthour, 3=fastminute, 4=fastrunning |
| 0x07 | ADD       | —            | a b → a+b           | wrapping |
| 0x08 | SUB       | —            | a b → a−b           | wrapping |
| 0x09 | MUL       | —            | a b → a·b           | wrapping |
| 0x0A | DIV       | —            | a b → a/b           | trunc toward 0; b=0 ⇒ DIV_ZERO fault |
| 0x0B | MOD       | —            | a b → a%b           | sign follows a; b=0 ⇒ fault |
| 0x0C | NEG       | —            | a → −a              | |
| 0x0D | EQ        | —            | a b → (a==b)        | result 0/1 |
| 0x0E | NE        | —            | a b → (a!=b)        | |
| 0x0F | LT        | —            | a b → (a<b)         | |
| 0x10 | LE        | —            | a b → (a<=b)        | |
| 0x11 | GT        | —            | a b → (a>b)         | |
| 0x12 | GE        | —            | a b → (a>=b)        | |
| 0x13 | NOT       | —            | a → (a==0)          | logical not |
| 0x14 | JMP       | rel16        | —                   | |
| 0x15 | JZ        | rel16        | a → —               | jump if a == 0 |
| 0x16 | JNZ       | rel16        | a → —               | jump if a != 0 |
| 0x17 | PRODUCE   | evt idx u8   | —                   | enqueue Producer event; index into slot binding set |
| 0x18 | WAITE     | evt idx u8   | t → —               | suspend; t = timeout ms, 0 = infinite; sets timedout on resume |
| 0x19 | SLEEP     | —            | t → —               | suspend t ms; timedout untouched |
| 0x1A | SETLINE   | —            | n v → —             | write logical line; bad n ⇒ fault |
| 0x1B | GETLINE   | —            | n → v               | read logical line; bad n ⇒ fault |
| 0x1C | LOG       | line# imm16  | v → —               | append (source line, v, millis) to diagnostic ring |
| 0x1D | STOP      | —            | —                   | end handler run normally (checks pending latch) |
| 0x1E | HALT      | —            | —                   | compiler-emitted end-of-handler; same as STOP |
| 0x1F | LOADP     | param idx u8 | — → v               | live read of slot CDI parameter (§5.7) |

Lowering conventions: `and`/`or` compile to JZ/JNZ short-circuit chains (no AND/OR
opcodes). `if/elif/else` and `while` are conventional structured lowering. `wait ev`
without timeout compiles to `PUSH8 0; WAITE ev`. Duration literals are ordinary integer
pushes. `x = x + 1` is `LOADV x; PUSH8 1; ADD; STOREV x` — no fused increment in v1;
measure before optimizing.

### 6.1 Compiled slot image (RAM-resident, never persisted)

```
SlotImage
  magic          u16      0xE5C0
  isa_version    u8       1
  flags          u8
  var_count      u8       ≤ 32; parallel var table: {init value i32,
                          flags: RETAIN | EXPORT}
  param_count    u8       ≤ 8; indices into the slot's CDI parameter table
  handler_count  u8       ≤ 16
  code_size      u16
  handlers[]     each: { trigger u8 (0=STARTUP,1=EVENT,2=PERIODIC,3=FASTTIME),
                          param u16 (event idx | period ms low word — period
                          stored as u32 in a side table if > 65535 |
                          FASTTIME: hour×256+minute, matching the protocol's
                          time-event encoding),
                          entry_pc u16,
                          max_stack u8 }   # computed statically by the compiler
  code[]         bytecode
```

`max_stack` per handler is the compiler's proof obligation: it must compute the exact
worst-case operand stack depth (straight-line analysis suffices — the grammar has no
recursion and expressions have static depth) and reject any handler exceeding the §8
cap. The VM's STACK_OVERFLOW check is belt-and-suspenders, not the enforcement.

---

## 7. Worked Example with Listing

Source (crossing gate, using binding-table names):

```
retain gate_down = false

on ev_approach:
    if not gate_down then
        produce(ev_gate_lower)
        gate_down = true
        wait ev_island_clear timeout 30s
        if timedout then log(1) end
        produce(ev_gate_raise)
        gate_down = false
    end
end
```

Compiled listing for the handler (annotated; offsets illustrative):

```
0000  LOADV   0          # gate_down
0002  JNZ     +0x1C      # if not gate_down … (NOT folded into inverted branch)
0005  PRODUCE 1          # ev_gate_lower
0007  PUSH8   1
0009  STOREV  0          # gate_down = true
000B  PUSH32  30000
0010  WAITE   2          # ev_island_clear, 30s
0012  LOADR   0          # timedout
0014  JZ      +0x05
0017  PUSH8   1
0019  LOG     line=9
001C  PRODUCE 3          # ev_gate_raise
001E  PUSH8   0
0020  STOREV  0          # gate_down = false
0022  HALT
```

(The compiler is free to fold `not` into branch polarity as shown; golden tests in M2
should assert semantics via execution traces, not exact byte sequences, so peephole
choices stay unconstrained.)

---

## 8. Limits (firmware compile-time constants, v1 defaults)

| Limit | Default | Rationale |
|---|---|---|
| Program slots | 8 | §3 of architecture doc |
| Source per slot | 2,048 bytes | one FRAM/flash-sector-aligned slot |
| Bytecode per slot | 4,096 bytes | RAM budget; ~2:1 worst-case expansion observed target |
| Variables per slot | 32 | u8 index headroom to 255 |
| Retained vars per slot | 8 | NVM write-coalescing budget |
| Parameters per slot | 8 | CDI table alongside event bindings |
| Exported vars per slot | 8 | monitor region size |
| Event bindings per slot | 16 | matches CDI table |
| Handlers per slot | 16 | |
| Operand stack per handler | 16 entries (64 B) | compiler-enforced |
| Handler contexts (node) | 32 | 8 slots × avg 4 concurrent |
| Slice budget | 1,000 instructions | tune in M4 |
| Per-run budget | 100,000 instructions | BUDGET_EXCEEDED fault |
| Event inbox depth | 32 entries | drop-oldest + counter on overflow |

---

## 9. Compile Errors (categories for M2 test coverage)

Every error carries line and column. Categories: lexical (bad character, identifier too
long, integer out of range, malformed EVENTID); syntax (per-production expected-token
messages — invest here, this is the user's primary feedback channel); name (undeclared
variable, unknown event or parameter name, duplicate declaration, duplicate handler for
trigger, assignment to register/keyword/parameter, variable name shadowing an event or
parameter name); semantic (non-constant initializer or period, `timeout 0`, chained
comparison, `at` hour/minute out of range, duplicate `at` time); resource (any §8
limit, with the limit named in the message: "too many variables (max 32)").

Status-block contract: on failure the slot reports `COMPILE_ERR`, line, column, and a
≤64-char message; on success, `RUNNING`, bytecode size, and handler count, plus the
monitor region serving exported-variable name/value pairs live (§5.7). This is the
entire debugging surface a headless user gets — treat error message quality as a
feature with tests, not a byproduct.

---

## 10. Deferred to v2 (recorded so scope stays pinned)

Wait-any (`wait ev_a or ev_b`) — first in line, pending field evidence (§5.3).
User-defined functions and handler-local variables (ISA space reserved).
`restartable` handler modifier. Cross-slot `shared` variables. Fast-clock extensions:
sub-minute language granularity (`at HH:MM:SS`, the local clock already tracks finer
than it exposes), a `fastrate` register, date/day-of-week registers, and per-script
clock selection for multi-clock layouts (§5.6). Writable parameters and an
application→script signaling path beyond events. Host-embedded compiler builds (the
same portable C compiled as a library) for editor-side validation — e.g., a JMRI or
standalone tool that checks scripts and reports error lines before any bytes reach the
node; the on-device compiler remains authoritative. Fused
increment/decrement and other peephole opcodes — only after profiling shows dispatch
overhead matters, which at layout-logic rates it almost certainly does not.
