# ZEMIZDAT-PROTO-1.0 — candidate specification

**Status:** candidate draft, pre-prototype. Normative where it says MUST. Items marked
**[E-x]** depend on an experiment in `08_verification/test_plan.md`; their values are
provisional. Executable reference: `reference_py/zmproto.py` (codec, reassembly, store) and
`reference_c/zm_core.c` (receive path). The scheduler is specified here in pseudocode and
modelled in `06_simulation/simulator.py`; it has **not** run on a radio.

Byte layouts are in `wire_format.md`; this document does not repeat them.

---

## 0. Architecture in one paragraph

Devices never connect to each other. Everything is a connectionless BLE 5 extended
advertisement that anyone in range may decode. Each pamphlet is an immutable object named
by a hash-list identifier; it travels as a small manifest plus ≤ 19 chunks of 220 bytes, each
chunk verifiable on arrival, so pieces may be collected from different senders at different
times. Each device that is permitted to transmit runs a **carousel**: at a rate set by a
density-adaptive controller, it picks one of its permitted pamphlets — preferring ones it has
not heard anyone else send recently — and sends a 3-PDU chained event carrying a sliding window of
that pamphlet's frames. A device that overhears a frame of a pamphlet it holds, and whose bytes
match its own copy, treats that pamphlet as recently served and deprioritises it (verified
suppression). A device whose permissions are only RX+STORE never transmits anything. Storage
is a crash-safe log on NOR flash. Firmware updates are a separate plane and never required for
the data plane.

## 1. Constants

| Name | Value | Basis |
|---|---|---|
| `FRAME_MAX` | 236 B | fits one AD structure in an AUX PDU with margin |
| `CHUNK` | 220 B | `FRAME_MAX − 16` |
| `CPO_MAX` | 4 064 B | ≤ 19 chunks |
| `L_CHAIN` | 3 PDUs per event | optimum of the airtime model [estimate]; **[E5]** |
| `G_P`, `G_A` | 0.25 primary, 0.15 secondary | ALOHA margin [estimate]; **[E5]** |
| `R_TARGET` | `min(G_P/τ_p, G_A·37/(L_CHAIN·τ_a))` ≈ 1 739 events/s per interference domain | τ_p = 136 µs, τ_a = 1 064 µs [spec-derived] |
| `λ_MIN`, `λ_MAX` | 0.05, 25 events/s per device | energy cap |
| `I_REP` | 2 s | minimum interval between a device's own sends of one pamphlet |
| `AGE_CAP` | 600 s | cap of the "not heard for" weight |
| `EPS` | 0.05 | weight floor (liveness, `liveness.md`) |
| `LISTEN_FLOOR` | 0.3 | fraction of events kept when all beaconing neighbours match |
| `K_SLOT` | 8 (4 on 32 KB MCUs) | staging slots |
| `SLOT_TIMEOUT` | 120 s | |
| `δ_active`, `δ_idle` | 0.30, 0.05 scan duty | energy budget **[E6]** |
| `T_SDB` | 4 s | only if beacons enabled |
| `BURST_N` | 8 | ≤ this many transmitters estimated nearby → burst mode |
| `δ_burst`, `λ_BURST` | 1.0 scan duty, 100 events/s | burst mode (sparse contacts) |

## 2. Permissions and modes

Four orthogonal bits, set only by the owner through the physical UI:

| Bit | Grants |
|---|---|
| `RX` | scanning, reassembly |
| `STORE` | committing verified objects to flash |
| `ORIG` | transmitting **own** pamphlets |
| `FWD` | transmitting **third-party** pamphlets |

User-facing presets: **LISTEN** = RX+STORE; **EXCHANGE** = RX+STORE+ORIG; **COURIER** =
RX+STORE+ORIG+FWD. The proposed fifth mode **RELAY** is not adopted (see `state_machine.md`
§RELAY). A device MUST NOT transmit any radio packet when neither ORIG nor FWD is set; in
that state it MUST use passive scanning and MUST NOT create an advertising set.

## 3. Discovery

There is no separate discovery phase. A frame is discovery. Devices learn of each other only
through overheard frames and never learn a stable identity:

* Advertising MUST be non-connectable and non-scannable. It SHOULD be anonymous (no AdvA). If
  the stack cannot omit AdvA, the address MUST be a non-resolvable private address re-drawn at
  least every 60 s and whenever the set of pamphlets the device is advertising changes.
* The Advertising Set ID and the ADI `DID` MUST be re-drawn with the address.
* Event timing is a Poisson process at the current rate `λ` (exponential gaps, re-drawn per
  event) — no periodic train that could be fingerprinted by phase.
* Scanning: passive; scan window/interval chosen to give duty `δ_active` while any ZEMIZDAT
  frame was decoded in the last 30 s, else `δ_idle`.

## 4. Rate control (congestion response)

Every device permitted to transmit runs:

```
every W = 2 s ± U(0, 0.5 s):
    H   ← ZEMIZDAT primary pointers decoded in the window ÷ seconds actually scanned
    Ĥ   ← κ_INT · H                         # interference-range correction, see below
    R̂   ← smaller root of  Ĥ = R e^{-2 R τ_p}   (Newton, 3 iterations; if Ĥ ≥ 1/(2eτ_p),
                                                  treat as saturated: R̂ = 1/(2τ_p))
    λ   ← clamp( λ · (R_TARGET / max(R̂, 1))^{1/2}, λ_MIN, λ_MAX )
```

Each device ends up with roughly `R_TARGET / (transmitting devices in the domain)`, with no
identities and no coordination. **Known weakness, unresolved:** a device can only count
transmitters it can *decode*, but it is interfered with by transmitters it cannot decode. In a
hall where interference range is ~3.5× reception range, `κ_INT ≈ (r_int/r_rx)² ≈ 10` would be
needed; a wrong `κ_INT` either wastes airtime (too high) or collapses the channel (too low). The
simulator's baseline gives the controller the true domain population (an idealisation).
Candidate observables that see undecodable interferers — RSSI energy sampling, the controller's
"truncated chain" status ratio — are radio-stack specific. **[E5 decides; see RESEARCH_QUESTIONS
Q1.]**

**Burst mode (sparse contacts).** When `R̂ / λ` (estimated number of transmitters in range)
is ≤ `BURST_N`, airtime is not the scarce resource — contact time is. The device then scans at
`δ_burst = 1.0`, raises its cap to `λ_BURST`, and (§5) replaces suppressed picks instead of
skipping them. It leaves burst mode as soon as the estimate exceeds `BURST_N` or 30 s pass
without decoding any frame. Simulation: in the 24-hour city model this one rule moves HYBRID
from ≈ 25 % to ≈ 90 % mean completeness at 12 h, matching pairwise anti-entropy for couriers
while still serving listeners, for ≈ 60 % more radio energy [simulated, `06_simulation/README.md`].

On top of rate control, the device MUST back off to `λ_MIN` for 30 s if its own last 20
transmitted events were all followed by overhearing ≥ 5 other events within 2 ms of its own
start (gross collision indicator), and MUST respect the user's transmit budget (§9).

## 5. Carousel scheduling (what to send)

```
on each scheduled event:
    cand ← (FWD ? S : {own pamphlets}) restricted to ORIG/FWD permissions
    cand ← { p ∈ cand : now − last_sent_by_me[p] ≥ I_REP }
    if cand = ∅: skip event (do not transmit)
    cand ← cand ∖ {p : a verified frame of p from another device was heard in the last 1 s}
           (in burst mode the event is then filled from the remainder; in crowd mode it is
            skipped — freeing shared airtime is the point of suppression)
    w[p] ← (EPS·w̄ + demand[bucket(p)]) · (1 + min(now − heard[p], AGE_CAP))
             where heard[p] = last time a VERIFIED frame of p was overheard (or sent by me)
             and demand[b] = number of cached beacons whose digest for bucket b differs from mine
                             (all-ones if beacons are disabled)
    if beacons enabled and demand ≡ 0: transmit this event only with probability LISTEN_FLOOR
    p ← sample cand with probability ∝ w
    off ← uniform(0 … n_frames(p) − 1)
    send event: frames [manifest, c_0, …, c_{n−1}] cyclically from off, L_CHAIN frames
    heard[p] ← now; last_sent_by_me[p] ← now
```

**Release in crowd (author privacy, recommended default).** A device holding an own pamphlet
that has never been heard from anyone else SHOULD transmit it only while its rate-control
estimate `R̂` indicates at least ~20 transmitting devices nearby, so that the first sighting of
a new id does not single out a lone transmitter. This bounds, but does not defeat, direction
finding by a determined observer.

**Verified suppression.** When a device overhears a FRAG of `p ∈ S` it compares the chunk with
its own copy (a 220-byte memcmp against flash). Only on equality does it set `heard[p] ← now`.
A forged header for `p` therefore never suppresses an honest holder (I10). Manifests are
self-certifying: an overheard manifest whose computed `sid` is in `S` also counts.

*Rationale from simulation.* At N = 1 000 in one hall, removing the `heard`-age term costs more
than removing beacon digests (see `06_simulation/README.md`, group F). The demand term is
therefore optional (§7).

## 6. Receiving

```
on frame f (already filtered by company id):
    parse strictly (wire_format §7); on error drop
    if type = SDB: if beacons enabled: cache (salt, digests) in a 32-entry ring; return
    if sid(f) ∈ index ∪ tombstones:
        if FRAG and bytes equal own copy: heard[p] ← now
        return
    if MANIFEST: open slot (or ignore if no free slot and none older than SLOT_TIMEOUT)
    if FRAG:   total = 1 → self-certify, complete
               else: slot must exist with manifest; leaf must match; store chunk
    on completion: validate CPO → ADMIT (§9) → COMMIT (§8) → index insert → heard[p] ← now
```

Partial objects live in RAM slots and are lost on reboot (acceptable: they are re-collected).
Devices with spare flash MAY persist slots in a staging sector; chunk verification makes
that safe.

## 7. Inventory reconciliation (optional summary beacons)

Beacons (SDB, `wire_format §3.3`) are **OFF by default in v1** and MAY be enabled by the owner
on EXCHANGE/COURIER devices. They are never sent by LISTEN devices.

```
every T_SDB ± U(0, 1 s), if enabled and transmit budget allows:
    salt ← 4 random bytes
    for b in 0..63: digest[b] ← trunc16( SHA-256( salt ‖ sid64s of bucket b in index order ) )
    wants ← up to 4 sid64 of open slots with a manifest
    send SDB as its own event (1 PDU)
on SDB received: recompute my digests under its salt (one streaming pass over the index:
    3 000 × 8 B hashed ≈ 24 KB, a few ms with the SoC SHA engine) → demand[b] += (mine ≠ theirs);
    a wanted sid64 that I hold gets heard[p] ← −∞ (top priority)
```

Why optional: beacons cost one event per device every 4 s — negligible in small groups but a
large share of the event budget in a crowd (≈ 35 % at 3 000 devices per hall, where each device
gets < 1 event/s), disclose which buckets differ (and, for
small libraries, enough to test guesses about contents), and in dense crowds add little over
overhearing. In sparse encounters they also brought nothing: in the 24-hour city simulation
HYBRID reached 100 % with beacons on and off alike; at 3 000 devices per hall they cost ≈ 4
points by consuming event budget [simulated, groups C, H].

Exact pairwise reconciliation (sorted inventory, IBLT, rateless IBLT) is **not** part of v1;
`synchronization.md` explains when it would be worth adding (courier-to-courier bulk sync with
M ≥ 10⁴ and small differences).

## 8. Storage

Normative layout and recovery: `storage.md`; executable reference `zmproto.Store`.
Summary: 4 KiB sectors with a 12-byte header (magic, sequence, open/closed); records =
48-byte header (state u16, len u16, id[32], reserved u8, flags u8, reserved, dead u16) + CPO; record
state `FFFF → FFFE → FFFC → FFF8` by clearing bits; deletion clears a separate `dead` field;
one erased spare sector always kept; GC compacts the oldest sector into the spare. Index =
sorted RAM array of `(sid64, address)` rebuilt at mount (12 B/entry).

## 9. Budgets and admission

All enforced locally; none needs other devices' cooperation.

| Budget | Default | Enforcement |
|---|---|---|
| storage capacity `C` | owner-set, ≤ flash | admission refuses when full (after eviction rule) |
| admissions | 60 per minute token bucket | refuse when empty |
| transmit events | owner-set per hour (default 20 000) | scheduler skips when exhausted |
| radio-on time | via `δ_active/δ_idle` and an hourly cap | scanner duty reduced when exceeded |
| battery reserve | stop all transmission below 20 %, stop scanning below 10 % | hard |
| flash writes | implied by admissions; endurance is not binding (see `storage.md`) | — |

**Admission default (chosen from simulation group E).** A token bucket of 60 admissions per
minute (burst 60) for all incoming objects, regardless of source. Rationale: under a continuous
flood it held honest completeness at 0.82–0.88 where naive admission fell to 0.24–0.53; in the
benign case it refused ≈ 4 300–5 200 completions per device during the initial surge of a
500-device hall (all later re-received), with no change in median time to 50/80/90 % coverage at
the simulator's 60-second resolution [simulated, N = 500, capacity 600]. The quota trades a
slower start for flood resistance; owners of high-capacity devices may raise it.

**When storage is full.** Refuse new objects, except that an unpinned object admitted ≥ 24 h ago
may be evicted (oldest first) to make room. Own pamphlets and user-pinned items are never evicted.
This lets a device keep circulating across days without letting today's flood displace today's
items. (The 24-hour rule is not simulated.)

**Not adopted: time-stratified eviction.** It looked attractive analytically, but under a
*continuous* flood every epoch fills with junk and the eviction churn removes honest items too:
0.39–0.60 in group E, below the plain quota. Theorem D says no content-neutral policy prevents
damage; the quota is the cheapest one that bounds it best in our tests.

## 10. Security mechanisms in the data plane

Defensive parsing (wire_format §7); per-chunk leaf verification; whole-object id check;
CPO validation; static memory; strict caps (`CPO_MAX`, `K_SLOT`, TLV length); admission
quota; refusal when full; verified suppression; no identities, no counters that a Sybil
could inflate. **Replays** are harmless: an object is immutable, a re-sent frame of a held
object is dropped (and counts as "heard"). There is no message whose meaning depends on
freshness. Optional future extensions (v2, not specified): author signatures in TLV 0x10;
event manifests for completeness checking; rateless-IBLT courier sync.

## 11. Versioning

* Frame version nibble: a receiver MUST ignore frames whose version it does not implement.
  v2 frames MUST use a new version nibble; they cannot be misparsed by v1 devices.
* CPO version byte: content ids are permanent; a v2 device MUST still accept and forward v1
  objects unchanged. Ids never change across firmware versions.
* No negotiation exists or is needed (connectionless). Mixed populations simply ignore each
  other's unknown frames; a v2 device SHOULD keep transmitting v1 frames for v1 objects.

## 12. Failure handling

| Condition | Behaviour |
|---|---|
| power loss anywhere | mount-time recovery; I6 (tested at every byte, including during GC) |
| malformed frame | dropped before any state change |
| interrupted transfer | chunks stay in the slot until `SLOT_TIMEOUT`; collected later from anyone |
| storage full | refusal (or eviction of unpinned items older than 24 h); user notified |
| radio unavailable / channel saturated | rate control to `λ_MIN`; UI shows "channel busy"; data plane resumes automatically |
| repeated encounters with the same devices | nothing is sent that `heard[]` shows was recently served; identical-library beacons (if enabled) drop transmissions to `LISTEN_FLOOR` |
| flash read-back mismatch | record killed, sector closed, retried later |
| clock skew | irrelevant: only local monotonic time is used, never compared across devices |

## 13. Dependency on radio-stack APIs

| Function | NimBLE (ESP32-S3) | Zephyr (nRF52840) | Risk |
|---|---|---|---|
| ext. non-conn. non-scan. adv. with ≥ 720 B data (chaining) | `ble_gap_ext_adv_*` | `bt_le_ext_adv_*` | **must verify chaining length on ESP32-S3 [E1]** |
| anonymous advertising | `anonymous` flag | `BT_LE_ADV_OPT_ANONYMOUS` | verify controller support [E1] |
| passive extended scanning, chained report reassembly | `ble_gap_ext_disc` | `bt_le_scan_start` + `BT_LE_SCAN_OPT_*` | host buffer sizes |
| report rate the host can absorb | — | — | **[E5]** (`host_rate` assumption: 200/s) |
| observable for interference load | not standard | RSSI sampling via radio driver | **[E5]**, §4 weakness |

Everything else (parsing, hashing, storage, scheduling) is portable C99.
