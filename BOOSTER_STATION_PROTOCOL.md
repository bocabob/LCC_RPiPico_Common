# Booster ↔ command station protocol

What `LCC_RPiPico_Booster` sends and takes, and what `LCC_RPiPico_CommandStation` reads and sends,
so the station can show and control every booster on the layout. Written 2026-11-13 (format version
1), from the decisions in the station's `work_plan.md` Phase 16 (the user, 2026-10-10). Both repos
follow this document. A change to a format here changes its version byte, and both repos together.

Everything is in each booster's **own event space**: `<booster node ID>.B0.xx`. So the station can
address any booster from its node ID alone, and nothing here needs configuring. These events are
separate from the booster's CDI-configurable events (Overload Trip/Clear, Power On/Off,
Warning/Normal), which stay for JMRI Logix users.

## 1. The fixed events

| Event | Direction | Payload | Meaning |
|---|---|---|---|
| `.B0.00` | booster produces | the status record (§2) | the booster's state |
| `.B0.01` | booster consumes | none | power on (also clears a latched trip) |
| `.B0.02` | booster consumes | none | power off |
| `.B0.03` | booster consumes | none | reset a latched trip: clears it; power comes back if it is commanded on |
| `.B0.04` | booster consumes | none | send your status record now |
| `.B0.10` | booster produces | the POM relay (§4) | a RailCom Channel 2 reply from this district |

`.B0.05`–`.B0.0F` and `.B0.11`–`.B0.FF` are reserved.

The booster registers what it produces and consumes, so it answers Identify Producers, Identify
Consumers and Identify Events for them. The station need not register anything to receive the
reports: OpenLcbCLib calls `on_pc_event_report_with_payload` for every event report with payload,
consumed or not.

## 2. The status record (`.B0.00`, version 1)

A PC Event Report with payload. Multi-byte fields are big-endian. After the 8-byte event ID:

| Offset | Size | Field |
|---|---|---|
| 0 | 1 | Magic: `0xB5` |
| 1 | 1 | Format version: `1` |
| 2 | 1 | State: 0 off, 1 on, 2 tripped, 3 no DCC input (commanded on, held off by the packet watchdog) |
| 3 | 1 | Reason for the state (§2.1) |
| 4 | 1 | Flags (§2.2) |
| 5 | 1 | The last trip's reason (§2.1: 5 or 6), 0 if none since boot |
| 6 | 2 | The current at the last trip, mA |
| 8 | 2 | Seconds since the last trip; 65535 for more, or for none |
| 10 | 2 | Trips since boot |
| 12 | 4 | Uptime, s |
| 16 | 4 | Seconds since it was last switched on; `0xFFFFFFFF` while it is off |
| 20 | 2 | Temperature, 0.1 °C, signed; `0x8000` with no reading |
| 22 | 12 | The first 12 bytes of the CDI node name, padded with 0 |

34 bytes, 42 with the event ID: six CAN frames.

### 2.1 Reason codes

| Code | Meaning | With state |
|---|---|---|
| 0 | none | on |
| 1 | not switched on since boot (it boots off) | off |
| 2 | commanded off: a CDI Power Off event, or the booster's console | off |
| 3 | commanded off by the station (`.B0.02`) | off |
| 4 | the layout's Emergency Off | off |
| 5 | short circuit or overcurrent: the firmware trip | tripped |
| 6 | over temperature: the cut-off | tripped |
| 7 | no valid DCC input | no DCC input |
| 8–255 | reserved (driver fault, undervoltage, retrying, …) | |

### 2.2 Flags

| Bit | Meaning |
|---|---|
| 0 | Valid DCC packets are arriving |
| 1 | RailCom cutouts are being seen |
| 2 | Reserved (a driver fault), 0 |
| 3 | The temperature sensor is not reading: the thermal cut-off cannot act |
| 4 | Follows the layout's Emergency Off (its CDI) |
| 5 | A trip here takes the whole layout off (its CDI): it sends Emergency Off |
| 6–7 | Reserved, 0 |

### 2.3 When it is sent

- Once the booster has logged in.
- On every change of state, reason, flags, trip count or node name, at most every 100 ms.
- On `.B0.04`.
- As a keep-alive: **every 5 s**, fixed. The station counts a booster lost after three missed:
  15 s without a record.

A reader checks the magic and the version and ignores a record it does not know.

## 3. Power and the layout

- **Boot:** a booster boots off (reason 1), as R15 holds it and as the station's own main track
  boots.
- **Following the layout** (CDI, "Follow Layout Emergency Off", default yes): the well-known
  Emergency Off (`01.00.00.00.00.00.FF.FF`) switches it off (reason 4). Clear Emergency Off
  (`…FF.FE`) switches it on, and so clears a trip, as the station's own track does. The station
  announces Emergency Off at login, so a booster that follows it reports at once. Per-booster on
  and off stay possible (`.B0.01`/`.B0.02`, the CDI's events); the next Clear Emergency Off
  switches every following booster on.
- **A trip** (CDI, "On a Trip", default this district only): it cuts this booster's track, latched
  until power is commanded on again. Set to the whole layout, the booster also sends Emergency
  Off. The command station's own main track follows the same rule, by its CDI's Trip Scope.

## 4. The POM relay (`.B0.10`, version 1)

The design and its reasons are in `LCC_RPiPico_CommandStation`'s `railcom_lcc_reporting.md`,
section E. A PC Event Report with payload, after the event ID:

| Offset | Size | Field |
|---|---|---|
| 0 | 1 | Format version: `1` |
| 1 | 1 | Flags: 0 (reserved) |
| 2 | 1 | P: the packet's length without its check byte (2–8) |
| 3 | P | The packet the cutout followed |
| 3+P | 1 | R: Channel 2's byte count (1–6) |
| 4+P | R | Channel 2's raw 4/8 codewords |

It is sent after a configuration-variable access packet (instruction `111x xxxx`) to a locomotive
address, when Channel 2 brought bytes.

## 5. Current and voltage: JMRI's meters

Current and voltage are not in the status record. They go as OpenLCB Location Services track meter
reports, which JMRI's meter window shows by itself and the station reads the same way: event
`01.02.<booster node ID>`, the format in the station's `callbacks_meters.h`. A booster sends three
analog blocks: "Track Current" (A), "Track Voltage" (V, estimated: VM − I × 15 mΩ − 0.45 V while on,
0 while off) and "Supply Voltage" (V). They are sent at the CDI's interval when a reading has moved by
more than its sensitivity, and at least once a minute.
