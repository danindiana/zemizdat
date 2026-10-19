# 08 · Minimum hardware experiment plan (none of these has been performed)

Goal: the smallest set of bench experiments that can **falsify** the architecture's load-bearing
assumptions, in the order that kills bad ideas cheapest. Two or three devices first; a
20–30-device rig only for E5.

## Common setup

* **Devices:** 3 × ESP32-S3-DevKitC-1 (N8R8 or N8) — or the ESP32-S3 on 3 × UNO R4 WiFi flashed
  directly — and 3 × nRF52840-DK (or nRF52840 Dongle). Same experiments on both families.
* **Firmware:** `reference_c/zm_core.c` + `zmproto`-equivalent store in C + radio glue
  (ESP-IDF 5.x NimBLE; nRF Connect SDK / Zephyr). One build flag selects LISTEN/EXCHANGE/COURIER.
* **Host tools:** Python 3, `reference_py/zmproto.py` (generates test pamphlets, checks dumps),
  a BLE sniffer (nRF52840 Dongle with nRF Sniffer for Bluetooth LE, or an SDR), a power analyser
  (Nordic PPK2 or Joulescope), a USB-controlled MOSFET switch for power cuts (the UNO R4's RA4M1
  can drive it).
* **Logging format (every experiment):** JSON Lines on USB serial, one object per event:
  `{"t_us":…, "dev":"A", "ev":"rx_frame|tx_event|commit|reject|slot_open|slot_timeout|mount",
  "sid":"…", "type":"FRAG|MANIFEST|SDB", "idx":…, "rc":"…", "rssi":…}`; current traces as CSV
  `t_us,mA`. Every run records firmware git hash, radio config, distances, and room description.

## E1 — Discovery and link feasibility (2 devices)

Question: can each stack send **anonymous, non-connectable, chained** extended advertising with
≥ 720 B data and can the peer's host receive the chain as one report?
Procedure: A advertises a fixed 3-frame event at 2 events/s; B passively scans at 30 %; 10 min,
at 1, 5, 10 m line-of-sight and 5 m through two people.
Measure: report rate, chain completeness histogram (0–3 PDUs), presence/absence of AdvA on the
sniffer, scan-to-first-frame latency.
**Pass:** ≥ 90 % of caught events deliver all 3 PDUs at 1 m; no AdvA observed (or rotating NRPA
if anonymous unsupported). **Fail → consequence:** no chaining → `L_CHAIN = 1` profile (≈ 34 %
less domain goodput [estimate]); no anonymous adv → address rotation only.

## E-L — LISTEN is radio-silent (2 devices + sniffer + SDR)

LISTEN device scans for 30 min next to the sniffer. **Pass:** zero packets attributable to it
(sniffer on 37/38/39 and an SDR energy capture on all 40 channels). **Fail** invalidates I5's
"presence privacy" claim for that stack.

## E2 — Verified, deduplicated transfer (2 devices)

A originates the pamphlet vectors in `reference_c/vectors.txt` (1 chunk, 2 chunks, 19 chunks);
B in LISTEN. **Pass:** B's committed ids equal the vectors' ids byte-for-byte; re-sending the same
pamphlets for 10 min produces 0 new commits and ≥ 1 `reject: have` per frame; flash dump of B
contains exactly one record per id (I1, I2).

## E3 — Three-node propagation without direct contact

A in room 1, C in room 2 (out of range, verified by sniffer), B COURIER carried from A to C after
5 min. **Pass:** C commits A's pamphlet; C's log never shows a frame decoded from A. Variant E3b:
B placed in the doorway (in range of both) — measures whether a "relay" position speeds
spread versus carrying (evidence for or against RELAY, `state_machine.md`).

## E4 — Differential synchronisation

A holds 1 000 pamphlets, B holds 990 of them + 10 others. Both COURIER, 2 m apart. Measure
time until each holds 1 010 and total events transmitted. Repeat with beacons on/off.
**Pass:** completion; with beacons on, transmissions after completion drop to the
`LISTEN_FLOOR` rate. Records the real cost of the "identical libraries" case.

## E5 — Congestion baseline and rate control (the decisive experiment)

20–30 devices on a table (all within decode range) then spread over a ~30 × 30 m hall.
(a) all at fixed 10 Hz; (b) rate control with `κ_INT = 1`; (c) `κ_INT` = 3, 10.
Measure: per-receiver frames/s, chain completeness vs load, events/s observed (`H`) vs true
transmitted, host report-rate ceiling (`host_rate` assumption: 200/s), and — with a second
receiver at the far wall — the ratio of interfering-but-undecodable traffic.
**Pass:** (b)/(c) hold per-receiver goodput within 30 % of the `airtime_model.py` optimum scaled
by device count; (a) degrades with N as predicted. **Fail:** if per-receiver goodput is far below
the model even at low load, the ALOHA model is wrong for real controllers (e.g. scheduling, host
limits) and simulation group A must be re-run with measured parameters.
**E5b:** repeat (a)–(b) with ESP-NOW v2 on the ESP32-S3s.

## E6 — Energy characterisation

PPK2/Joulescope on each device: deep sleep; idle scan 5 %; scan 30 %; 2 events/s TX; flash commit
of a 1 KiB record; mount of 3 000 records. 10 min each, 3 repeats, 25 °C.
**Output:** a table replacing every [assumed] current in `05_hardware/battery_budget.md`.
**Decision rule:** if ESP32-S3 scan at 30 % averages > 25 mA, the ESP32-S3 is prototype-only.

## E7 — Power-loss consistency on real flash

Device commits pamphlets in a loop with GC forced (small partition); the RA4M1 cuts 3.3 V at a
random instant 0–50 ms after each "commit start" log line; 2 000 cycles. After each reboot, the
device dumps `(id, verify ok)` for all records.
**Pass:** 0 records failing verification; 0 duplicates in the index; every acknowledged commit
present (except a delete in flight). Same acceptance as the Python model test, now on silicon.

## Order and cost

E1 → E-L → E2 → E7 (all 2 devices, ~1 week) → E3/E4 (3 devices) → E6 → E5 (needs 20–30 devices,
~$150–300 of dev boards). Any failure in E1/E5 changes the radio design; failures elsewhere change
parameters.
