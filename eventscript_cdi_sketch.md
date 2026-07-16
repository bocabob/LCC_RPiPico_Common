# EventScript CDI and Memory Map Sketch — M1 Deliverable

Pins the byte layout and CDI XML structure for the configuration segment (space 0xFD)
and the read-only status/monitor space, so M6 implements rather than relitigates.
Constants here follow spec v0.4 limits: 8 slots, 2,048 B source, 16 event bindings,
8 parameters, 8 exported variables per slot.

One divergence from the architecture document, decided here: the per-slot **action**
selector is `None / Compile & Run / Stop / Validate` — **Revert is dropped for v1**.
Revert implies a shadow copy of the last committed source (writes land in NVM
immediately, so there is nothing to revert *to* without doubling storage). A tool that
wants revert-like behavior reads the slot before editing. The architecture doc has been
amended to match.

Byte order: all multi-byte integers in CDI-visible spaces (param values, status
counters, line/column fields) are **big-endian**, per LCC convention for CDI integer
elements — generic tools already assume it. Firmware must serialize through explicit
pack/unpack helpers, never by copying native structs.

---

## 1. Address Space Overview

| Space | Contents | Access | Backing |
|---|---|---|---|
| 0xFD | Node application config (existing) + EventScript segment at `ES_BASE` | R/W | EEPROM/FRAM/flash |
| 0x50 | EventScript status + monitor (custom space) | Read-only | RAM, served live |
| 0xFF / 0xFE / 0xFC | CDI, all-memory, ACDI | per OpenLcbCLib | — |

`ES_BASE` is a firmware constant placing the EventScript region after the node's
existing application configuration; the sketch uses `ES_BASE = 0x1000` illustratively.
Space 0x50 is advertised read-only in its Get-Address-Space-Info reply; the node
rejects writes.

Slot stride is backend-dependent (both are firmware compile-time constants baked into
the generated CDI, so tools always see consistent offsets for a given firmware):

| Backend | `SLOT_STRIDE` | 8 slots + 16 B global | Rationale |
|---|---|---|---|
| I2C EEPROM | 2,816 B (0xB00) | 22,544 B | 22 × 128 B pages; fits a 24LC256 with room for app config |
| FRAM | 2,816 B | 22,544 B | match EEPROM for layout commonality |
| Raw flash | 4,096 B (0x1000) | 32,784 B | one erase sector per slot |

---

## 2. Config Space Layout (space 0xFD, relative to ES_BASE)

### Global block — 16 B at ES_BASE + 0x0000

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0x00 | 1 | clock_select u8 | map: 0=Default Fast Clock, 1=Real-Time, 2=Alt 1, 3=Alt 2, 4=custom |
| 0x01 | 8 | clock_custom eventid | used when clock_select = 4; low 2 bytes ignored |
| 0x09 | 7 | reserved | zero |

### Slot n (n = 0…7) — at ES_BASE + 0x10 + n × SLOT_STRIDE

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0x000 | 1 | enable u8 | 0=disabled, 1=enabled |
| 0x001 | 1 | action u8 | 0=none, 1=Compile & Run, 2=Stop, 3=Validate; write-triggered, self-clears to 0 |
| 0x002 | 16 | slot name | string, NUL-padded |
| 0x012 | 384 | event table | 16 × { eventid 8 B, name 16 B } = 16 × 24 B |
| 0x192 | 160 | param table | 8 × { name 16 B, value int32 } = 8 × 20 B |
| 0x232 | 2048 | source text | NUL-terminated within the field |
| 0xA32 | — | pad to SLOT_STRIDE | reserved, zero |

Used bytes per slot: 2,610 (0xA32). Firmware maintains the per-slot CRC32 over
0x000–0xA31 internally at commit; it is not stored in this space (it lives beside the
slot in raw NVM, outside the CDI-visible window, so tools can't corrupt it).

Write-behavior rules the config handler enforces: a write touching any event-table
*name*, any param-table *name*, or the source text marks the slot dirty (recompile
required — reported in status until the next Compile & Run); a write touching only a
param *value* or an eventid is live (eventid edits re-register bindings without
recompile, since bytecode carries table indices, not IDs); writing `action = 1` on a
dirty or clean slot compiles and (re)starts it; `action = 2` stops all handlers but
keeps state; `action = 3` compiles and reports full status (error line/column/message
or success metrics) **without starting or stopping anything** — the round-trip an
external editor's Validate button rides on, using the node itself as the authoritative
checker so no tool ever reimplements the compiler.

---

## 3. Status / Monitor Space Layout (space 0x50, served live from RAM)

### Global status — 16 B at 0x0000

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0x00 | 1 | fasthour i8 | −1 until first sync |
| 0x01 | 1 | fastminute i8 | −1 until first sync |
| 0x02 | 1 | fastrunning u8 | |
| 0x03 | 1 | clock_synced u8 | |
| 0x04 | 1 | engine_version u8 | status/monitor layout revision |
| 0x05 | 1 | lang_major u8 | language version the node compiles |
| 0x06 | 1 | lang_minor u8 | |
| 0x07 | 9 | reserved | |

(Exposing the local clock here gives JMRI a one-refresh answer to "what time does this
node think it is" — the first question in any fast-clock dispute.)

### Slot n status — 256 B at 0x10 + n × 0x100

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0x00 | 1 | state u8 | 0=empty, 1=compile error, 2=stopped, 3=running, 4=faulted, 5=dirty (edited since last compile) |
| 0x01 | 1 | code u8 | compile-error or fault code per spec §5.5/§9 |
| 0x02 | 2 | line u16 | error/fault source line |
| 0x04 | 2 | column u16 | compile errors only |
| 0x06 | 2 | bytecode_size u16 | |
| 0x08 | 1 | handler_count u8 | |
| 0x09 | 1 | reserved | |
| 0x0A | 2 | latch_drops u16 | saturating |
| 0x0C | 2 | inbox_drops u16 | saturating |
| 0x0E | 2 | reserved | |
| 0x10 | 64 | message | compile/fault message string |
| 0x50 | 160 | monitor | 8 × { name 16 B, value int32 } — export names + live values |
| 0xF0 | 16 | reserved | |

---

## 4. CDI XML Skeleton

Replication groups keep the XML compact — one `<group replication='8'>` describes all
slots. Element order matches the byte layout above exactly; `<group offset>` spacers
express the pads. Abbreviated where repetition is obvious:

```xml
<cdi>
  <identification> … existing node identification … </identification>
  <acdi/>

  <segment space='253' origin='4096'>            <!-- 0xFD, ES_BASE=0x1000 -->
    <name>Logic Engine</name>
    <group>
      <name>Clock</name>
      <int size='1'>
        <name>Fast clock source</name>
        <map>
          <relation><property>0</property><value>Default Fast Clock</value></relation>
          <relation><property>1</property><value>Real-Time Clock</value></relation>
          <relation><property>2</property><value>Alternate Clock 1</value></relation>
          <relation><property>3</property><value>Alternate Clock 2</value></relation>
          <relation><property>4</property><value>Custom (below)</value></relation>
        </map>
      </int>
      <eventid><name>Custom clock ID</name></eventid>
      <group offset='7'/>                        <!-- reserved -->
    </group>

    <group replication='8'>
      <name>Programs</name>
      <repname>Program</repname>
      <int size='1'>
        <name>Enable</name>
        <map><relation><property>0</property><value>Disabled</value></relation>
             <relation><property>1</property><value>Enabled</value></relation></map>
      </int>
      <int size='1'>
        <name>Action</name>
        <map><relation><property>0</property><value>— none —</value></relation>
             <relation><property>1</property><value>Compile &amp; Run</value></relation>
             <relation><property>2</property><value>Stop</value></relation>
             <relation><property>3</property><value>Validate</value></relation></map>
      </int>
      <string size='16'><name>Program name</name></string>
      <group replication='16'>
        <name>Events</name>
        <repname>Event</repname>
        <eventid><name>Event ID</name></eventid>
        <string size='16'><name>Name (used in script)</name></string>
      </group>
      <group replication='8'>
        <name>Parameters</name>
        <repname>Parameter</repname>
        <string size='16'><name>Name (used in script)</name></string>
        <int size='4'><name>Value</name><min>-2147483648</min><max>2147483647</max></int>
      </group>
      <string size='2048'><name>Program source</name></string>
      <group offset='206'/>                      <!-- pad to SLOT_STRIDE (EEPROM: 0xB00-0xA32) -->
    </group>
  </segment>

  <segment space='80' origin='0'>                <!-- 0x50, read-only -->
    <name>Logic Engine Status</name>
    <group>
      <name>Clock</name>
      <int size='1'><name>Fast hour (-1 = not synced)</name></int>
      <int size='1'><name>Fast minute</name></int>
      <int size='1'><name>Running</name></int>
      <int size='1'><name>Synced</name></int>
      <int size='1'><name>Engine version</name></int>
      <int size='1'><name>Language version (major)</name></int>
      <int size='1'><name>Language version (minor)</name></int>
      <group offset='9'/>
    </group>
    <group replication='8'>
      <name>Programs</name>
      <repname>Program</repname>
      <int size='1'>
        <name>State</name>
        <map><relation><property>0</property><value>Empty</value></relation>
             <relation><property>1</property><value>Compile error</value></relation>
             <relation><property>2</property><value>Stopped</value></relation>
             <relation><property>3</property><value>Running</value></relation>
             <relation><property>4</property><value>Faulted</value></relation>
             <relation><property>5</property><value>Edited (recompile needed)</value></relation></map>
      </int>
      <int size='1'><name>Error/fault code</name></int>
      <int size='2'><name>Line</name></int>
      <int size='2'><name>Column</name></int>
      <int size='2'><name>Bytecode size</name></int>
      <int size='1'><name>Handlers</name></int>
      <group offset='1'/>
      <int size='2'><name>Latch drops</name></int>
      <int size='2'><name>Inbox drops</name></int>
      <group offset='2'/>
      <string size='64'><name>Message</name></string>
      <group replication='8'>
        <name>Watch</name>
        <repname>Variable</repname>
        <string size='16'><name>Name</name></string>
        <int size='4'><name>Value</name></int>
      </group>
      <group offset='16'/>
    </group>
  </segment>
</cdi>
```

Note the flash-backed build changes only the slot pad (`offset='1486'`) and `origin` —
nothing structural. The XML is emitted from the same constants as the firmware layout
(single source of truth in a header; M6 should generate the pad values, not hand-edit
them).

---

## 5. Firmware Hooks Required (M5/M6 checklist against OpenLcbCLib)

Config-write callback: dispatch the action byte (compile/stop, then clear to 0), mark
slots dirty on name/source writes, re-register bindings on eventid writes, and treat
param-value writes as live (no side effects beyond the store). Memory-read handler for
space 0x50: serve global clock state and per-slot status from RAM, filling monitor
values at read time from the VM's variable store. Get-Address-Space-Info: advertise
0x50 present and read-only; reject writes. Commit path: recompute and stash the slot
CRC (outside the CDI window), verify at boot before compiling, report `COMPILE_ERR`
with a CRC-specific code on mismatch rather than parsing corrupt text. CDI XML: served
from flash as usual; regenerate pads from the layout header at build time.

Open verification item for M5 (carried from earlier discussion): confirm OpenLcbCLib's
consumer/producer registration path accepts post-boot re-registration when eventid
fields are edited live, or wrap registration in a module that rebuilds the node's
tables on any binding change.
