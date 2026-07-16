# EventScript Example Program Library — M1 Deliverable

Six worked programs, each with its slot setup (event bindings, parameters, exported
variables), source, and behavior notes. Two purposes: they are the design's proof
against real layout jobs, and they are the seed corpus for M2's golden tests — each
"behavior" paragraph below translates directly into a stimulus/expectation script for
the host harness. All programs have been hand-checked against spec v0.4's grammar.

A recurring idiom appears in several examples and deserves a name up front: the
**internal recompute event**. v1 has no user functions, so logic that several handlers
share is placed in a handler for an event the slot both produces and consumes —
`produce(ev_recalc)` anywhere acts as a subroutine call, because locally produced
events loop back to local consumers. It costs one event-table entry and one network
report, and it composes with everything else.

---

## 1. Grade Crossing with Flashers and Island Timeout

Flashers lead the gate down, island clearance (with a tunable timeout) brings it back
up, flashers trail. The timeout is a CDI parameter, so the operator adjusts it without
touching code.

Bindings: `ev_approach` (consumed), `ev_island_clear` (consumed), `ev_flashers_on`,
`ev_flashers_off`, `ev_gate_lower`, `ev_gate_raise` (produced).
Parameter: `island_timeout` (ms, default 30000, min 5000, max 120000).

```
retain gate_down = false

on ev_approach:
    if gate_down then stop end
    produce(ev_flashers_on)
    sleep 3s                        # flashers lead the gate
    produce(ev_gate_lower)
    gate_down = true
    wait ev_island_clear timeout island_timeout
    if timedout then log(1) end     # island never cleared — flag it
    produce(ev_gate_raise)
    sleep 4s
    produce(ev_flashers_off)
    gate_down = false
end
```

Behavior notes / golden tests: a second `ev_approach` during the cycle hits the
`gate_down` guard and stops (and the one-deep latch queues at most one re-run — assert
exactly one extra cycle after three rapid approaches); `timedout` path logs line 9 and
still raises the gate; changing `island_timeout` in CDI affects the *next* wait with no
recompile.

Exercises: `wait`/`timeout`/`timedout`, `sleep`, `stop`, `log`, parameter read inside
a timeout expression, retained guard, pending-latch semantics.

---

## 2. Three-Aspect ABS Signal

Signal protecting block B, considering B and the block beyond (C). Occupancy events
maintain retained state; one recompute handler owns the aspect decision — the internal
recompute event idiom.

Bindings: `ev_b_occupied`, `ev_b_clear`, `ev_c_occupied`, `ev_c_clear` (consumed),
`ev_sig_red`, `ev_sig_yellow`, `ev_sig_green` (produced), `ev_recalc` (produced and
consumed — internal).

```
retain b_occ = false
retain c_occ = false

on startup:
    produce(ev_recalc)

on ev_b_occupied:
    b_occ = true
    produce(ev_recalc)
end

on ev_b_clear:
    b_occ = false
    produce(ev_recalc)
end

on ev_c_occupied:
    c_occ = true
    produce(ev_recalc)
end

on ev_c_clear:
    c_occ = false
    produce(ev_recalc)
end

on ev_recalc:
    if b_occ then
        produce(ev_sig_red)
    elif c_occ then
        produce(ev_sig_yellow)
    else
        produce(ev_sig_green)
    end
end
```

(Deliberate wart in line 5: `on startup:` with no `end` — this program must **fail to
compile** with a clear "expected 'end'" error at the right line. Keep it in the corpus
both ways: the corrected version as a golden run, the wart as a §9 error-message test.
Every library needs one intentional mistake; this is ours.)

Behavior notes: aspect follows the truth table for all four occupancy combinations;
after power loss mid-session, retained occupancy plus the startup recompute re-emits
the correct aspect (assert exactly one aspect event at boot); B and C events arriving
in the same slice produce one recompute each, in order.

Exercises: `elif` chains, retained state across reboot, startup handler, internal
recompute event, multi-handler coordination — plus one intentional syntax error.

---

## 3. Turnout Interlock with Local Lockout

Requests are honored only when the OS section is clear *and* the maintainer's lockout
toggle (a physical switch sampled on line 2) is off. Position is exported so the node
application — or JMRI, via the monitor region — can observe it.

Bindings: `ev_req_normal`, `ev_req_reverse`, `ev_os_occupied`, `ev_os_clear`
(consumed), `ev_cmd_normal`, `ev_cmd_reverse`, `ev_denied` (produced).
Line 2: lockout switch (input).

```
retain os_occ = false
export retain position = 0      # 0 = normal, 1 = reverse

on ev_os_occupied:
    os_occ = true
end

on ev_os_clear:
    os_occ = false
end

on ev_req_normal:
    if os_occ or getline(2) == 1 then
        produce(ev_denied)
        stop
    end
    produce(ev_cmd_normal)
    position = 0
end

on ev_req_reverse:
    if os_occ or getline(2) == 1 then
        produce(ev_denied)
        stop
    end
    produce(ev_cmd_reverse)
    position = 1
end
```

Behavior notes: requests under occupancy or lockout produce exactly `ev_denied` and
nothing else; `position` in the monitor region tracks the last honored command;
`ev_cmd_*` drives an RR-CirKits-style stall-motor daughter card via whatever node
consumes it — this slot neither knows nor cares.

Exercises: `getline`, `or` short-circuit, `stop` as guard exit, `export retain`,
denial-indication pattern.

---

## 4. Fascia Route Dispatcher with Lamp Feedback

One button cycles through routes; each selection immediately produces that route's
event and blinks an acknowledgment lamp. Route count is a CDI parameter so the same
script serves 2-, 3-, and 4-route yards.

Bindings: `ev_button` (consumed), `ev_route1` … `ev_route4` (produced).
Parameter: `route_count` (default 4, min 1, max 4). Line 1: fascia lamp (output).

```
export retain route = 1
var i = 0

on ev_button:
    route = route + 1
    if route > route_count then route = 1 end
    if route == 1 then produce(ev_route1) end
    if route == 2 then produce(ev_route2) end
    if route == 3 then produce(ev_route3) end
    if route == 4 then produce(ev_route4) end
    i = 0
    while i < route do              # blink the lamp 'route' times
        setline(1, 1)
        sleep 200ms
        setline(1, 0)
        sleep 200ms
        i = i + 1
    end
end
```

Behavior notes: with `route_count = 3`, presses cycle 1→2→3→1; the blink count always
equals the selected route number (a human-readable indicator with zero extra
hardware); a press *during* the blink sequence latches one re-run — assert the latched
run sees the already-incremented `route`. Lowering `route_count` below the current
`route` self-heals on the next press.

Exercises: `while` with counter, `setline`, `sleep` inside a loop (suspension mid-loop
— a good VM stress case), live parameter governing control flow, `export retain`.

---

## 5. Startup Position Restoration

The slot passively shadows turnout command events from anywhere on the layout (panel,
throttle, another script), retains the last position, and replays it after boot so
stall motors resynchronize. Note both events are consumed *and* produced by this slot
— the spec's "both directions" case.

Bindings: `ev_cmd_normal`, `ev_cmd_reverse` (consumed **and** produced).

```
retain position = 0

on ev_cmd_normal:
    position = 0
end

on ev_cmd_reverse:
    position = 1
end

on startup:
    sleep 2s                        # let drivers finish their own boot
    if position == 1 then
        produce(ev_cmd_reverse)
    else
        produce(ev_cmd_normal)
    end
end
```

Behavior notes: the startup replay loops back into this slot's own consumer handler,
which harmlessly rewrites `position` to its current value — assert no oscillation and
exactly one produced event at boot. Also the golden test for boot-time
Producer/Consumer Identified: both events must report in both roles with valid state
derived from `position`.

Exercises: dual-direction bindings, local loopback, `sleep` in startup, retained
persistence as the *point* of the program rather than a supporting detail.

---

## 6. Town Lights and Mill Whistle on the Fast Clock

Scheduled actions via `at`, with state convergence via register range-checks — the
exact split §5.6 prescribes: the whistle is instantaneous (fires only when its minute
genuinely passes), while lighting is *state* (converges after any time-set, even
though skipped `at` triggers never fire).

Bindings: `ev_town_lights_on`, `ev_town_lights_off`, `ev_mill_whistle` (produced).

```
retain lights_on = false

at 19:00:
    produce(ev_town_lights_on)
    lights_on = true
end

at 6:00:
    produce(ev_town_lights_off)
    lights_on = false
end

at 7:00:
    produce(ev_mill_whistle)
end

every 10s:
    if fasthour >= 0 then                    # guard: clock synced yet?
        if fasthour >= 19 or fasthour < 6 then
            if not lights_on then
                produce(ev_town_lights_on)
                lights_on = true
            end
        elif lights_on then
            produce(ev_town_lights_off)
            lights_on = false
        end
    end
end
```

Behavior notes / golden tests (driven through the injected clock module): normal
running at 60:1 fires each `at` exactly once per fast day; a time-set from 14:00 to
21:00 fires *no* `at` triggers (discontinuity) but the next `every` tick turns the
lights on; a drift correction of +2 fast minutes across 19:00 *does* fire the 19:00
trigger; before first sync, the `fasthour >= 0` guard keeps everything quiet; a
backward-running clock passing 07:00 sounds the whistle.

Exercises: `at` triggers, `every` trigger, fast-clock registers, −1 sentinel guard,
midnight-spanning range, discontinuity vs. drift semantics, state-convergence pattern.

---

## Feature Coverage Matrix

| Feature | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| `on event` handler | ✓ | ✓ | ✓ | ✓ | ✓ | |
| `on startup` | | ✓ | | | ✓ | |
| `every` | | | | | | ✓ |
| `at` | | | | | | ✓ |
| `wait` / `timeout` / `timedout` | ✓ | | | | | |
| `sleep` | ✓ | | | ✓ | ✓ | |
| `while` | | | | ✓ | | |
| `if` / `elif` / `else` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `stop` | ✓ | | ✓ | | | |
| `log` | ✓ | | | | | |
| `setline` / `getline` | | | ✓ | ✓ | | |
| Parameters (live) | ✓ | | | ✓ | | |
| `export` | | | ✓ | ✓ | | |
| `retain` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Fast-clock registers | | | | | | ✓ |
| Internal recompute event | | ✓ | | | | |
| Dual-direction binding | | | | | ✓ | |
| Pending-latch assertion | ✓ | | | ✓ | | |
| Intentional compile error | | ✓ | | | | |

Not yet exercised anywhere: the `event(…)` literal escape hatch (add one variant of
example 5 using a literal to the M2 test set — it should stay out of the showcase
library, being the discouraged path), `%`, unary minus, and hex literals (pure
expression-evaluator unit-test territory, not example territory).
