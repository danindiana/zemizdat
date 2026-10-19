# 03 · State machine and participation semantics

## 1. Why one machine with permission bits instead of four modes

The four proposed modes differ only in *which candidates the carousel may draw from* and
*whether the radio may transmit*. Encoding them as four separate machines would duplicate the
receive path, storage and budgets four times. One machine parameterised by
`π ⊆ {RX, STORE, ORIG, FWD}` covers all of them; the UI exposes presets.

| Preset | π | Transmits | Carousel candidates | Beacons | Scan duty |
|---|---|---|---|---|---|
| OFF | ∅ | never | — | never | 0 |
| LISTEN | RX STORE | **never** (passive scan, no adv set) | — | never | δ_active / δ_idle |
| EXCHANGE | RX STORE ORIG | yes | own pamphlets only | optional | same |
| COURIER | RX STORE ORIG FWD | yes | everything stored | optional | same |

`STORE` without `RX` is meaningless (rejected by UI); `RX` without `STORE` ("browse only",
display then discard) is allowed and useful for a viewer that keeps nothing.

## 2. States

```
            power-on
               │
           ┌───▼────┐   flash scan, GC completion/rollback, index rebuild
           │ MOUNT  │──────────────────────────────────────────┐
           └───┬────┘                                          │ unrecoverable flash error
               │ ok                                            ▼
           ┌───▼────┐  battery < 10 %             ┌────────────────────┐
     ┌────►│ IDLE   │◄──────────────────────────► │ DORMANT (no radio) │
     │     └───┬────┘   battery ≥ 15 % (hyst.)    └────────────────────┘
     │         │ RX ∈ π
     │     ┌───▼──────────┐  frame decoded         ┌──────────────┐
     │     │ SCAN_IDLE    │───────────────────────►│ SCAN_ACTIVE  │
     │     │ δ = 0.05     │◄───────────────────────│ δ = 0.30     │
     │     └──────────────┘ 30 s with no frame     └──────┬───────┘
     │                                                    │ (ORIG ∨ FWD) ∈ π and
     │                                                    │ battery ≥ 20 % and tx budget > 0
     │                                             ┌──────▼───────┐
     └─────────────────────────────────────────────│ CAROUSEL     │  scheduler (§4–5 of spec)
              budget exhausted / battery < 20 % /   │ (in parallel │  runs alongside scanning
              user clears ORIG and FWD             │  with scan)  │
                                                    └──────────────┘
```

Inside SCAN_ACTIVE/CAROUSEL a sub-state **BURST** applies while ≤ `BURST_N` transmitters are
estimated in range: scan duty 1.0, event cap 100/s, suppressed picks refilled (spec §4). It is
what makes brief two-person encounters useful.

Transitions are local and immediate. Changing `π` takes effect at the next scheduler tick; a
device that loses FWD stops transmitting third-party items at once but keeps them stored
(storage and transmission are separate consents).

## 3. Per-mode specification

### LISTEN
* **Radio:** passive extended scanning only. No advertising set exists in the controller
  configuration (so a firmware bug in the scheduler cannot transmit). I5.
* **CPU:** frame parsing, SHA-256 per received chunk (≤ 19 per object), flash writes.
* **Storage:** commits objects that complete from overheard carousels.
* **Energy:** scan duty only; on nRF52840, 0.30 × 6.26 mA ≈ 1.9 mA radio while neighbours are
  present, 0.05 × 6.26 ≈ 0.3 mA otherwise [estimate from datasheet radio currents, CPU and
  regulator excluded].
* **What it can achieve:** whatever transmitting neighbours choose to send (Theorem F). It is
  invisible to beacon-based demand estimation; the carousel's `LISTEN_FLOOR` and age weighting
  are what serve it.
* **Failure:** surrounded only by devices that never transmit unprompted → receives nothing.
* **Security:** the only mode that discloses nothing about its library, and — because passive
  scanning emits no RF — nothing about its presence either (to be confirmed by experiment E-L).
  Physical carriage of a device is outside the protocol.

### EXCHANGE
* **Radio:** carousel limited to own pamphlets; optional beacons.
* **Discloses:** its own pamphlets (by sending them) and, if beacons are on, which buckets
  differ from neighbours.
* **Failure:** an author with only EXCHANGE devices around reaches only those it meets directly.

### COURIER
* **Radio:** full carousel; optional beacons.
* **Discloses:** its library over time (every transmission is an item it holds). Address
  rotation prevents linking by address but not by content: a courier carrying a rare set of
  pamphlets is recognisable by what it sends. This is intrinsic to forwarding.
* **Prioritisation without routing tables:** age weighting ("least recently heard") and, if
  enabled, bucket demand. No device ever keeps per-peer state.

### RELAY — not adopted in v1

The proposal was "live multi-hop forwarding where suitable neighbours are present". In a
connectionless broadcast design, the only thing RELAY could add over COURIER is *immediate*
retransmission of a just-received item. Analysis:

* Inside one interference domain every receiver already heard the original transmission;
  an immediate relay re-occupies the same shared airtime to serve the few who missed it — the
  carousel's age weighting does that anyway, with suppression.
* Across domains (another room), a relay helps only if some device is simultaneously in range
  of both. In crowds that is a person standing in a doorway; their COURIER carousel already
  serves both sides.
* Cost: higher duty cycle (to catch items fast) and more airtime per item.

So RELAY ≡ COURIER with a "fresh items first" bias. A v1 experiment (E3 variant) can test whether
a doorway relay measurably speeds room-to-room spread; until then the mode would be complexity
without evidence. Verdict: **REJECT as a separate mode; CONDITIONAL as a scheduling bias.**

## 4. Transmit permission check (normative pseudocode)

```c
bool may_transmit(const record *r) {
    if (!(perm & (ORIG | FWD)))        return false;   // LISTEN, OFF
    if (battery_pct < 20)              return false;
    if (tx_budget_remaining == 0)      return false;
    if (r->flags & FLAG_OWN)           return perm & ORIG;
    return perm & FWD;
}
```

## 5. Concurrency

Single-threaded event loop; radio callbacks enqueue frames into a fixed 16-entry ring (overflow
drops the newest frame — counted, never blocking). Flash commits are synchronous from the loop.
No locks are needed in the protocol engine.
