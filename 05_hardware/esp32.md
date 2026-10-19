# 05 · H2 — ESP32-S3-only device

Sources: ESP32-S3 Series Datasheet v0.6.1 (current table) and v2.2 (features); ESP-IDF ESP-NOW
and Secure Boot V2 documentation (all fetched 2026-10-19).

## Verified facts [spec]

* 512 KB SRAM, 384 KB ROM, 16 KB RTC SRAM.
* Bluetooth LE 5: 2M PHY, Coded PHY (125/500 kbit/s), **advertising extensions, multiple
  advertising sets**.
* Wi-Fi current (3.3 V, 25 °C, 100 % duty): RX 95 mA (11b/g/n HT20), TX peak 340 mA at 21 dBm
  (11b). Deep sleep 7 µA.
* ESP-NOW: vendor action frames; payload 250 B (v1) or **1 470 B (v2)**; default rate 1 Mbit/s;
  broadcast frames cannot be encrypted.
* Secure Boot V2: RSA-3072-PSS, up to three key digests in eFuse, individually revocable.
* ESP32-S3-MINI-1-N8 carries 8 MB flash (part-number suffix).

## Not verified (must be measured, E6)

* **BLE RX/TX current on ESP32-S3.** The fetched documents did not include the BLE current
  table. Order of magnitude is expected to be tens of mA (shared RF front end with Wi-Fi, whose RX
  is 95 mA) — an order of magnitude above the nRF52840. This single number decides whether the
  ESP32-S3 is a weekend prototype or a viable product.
* Whether NimBLE on ESP32-S3 transmits **chained** extended advertising data (≥ 720 B per event)
  and whether its controller supports **anonymous** advertising. If chaining is unavailable, the
  airtime model's `L_CHAIN = 1` row applies (≈ 30 % less domain goodput, [estimate]).

## Fit

| Need | ESP32-S3 |
|---|---|
| receive state (8 slots, 34.9 kB) + 3 000-entry index (36 kB) | trivially fits in 512 KB |
| 3 000 × 1 KiB library + 2 firmware slots | fits in 8 MB |
| SHA-256 | hardware accelerator |
| radio options | BLE 5 ext. adv. (normative) **or** ESP-NOW v2 (1 470 B ≈ 6 frames per packet) |

## ESP-NOW as an alternative data link (prototype only)

Advantages: a 1 KiB pamphlet fits one ESP-NOW v2 frame; Wi-Fi CSMA/CA avoids the ALOHA collapse
of uncoordinated advertising; at higher PHY rates (configurable per peer) airtime per pamphlet
falls well below BLE's. Disadvantages: ESP32-only (locks out Nordic and phones), Wi-Fi-level
current draw for every listening moment, MAC address in every frame (must be randomised by the
application), one shared Wi-Fi channel competing with venue Wi-Fi. Verdict: **UNRESOLVED** as a
competitor; worth one bench comparison (E5b) because it is free on the same hardware.

## Verdict

**CONDITIONAL PROCEED** as the v1 field prototype: everything fits, development tooling is
mature, and the UNO R4's own module can be used (see `arduino_r4.md`). Conditions: E1 confirms
chained + anonymous extended advertising on NimBLE; E6 measures BLE scan current. If scan
current at 30 % duty exceeds ~25 mA average, a 2 000 mAh cell lasts under ~3 days of active use
[estimate], and the production device should move to H3.
