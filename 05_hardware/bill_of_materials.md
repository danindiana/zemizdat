# 05 · Bill of materials (rough, unverified prices)

**Prices below are order-of-magnitude estimates for small-batch purchasing, not quotes. They
were not checked against distributors in this session.** Use them to compare architectures, not
to price a product.

| Item | H1 UNO R4 WiFi bench rig | H2 ESP32-S3 prototype | H3 nRF52840 product candidate |
|---|---|---|---|
| processor / radio | UNO R4 WiFi board (~$25–30) | ESP32-S3-MINI-1-N8 module (~$3–5) | nRF52840 module, e.g. pre-certified (~$7–12) |
| external flash | on module (8 MB) | on module (8 MB) | 8 MB SPI NOR (~$0.3–0.7) |
| cell | USB power bank | 2 000 mAh 1S Li-ion, protected (~$2–5) | same |
| charging + power path | — | charger IC + buck-boost (~$1.5–3) | charger IC (~$0.5–1.5); nRF DC/DC on chip |
| UI | serial console | 1.5" e-paper (~$5–9) or small OLED (~$2–4); 3 buttons | same; e-paper preferred (zero hold power) |
| USB-C, passives, PCB, enclosure | — | ~$4–8 | ~$4–8 |
| **total (rough)** | ~$30–40 | **~$16–30** | **~$19–36** |

Notes
* Pre-certified radio modules avoid per-design RF certification; a bare-chip design is cheaper
  per unit but needs its own RF certification — a real cost not shown here.
* The display is optional for a "pocket courier" variant (no reading UI; content read later via
  a phone over USB). That removes ~$5–9 and most UI firmware.
* Firmware development burden (all three): portable C core shared; radio glue differs (NimBLE vs
  Zephyr). H1 adds a bridge protocol and a second firmware.
