# 04 · Uncertainty: which assumptions move the conclusions

Source: simulation group F (N = 1 000, one hall, 30 min, 2 seeds; ± = s.d. over seeds;
`06_simulation/results/summary.md`). Baseline HYBRID mean completeness **0.823**; AE_INV **0.778**
(its listeners always 0).

## Ranking by effect on HYBRID (one factor at a time)

| Assumption | Values tried | HYBRID mean | Moves the architecture decision? |
|---|---|---|---|
| receive scan duty | 0.1 / **0.3** / 1.0 | 0.47 / 0.82 / 1.00 | No — it moves latency and energy (0.33 / 0.95 / 3.14 mAh per 30 min); it is the main user-facing trade-off |
| reception-tile edge `r_rx` (with interference radius fixed at 35 m) | 5 / **10** / 20 m | 0.46 / 0.82 / 1.00 | **Potentially**: the reception/interference ratio sets how much broadcast gain survives; must be measured (E5, R3) |
| pamphlet size | 200 B / **1 KiB** / 4 KB body | 1.00 / 0.82 / 0.24 | No — but sets expectations: a hall moves ~300 kB/s in total |
| chaining | 1 / **3** PDUs | 0.53 / 0.82 | No, if E1 confirms chaining; otherwise every crowd number drops by ~⅓ |
| residual loss `p_loss` | 0 / **0.1** / 0.3 | 0.89 / 0.82 / 0.66 | No |
| age (overhearing) weighting | on / off | 0.82 / 0.74 | Yes for the scheduler: keep it |
| beacon digest weighting | on / off | 0.82 / 0.81 | Yes, the other way: beacons are not worth their privacy cost |
| host report ceiling | 50 / 200 / 1 000 per s | 0.82 (all) | No — not binding at these densities |
| mode mix (LISTEN/EXCH/COURIER) | 0.6/0.2/0.2 · **0.2/0.3/0.5** · 0/0/1 | 1.00 / 0.82 / 0.80 | No (fewer originators → fewer items to move) |

Separately (group G): **rate-control observability** — decodable-only counting collapses the
hall; this is the single assumption that can invalidate the crowd design (CX2, Q1).

## For the pairwise baseline

AE_INV depends almost entirely on the connection assumptions: per-link goodput 10 kB/s instead
of 40 kB/s → 0.31; domain goodput 0.5 MB/s instead of 1.5 → 0.41; 1.5 s setup instead of 0.4 s →
0.53; more listeners (60 %) → 0.40. So the result "pairwise is competitive for transmitting
devices in a hall" is fragile, and the result "pairwise gives listeners nothing" is not.

## What is robust across all variations

1. Listeners receive only under broadcast designs.
2. Without rate control, broadcast fails beyond a few hundred transmitters per domain.
3. Overhearing-based prioritisation beats beacon-based prioritisation per unit of privacy spent.
4. Scan duty is the dominant energy–latency knob.

## Statistical note

Seeds vary placement, mode assignment and all channel draws; with N = 1 000 the seed-to-seed
s.d. of mean completeness is ≤ 0.02 in every configuration, so the one-factor differences above
(≥ 0.08 except digest weighting) are well outside run-to-run noise. Digest weighting's +0.017 is
about 3 s.d. — real but small. All of this is model uncertainty-free only *within* the model:
the dominant uncertainty is model error, addressed by E1/E5.
