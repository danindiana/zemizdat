# 09 · Prototype plan

## Phase 0 — done in this session (software only)

* Executable reference of the wire format, identity, reassembly and crash-safe store (Python,
  31 tests incl. every-byte power cuts through GC).
* Portable C99 receive path, byte-for-byte equal to the Python on test vectors, fuzzed with 2 M
  mutated frames under ASan/UBSan.
* Simulator with 5 strategies + oracle, 377 runs across 8 experiment groups.

## Phase 1 — two-board link proof (1–2 weeks, ≈ $60)

Hardware: 2 × ESP32-S3-DevKitC-1 (or the ESP32-S3 on two UNO R4 WiFi boards, flashed directly),
2 × nRF52840 Dongle, 1 extra nRF52840 Dongle as sniffer, a USB power meter.
Firmware: `zm_core.c` + radio glue (NimBLE / Zephyr) + the log-structured store in C (port of
`zmproto.Store`). Serial JSONL logging.
Experiments: E1, E-L, E2, E7. Exit criteria: AT1–AT4, AT6.

## Phase 2 — three-node behaviour (1 week)

E3 (propagation without direct contact; doorway variant), E4 (differential sync, beacons on/off,
burst mode between two walkers). Exit: AT5.

## Phase 3 — energy (1 week, PPK2 or Joulescope)

E6 on both families. Update `05_hardware/battery_budget.md` with measured values. Decision point:
ESP32-S3 prototype-only or viable (rule in `esp32.md`).

## Phase 4 — congestion rig (2–3 weeks, ≈ $150–300 of boards)

20–30 nRF52840 Dongles (cheapest per node) on USB hubs, plus 2 receivers at near/far positions.
E5 (a)–(c), E5b on ESP32-S3s if available. Re-run simulator groups A/F/G with measured
parameters. Decision point: Q1 (rate-control observability).

## Phase 5 — pocket device (only after Phase 4 passes)

nRF52840 module + 8 MB SPI NOR + 1S Li-ion with charger + e-paper + 3 buttons. Governance plane:
MCUboot with ≥ 2 keys, threshold-signed release records, owner-button consent.

## What would stop the project at each phase

| Phase | Stop condition |
|---|---|
| 1 | neither stack can do non-connectable chained extended advertising → redesign the link (ESP-NOW or Coded PHY) |
| 1 | power-cut test fails on real flash → storage redesign before anything else |
| 4 | no observable for interference and fixed caps make halls unusably slow → crowd scenario dropped; the device becomes a small-group / city courier only |
