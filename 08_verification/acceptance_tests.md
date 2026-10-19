# 08 · Acceptance tests for the first prototype (go / no-go)

A prototype build is accepted only if **all** of the following pass. Each maps to an experiment
in `test_plan.md`. Thresholds are proposals; they are set so that failure clearly means the
assumption is wrong, not that the build is slightly off.

| # | Test | Pass criterion | If it fails |
|---|---|---|---|
| AT1 | conformance | device decodes every frame in `reference_c/vectors.txt` replayed by a test transmitter and commits exactly the listed ids | implementation bug — fix before anything else |
| AT2 | chained anonymous adv (E1) | ≥ 90 % of caught events complete at 1 m; no stable AdvA | switch radio profile (`L_CHAIN = 1` / NRPA rotation) and re-run group A with that profile |
| AT3 | LISTEN silence (E-L) | 0 attributable packets in 30 min | LISTEN privacy claim withdrawn for that stack |
| AT4 | dedup + integrity (E2) | 0 duplicate records; 0 integrity failures after 10 min of repeats | bug |
| AT5 | 3-hop spread (E3) | C commits A's pamphlet within 2 min of B arriving | investigate reassembly/slot logic |
| AT6 | power-cut safety (E7) | 2 000 random cuts: 0 corrupt, 0 duplicate, ≤ 1 lost delete per cut | storage design defect (stop) |
| AT7 | congestion (E5) | rate-controlled goodput per receiver ≥ 70 % of model at 20 devices; unregulated degrades as predicted | recalibrate model; if rate control cannot observe load, design a new controller (Q1) |
| AT8 | energy (E6) | measured currents recorded; nRF52840 crowd-mode average ≤ 4 mA | hardware choice revisited |
| AT9 | memory | on-target worst-case stack + static RAM ≤ 75 % of SRAM with `K_SLOT` = 8 (4 on RA4M1) | reduce slots / move staging to flash |
| AT10 | fuzz on target | 10⁶ random/mutated frames injected over the air from an SDR or a second board: no reset, no corrupt commit | parser/radio-glue bug |
