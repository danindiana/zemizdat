# 04 · Convergence: how fast, and what limits it (simulation results)

All numbers: `06_simulation/results/summary.md` (**SIMULATION**, idealised rate control unless
stated; ± is s.d. over seeds). "Completeness" = fraction of honest pamphlets held, averaged over
honest receivers; listeners included.

## Environment 1 — one auditorium, 1 person/m², 60 min

| devices N | HYBRID v1 (beacons off) | BCAST_RC | BCAST (10 Hz) | AE_INV (listeners) |
|---|---|---|---|---|
| 100 | 1.000 | 1.000 | 1.000 | 0.80 (0) |
| 500 | 1.000 | 0.951 | 0.864 | 0.80 (0) |
| 1 000 | 0.945 ± 0.002 | 0.614 | 0.392 | 0.80 (0) |
| 3 000 | 0.398 ± 0.005 | 0.358 | **0.000** | 0.28 (0) |
| 5 000 | 0.245 | 0.232 | **0.000** | 0.10 (0) |

* Up to ~1 000 devices per hall the carousel moves essentially everything within an hour; the
  median pamphlet reaches 80 % of receivers in ≈ 14 min at N = 1 000 (HYBRID, beacons on).
* At 3 000 devices the hall moves ~40 % of 2 400 pamphlets in an hour — consistent with the
  analytical bound (≥ 20–24 min for *perfect* scheduling of the full collection at 30 % scan
  duty, `communication_bounds.md` §5). Efficiency relative to that bound is low (≈ 15–20 %);
  the ORACLE scheduler (perfect knowledge of what each receiver lacks) reached 100 % at
  N = 1 000 where HYBRID reached 95 %, so better *choice* helps at the margin, but the hall's
  ~300 kB/s is the wall. **Thousands of devices in one room is a receiver-rich, capacity-poor
  regime.**
* Unregulated broadcast is fine to ~100 transmitters, degraded at 500, dead at 3 000.
* Beacon digests: +1.7 points at N = 1 000 when beacons cost little; at N ≥ 3 000 they *cost*
  points (0.36 with vs 0.40 without at N = 3 000; 0.20 vs 0.245 at 5 000) because a fixed beacon
  period eats a growing share of a fixed event budget.

## Environment 2 — six rooms × 500, people change rooms every ~20 min on average, 60 min

| strategy | mean | LISTEN | COURIER | median t50 |
|---|---|---|---|---|
| HYBRID v1 (beacons off) | 0.976 | 0.976 | 0.976 | 24 min |
| HYBRID (beacons on) | 0.968 ± 0.004 | 0.968 | 0.968 | 24 min |
| AE_INV | 0.754 | 0 | 0.946 | 36 min |
| PAIRWISE | 0.714 | 0 | 0.893 | 38 min |
| BCAST_RC | 0.647 | 0.647 | 0.647 | 26 min |

Spatial reuse across rooms multiplies capacity by the number of rooms; mixing by walking does the
rest. This is the regime where the design works best.

## Environment 3 — city, 24 h, 1.5 encounters/h, 20 communities

| strategy | mean | LISTEN | COURIER | median t50 | radio energy (mAh/day, nRF52840 currents) |
|---|---|---|---|---|---|
| HYBRID v1 (burst mode, beacons off) | 1.000 | 1.000 | 1.000 | 6.5 h | 15.5 |
| HYBRID without burst mode | 0.49 ± 0.02 | 0.43 | 0.51 | 15.8 h | 9.6 |
| AE_INV / PAIRWISE | 0.80 | **0** | 1.000 | 8.75 h | 9.8 |
| BCAST_RC | 0.58 | 0.59 | 0.58 | 14.8 h | 10.0 |

* The homogeneous-mixing prediction (`temporal_graphs.md` §2) was `T_50 ≈ 9.8 h` for couriers with
  `γ = 1`. Pairwise sync measured 8.5–9 h, close to the prediction; HYBRID with burst mode is faster
  (6.5 h) because ~15 % of encounters are groups of 3–8 where one transmission serves several.
* Without burst mode the crowd-tuned carousel wastes short contacts; this was found by the
  simulation and fixed in the specification (CX14).

## Interdiction (two rooms of 200 joined only by bridge couriers, 2 h)

| bridges | present | silenced |
|---|---|---|
| 2 | 0.84 ± 0.29 — per seed 0.50 / 1.00 / 1.00 | 0.50 |
| 8 | 1.00 | 0.48 |

Each side keeps only its own half once the bridges are removed — independent of cooperation.
The failing seed is instructive: both of its randomly chosen bridge people were in LISTEN or
EXCHANGE mode, which do not forward third-party pamphlets. A bridge only counts if it is a
COURIER — the min cut is measured in *forwarding* movers, not in movers.

## Adversaries (N = 500, 30 min; HYBRID with beacons on)

| h | flood (50 events/s each) | black-hole | forged suppression |
|---|---|---|---|
| 1.00 | 1.000 | 1.000 | 1.000 |
| 0.99 | 1.000 | 1.000 | 1.000 |
| 0.95 | 0.997 | 1.000 | 1.000 |
| 0.90 | 0.857 | 1.000 | 1.000 |
| 0.80 | 0.294 | 1.000 | 1.000 |

Flooding is the only adversary that matters, and it acts through the channel, not the protocol.

## Rate-control observability (N = 1 000, 30 min)

| controller | mean | combined load G |
|---|---|---|
| idealised (knows its interference domain) | 0.823 | 0.29 |
| counts decodable neighbours only (κ = 1) | 0.468 | 1.53 |
| κ = 3 | 0.757 | 1.07 |
| κ = 10 | 0.854 | 0.45 |
