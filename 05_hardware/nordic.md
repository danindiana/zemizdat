# 05 · H3 — Nordic nRF52840 (and nRF54L15)

Sources: nRF52840 SoC Product Brief v3.0 (fetched 2026-10-19). The nRF54L15 datasheet page
could not be read in this session; its figures are **not** used.

## Verified facts [spec, nRF52840]

* 1 MB flash, 256 KB RAM, supply 1.7–5.5 V.
* Radio current (DC/DC, 3 V): **RX 6.26 mA at 1 Mbit/s; TX 6.40 mA at 0 dBm; 16.40 mA at +8 dBm.**
* System ON idle with full RAM retention and RTC: 3.16 µA.
* BLE 5 incl. 2M PHY and extended advertising (Zephyr controller supports up to 1 650 B of
  advertising data with chaining, per Nordic DevZone discussions; to be confirmed in E1).

## Fit

| Need | nRF52840 |
|---|---|
| receive state (8 slots) + 3 000-entry index | 71 KB of 256 KB |
| library 3 000 × 1 KiB (3.25 MB) | needs external 8 MB SPI NOR; internal flash holds ~600 |
| SHA-256 | CryptoCell-310 |
| supply from 1S Li-ion | directly within 1.7–5.5 V (use the internal DC/DC) |

## Energy (radio only, from datasheet currents) [estimate]

Scan at δ = 0.30: 0.30 × 6.26 = 1.88 mA. Transmit at the auditorium equilibrium rate (~2
events/s × 3.6 ms airtime): 0.046 mA. Idle scan δ = 0.05 when alone: 0.31 mA. CPU, flash and
regulator losses are **not** included and must come from E6.

## nRF54L15

Newer, lower-power family; Nordic markets it as a successor. Not assessed here because its
datasheet values were not obtained. **UNRESOLVED**; revisit after E6 on nRF52840.

## Verdict

**CONDITIONAL PROCEED as the production candidate.** Roughly 10× lower radio current than any
plausible ESP32-S3 BLE figure, direct Li-ion supply, and enough RAM. Conditions: external SPI
NOR for large libraries; E1 confirms chained extended advertising and host report throughput
with Zephyr; E6 measures total system current.
