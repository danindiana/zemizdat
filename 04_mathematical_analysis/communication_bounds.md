# 04 · Communication bounds and the airtime model

Script: `scripts/airtime_model.py` → `results/airtime_model.json` [executed; THEORETICAL
ESTIMATE]. All PDU durations follow from Bluetooth Core PDU formats; channel behaviour is
unslotted ALOHA without capture (pessimistic); `p_loss = 0.10` is an assumption.

## 1. What one BLE-5 extended advertising event costs

| PDU | Bytes on air | Duration |
|---|---|---|
| ADV_EXT_IND (1M PHY, ext header 7 B: flags, ADI, AuxPtr) | 17 | **136 µs**, sent on each of channels 37, 38, 39 |
| AUX_ADV_IND / AUX_CHAIN_IND, 255 B payload (2M PHY) | 266 | **1 064 µs** (2 120 µs on 1M PHY), on one of 37 secondary channels |

Raw PHY rate (2 Mbit/s) is not application throughput: of 1 064 µs, 236 B are a ZEMIZDAT frame
and 220 B of that are pamphlet bytes (≈ 1.65 Mbit/s instantaneous), and the event also spends
3 × 136 µs on primary pointers and suffers collisions.

## 2. Domain goodput and chain length

For an interference domain carrying `R` events/s with chains of `L` AUX PDUs:

```
G_p = R·τ_p          (each event hits each primary channel once)
G_a = R·L·τ_a / 37   (AUX PDUs spread over 37 secondary channels)
a   = e^{−2 G_a} (1 − p_loss)             per-AUX-PDU success
frames decoded per event by an always-on receiver = e^{−2 G_p} · Σ_{k=1..L} a^k
```

Optimised over `R` for each `L`:

| L | R* (events/s) | frames/s | kB/s of chunk payload | G_p | G_a | a |
|---|---|---|---|---|---|---|
| 1 | 3 030 | 1 005 | 221 | 0.41 | 0.09 | 0.76 |
| 2 | 2 300 | 1 437 | 316 | 0.31 | 0.13 | 0.69 |
| **3** | **1 750** | **1 525** | **336** | 0.24 | 0.15 | 0.67 |
| 4 | 1 370 | 1 470 | 323 | 0.19 | 0.16 | 0.66 |
| 6 | 910 | 1 254 | 276 | 0.12 | 0.16 | 0.66 |
| 7 | 770 | 1 147 | 252 | 0.10 | 0.15 | 0.66 |

Conclusions: (i) without chaining the primary channels are the bottleneck; (ii) beyond ~3 PDUs,
chain truncation (a lost PDU loses the rest of the chain) dominates; (iii) the whole domain
moves only ~1 500 frames/s ≈ 336 kB/s of pamphlet bytes, no matter how many devices are in it.
**A crowd adds receivers, not capacity.**

## 3. Unregulated advertising collapses

Each device at 10 events/s (100 ms interval), `L = 6`, one domain:

| transmitters | G_p | G_a | frames/event | domain frames/s |
|---|---|---|---|---|
| 10 | 0.01 | 0.02 | 3.68 | 368 |
| 50 | 0.07 | 0.09 | 2.21 | 1 105 |
| 100 | 0.14 | 0.17 | 1.25 | **1 249 (peak)** |
| 200 | 0.27 | 0.34 | 0.47 | 947 |
| 500 | 0.68 | 0.86 | 0.049 | 245 |
| 1 000 | 1.36 | 1.73 | 0.0019 | 19 |
| 3 000 | 4.08 | 5.18 | ~0 | 0 |

So "simple repeated broadcasting" is a good protocol up to ~100 transmitters per interference
domain and a failed one beyond a few hundred. Density-adaptive rate control is not
sophistication; it is the condition for the broadcast family to work at all in Environment 1.
The simulator reproduces this (BCAST vs BCAST_RC, group A).

## 4. Broadcast vs unicast: the real factor

Bits that must cross the air for 3 000 devices to each obtain 3 000 × 1 KiB pamphlets:

* Unicast (each delivery separate): `N(M−1)·L ≈ 7.7 × 10¹⁰ bit`. On one 200 kbit/s channel that is
  107 h (Gemini's figure). BLE connections hop over 37 data channels; at an *assumed* 13.6 Mbit/s
  effective aggregate (37 × 2 Mbit/s × 0.5 link efficiency × e⁻¹ ALOHA factor) it is ≈ 1.6 h.
* Broadcast: one copy per **reception tile**. With ~10 m reception range in a ~55 × 55 m hall
  that is ≈ 30 copies → ≈ 7.7 × 10⁸ bit, **≈ 100× less** than unicast.

The gain is "receivers per tile", not "N". It disappears in sparse encounters (two devices: a
broadcast serves one receiver, exactly like unicast) — which is why Environment 3 behaves so
differently (see `convergence.md`).

## 5. Per-receiver bound in the auditorium

With domain goodput 1 254–1 525 frames/s split over ≈ 30 tiles and 30 % scan duty, a receiver
decodes ≈ 12.5–15 frames/s. Receiving 3 000 pamphlets × 6 frames therefore takes **≥ 20–24 min
even with a perfect scheduler** [estimate]. Halving scan duty doubles this. This is the honest
answer to "can 3 000 devices exchange everything during a conference session?": only if the
session is long, or if not everyone needs everything.

## 6. Where is the bottleneck? (mission §7)

| Environment | Binding constraint | Not binding |
|---|---|---|
| E1 single auditorium | shared airtime of one interference domain; receiver scan duty | processing, flash writes, discovery |
| E2 rooms/buildings | per-room airtime early; then **inter-room mixing** (people moving) | radio capacity overall (rooms reuse spectrum) |
| E3 city, 24 h | **contact opportunities × contact duration** (temporal graph) | airtime (encounters are small) |

Battery is binding in all three for an ESP32-S3 device and in none over a day for an nRF52840
(see `05_hardware/battery_budget.md`). Session setup is binding only for pairwise designs.

## 7. ESP-NOW comparison [estimate]

A 1 KiB pamphlet = 6 frames ≈ 1.4 kB → one ESP-NOW v2 packet. At the default 1 Mbit/s that is
≈ 11.5 ms of airtime per pamphlet, against 2 events × (3 × 0.136 + 3 × 1.064) ms ≈ 7.2 ms for BLE.
At 6 Mbit/s OFDM (if configured) ≈ 2 ms. CSMA/CA turns the ALOHA `e^{−2G}` into roughly
contention-free access at moderate load. ESP-NOW is therefore plausibly *better* on raw airtime
and worse on energy (Wi-Fi receive current) and portability. UNRESOLVED; bench test E5b.
