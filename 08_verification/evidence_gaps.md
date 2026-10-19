# 08 · Evidence gaps (what is assumed, and what would settle it)

| # | Assumption / unknown | Where it matters | Current basis | Settled by |
|---|---|---|---|---|
| R1 | ESP32-S3 NimBLE and nRF52840 Zephyr transmit and deliver **chained, anonymous** extended advertising (≥ 720 B) | entire radio design | spec + vendor forum reports | E1 |
| R2 | ALOHA model of primary/secondary collisions is accurate enough for real controllers | all group-A/B/C numbers | standard model; no capture | E5 |
| R3 | reception tile ≈ 10 m and interference radius ≈ 35 m in a dense crowd | auditorium capacity per receiver | assumption | E5 (two receivers, near/far) |
| R4 | host can process ≥ 200 advertising reports/s | per-receiver throughput ceiling | assumption; sensitivity group F | E5 |
| R5 | a rate controller can observe interference it cannot decode (`κ_INT`) | crowd stability | **unresolved**; simulator idealises | E5(c) |
| R6 | city mobility (Poisson encounters, communities) | Environment 3 conclusions | synthetic model, no traces | real mobility traces (e.g. public Bluetooth encounter datasets) replayed through the simulator |
| R7 | ESP32-S3 BLE scan current | hardware choice | not obtained | E6 |
| R8 | connection goodput 40 kB/s per link and 1.5 MB/s per domain | pairwise baselines only | assumption; sensitivity group F | E5 with connections |
| R9 | NOR torn-write behaviour beyond the bit-subset model | I6 on silicon | model | E7 |
| R10 | users' mode mix (20/30/50) and scan duty | all results | assumption; sensitivity group F | user study / pilot |
| R11 | MCU SHA-256 rate (for PoW argument and recovery time) | minor | estimate | microbenchmark |
| R12 | LISTEN passive scan emits nothing | presence privacy | stack documentation | E-L |
| R13 | nRF54L15 figures | future hardware | not obtained | datasheet review |
| R14 | BOM prices | cost claims | unverified ranges | distributor quotes |

Simulation limitations (independent of parameters):
* round-based (1 s, 30 s in city); events within a round are not ordered; up to 4 events per
  item per round are drawn independently, more are approximated per-frame;
* staging-slot limits are not modelled in the simulator (they are in the reference code);
* beacon (SDB) staleness and the 16-bit false-equal rate are not modelled; digests are exact;
* rate control is idealised (knows the transmitter count of its domain) — see R5;
* energy counts radio-on time only, with nRF52840 currents; CPU, flash, regulator excluded;
* pairwise models: one connection per device, fixed setup time, no connection-event collisions
  beyond a shared domain budget.
