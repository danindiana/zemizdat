# 02 · Comparison of candidate architectures and verdicts

Evidence types: [estimate] = `04_mathematical_analysis/scripts`; [simulated] = `06_simulation`
(numbers in `04_mathematical_analysis/convergence.md`); [executed] = reference code tests.
No hardware measurements exist yet.

## 1. Head-to-head (mean completeness of honest receivers; LISTEN devices in brackets)

| Scenario | A: BCAST (10 Hz) | A': BCAST + rate control | B: pairwise AE | C+D: HYBRID v1 |
|---|---|---|---|---|
| hall, 100 devices, 1 h | 1.00 [1.00] | 1.00 [1.00] | 0.80 [0] | 1.00 [1.00] |
| hall, 1 000 devices, 1 h | 0.39 | 0.61 | 0.80 [0] | **0.95** [0.95] |
| hall, 3 000 devices, 1 h | **0.00** | 0.36 | 0.28 [0] | **0.40** |
| hall, 5 000 devices, 1 h | 0.00 | 0.23 | 0.10 [0] | **0.25** |
| 6 rooms × 500, walking, 1 h | — | 0.65 | 0.75 [0] (couriers 0.95) | **0.98** [0.98] |
| city 3 000, 24 h | — | 0.58 | 0.80 [0] (couriers 1.00) | **1.00** [1.00] (burst mode) |
| flood, 20 % devices, N = 500 | — | 0.40 | 0.78 [0] | 0.29 |

Read across rows: no candidate is best everywhere. HYBRID wins or ties in every benign row and is
the only design that serves listeners in every row. Pairwise sync is more robust to a protocol
flooder (its data never touches the saturated primary channels) and is excellent for couriers in
the city — and gives listeners nothing, ever.

## 2. Structural comparison

| Dimension | A broadcast | B pairwise AE | C+D hybrid carousel | E standard BLE Mesh |
|---|---|---|---|---|
| discovery cost | none (data is discovery) | advertise + connect + GATT (≈ 0.4 s assumed) | none | provisioning |
| LISTEN (zero TX) | yes | **impossible** | yes | needs network keys |
| one transmission serves | all in tile | one peer | all in tile | all in range, then relayed (flooding) |
| dense-hall scaling | collapses without rate control | limited by data-channel aggregate; inventory per encounter | rate-controlled; ~300 kB/s per hall | relay storms, 11-byte segments |
| sparse-contact efficiency | poor (low duty) | **good** | good with burst mode | n/a |
| RAM | ~17 KB receive state | + connection, inventory buffer | ~17 KB + age table (2 B/item) | replay list grows with nodes |
| identities exposed | none (anonymous adv) | addresses per connection, inventories | none; content of what couriers send | unicast addresses, sequence numbers |
| control traffic | 0 | inventories | 0 (beacons off) | heartbeats, provisioning |
| integrity per fragment | with hash list | link-layer reliable | with hash list | network/app keys (shared) |

## 3. Coding (erasure / fountain / network)

Rejected for v1 (`store_carry_forward.md` §coding): breaks per-chunk verification (re-opens
pollution), adds RAM and CPU, and the measured gap to the ideal scheduler (ORACLE) is in *which
pamphlet* is sent, not chunk-level loss.

## 4. Verdicts

| Architecture | Verdict | Evidence | Assumptions | Open tests |
|---|---|---|---|---|
| A — pure broadcast, fixed rate | **REJECT** for crowds; acceptable ≤ ~100 devices | airtime model §3; group A (0 % at 3 000) | ALOHA, no capture | E5(a) |
| A' — broadcast + rate control | subsumed by C | group A, B | same | — |
| B — pairwise anti-entropy | **REJECT** as primary; **CONDITIONAL** as a v2 courier-to-courier bulk-sync add-on (rateless IBLT) | listeners 0 in every scenario; fragile to connection assumptions (group F) | 40 kB/s links, 1.5 MB/s per domain | E5 with connections |
| C+D — hybrid carousel (crowd mode + burst mode), store-carry-forward | **CONDITIONAL PROCEED** | groups A–H; executed protocol code | chained anonymous ext. adv. works (E1); rate controller can see interference (E5, Q1); 10 m reception / 35 m interference | E1, E5, E6, E7 |
| E — standard BLE Mesh | **REJECT** | structural: provisioning, network keys, sequence numbers, relay flooding with 11-byte segment payloads | — | none needed |
| erasure / network coding | **REJECT (v1)** | analysis | — | revisit if E5 shows large chunk-tail loss |
| ESP-NOW instead of BLE | **UNRESOLVED** | airtime estimate favourable, energy unfavourable | ESP32-only | E5b |
| summary beacons (SDB) | **REJECT as default; optional** | +1.7 pts at N = 1 000, −4 pts at N = 3 000, no gain in city/rooms; leak bucket equality | — | — |

## 5. Answer to the brief's central hypothesis

"Cooperative behaviour, mobility and redundant opportunities permit a substantially simpler
architecture than conventional highly authenticated mesh networks." **Supported, with two
qualifications.** Simpler: yes — no connections, no keys, no identities, no routing, no
reconciliation protocol; integrity from content addressing alone. But (1) one non-trivial
mechanism is indispensable: density-adaptive rate control, whose real-world observability is the
open risk; and (2) a dense hall is capacity-bound (~300 kB/s), so "everyone gets everything" holds
for hundreds per room, not thousands.
