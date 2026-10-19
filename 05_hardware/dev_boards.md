# 05 · Candidate development boards (checked 2026-10-19)

Prices are single-unit retail figures seen on the linked listing on that date, in that store's currency.
They are not quotes. Specs are from those listings unless marked *(unverified)*.

## What a board must do for ZEMIZDAT

1. BLE 5 extended advertising (needed for E1). Chaining and anonymous advertising are still to be confirmed per stack.
2. Enough RAM for the C core: ≥ 64 KB is comfortable; `zm_rx` alone is 17 KB.
3. External flash for the library: 2 MB ≈ 1 800 one-KiB pamphlets; 8 MB is needed for the full 3 000 scenario.
4. A single-cell Li-ion charger on the board, so devices can walk around (E3, E5 spread over a hall).
5. For energy work (E6): a debugger and current-measurement pins.

## Shortlist

| Board | SoC | Ext. flash | Charger | Debug / measure | Price seen | Role |
|---|---|---|---|---|---|---|
| **Seeed XIAO nRF52840** | nRF52840 | 2 MB QSPI | yes, BQ25101, 50/100 mA | SWD pads; ~5 µA deep sleep | $12.38 (RobotShop) | **workhorse:** E1–E4, and the 20–30-node untethered E5 rig |
| **Nordic nRF52840 DK** (PCA10056) | nRF52840 | 8 MB QSPI *(unverified)* | no (USB/coin cell) | J-Link OB; current-measurement pins *(unverified)* | ~US$50 *(unverified)* | reference board for E1/E6/E7 with full debugging |
| **Nordic nRF52840 Dongle** (PCA10059) | nRF52840 | — | no | no debugger, USB DFU only | A$28.95 (Core Electronics) | BLE **sniffer** (nRF Sniffer) for E1/E-L; cheap fixed rig nodes |
| **Seeed XIAO nRF54L15** | nRF54L15 (M33 128 MHz + RISC-V) | none listed (1.5 MB on-chip NVM) | yes | IPEX antenna option; board-level power data "being verified" | £9.60 (The Pi Hut) | nRF54L family evaluation (Q: lower power than nRF52840?) |
| **Nordic nRF54L15 DK** | nRF54L15 | 8 MB | no | J-Link OB, power-measurement pins, 4 buttons | $36.17 (Future Electronics) | nRF54L energy reference (E6) |
| **Seeed XIAO ESP32S3** | ESP32-S3 | 8 MB flash + 8 MB PSRAM | yes, 50 mA | ~14 µA deep sleep; U.FL antenna included | £7.30–8.20 (The Pi Hut) | ESP32-S3 prototype node; ESP-NOW comparison (E5b) |
| **ESP32-S3-DevKitC-1-N8R8** | ESP32-S3 (WROOM-1) | 8 MB + 8 MB PSRAM | no | USB-JTAG on chip | $31.55 (Jameco) | ESP32-S3 reference board for E1/E6 |
| **Arduino UNO R4 WiFi** (already owned) | RA4M1 + ESP32-S3-MINI-1-N8 | 8 MB on module | no | — | — | flash the ESP32-S3 directly; RA4M1 drives the power-cut MOSFET for E7 |
| **LilyGO T-Echo Plus** | nRF52840 | 2 MB | 2 400 mAh Li-Po included | — | $94.95 (Ameridroid) | closest off-the-shelf "pocket device": 1.54" e-paper, enclosure, battery |
| **Heltec Mesh Node T114** | nRF52840 | not stated | Li-ion + solar connectors; ~11 µA sleep | — | $32.97–42.97 (Rokland) | cheaper pocket-device stand-in (1.14" TFT option) |
| **Adafruit Feather nRF52840 Express** | nRF52840 | 2 MB QSPI | yes, LiPo | SWD 2×5 header, UF2 bootloader | A$47.10 (Core Electronics) | well-documented alternative to the XIAO; bigger and dearer |

## Notes

* **The XIAO nRF52840 is the best value overall.** It is cheap, has a charger and 2 MB of flash, and sits on the production-candidate chip. Thirty of them come to about $370 plus small Li-Po cells, which buys an E5 rig that can be spread across a real room instead of hanging off USB hubs.
* **LoRa and GPS on the T-Echo and T114 are not used by ZEMIZDAT.** Leave GPS physically disabled. A location receiver on a privacy device is a liability, and LoRa would be a separate design question.
* **2 MB of flash caps a prototype at roughly 1 800 pamphlets.** That is enough for every planned experiment. The 3 000-pamphlet scenario needs 8 MB: the DKs or an add-on SPI NOR.
* **Same chip, different board.** Energy numbers measured on DKs (debugger circuitry, LEDs) need re-measuring on the XIAO or a custom board before any battery claim.
* **ESP32-S3 BLE receive current:** the module datasheet gives 93 mA (peak). Measure the average on the DevKitC or XIAO before committing more ESP32 hardware (E6 rule in `esp32.md`).

## Custom board

For a board built around ZEMIZDAT's needs (charger, power-switched microSD, E6/E7 test
hooks, Arduino variant), see the ZB-1 design in [`zb1/README.md`](zb1/README.md).

## Suggested first order (Phase 1 + sniffer, ≈ US$110–130 + cells)

2 × XIAO nRF52840, 2 × XIAO ESP32S3, 1 × nRF52840 Dongle (sniffer), 1 × nRF52840 DK
(debugger and current pins), 4 × small 1S Li-Po cells. For E7, the UNO R4 WiFi you already
have is the power-cut controller.

## Sources

[RobotShop XIAO nRF52840](https://www.robotshop.com/products/seeedstudio-seeed-studio-xiao-nrf52840) ·
[Pimoroni XIAO nRF52840 specs](https://shop.pimoroni.com/products/seeed-xiao-ble-nrf52840-supports-arduino-micropython-bluetooth5-0-with-onboard-antenna) ·
[Pi Hut XIAO nRF54L15](https://thepihut.com/products/seeed-studio-xiao-nrf54l15) ·
[Nordic nRF54L15 DK](https://nordicsemi.com/Products/Development-hardware/nRF54L15-DK) ·
[Future Electronics nRF54L15-DK](https://www.futureelectronics.com/p/3205208) ·
[Core Electronics nRF52840 Dongle](https://core-electronics.com.au/nordic-semiconductor-nrf52840-usb-dongle.html) ·
[Pi Hut XIAO ESP32S3](https://thepihut.com/products/seeed-studio-xiao-esp32s3) ·
[Jameco ESP32-S3-DevKitC-1-N8R8](https://www.jameco.com/z/5336-Adafruit-Industries-Esp32-S3-Devkitc-1-N8R8-Esp32-S3-Wroom-1-8MB-Flash-8MB-PSRAM_2524143.html) ·
[Ameridroid T-Echo Plus](https://ameridroid.com/products/lilygo-t-echo-plus) ·
[LilyGO T-Echo wiki](https://wiki.lilygo.cc/get_started/en/Wearable/T-Echo/T-Echo.html) ·
[Rokland Heltec T114](https://store.rokland.com/products/heltec-mesh-node-t114-with-optional-1-14-inch-tft-display) ·
[Core Electronics Feather nRF52840](https://core-electronics.com.au/adafruit-feather-nrf52840-express.html) ·
[CircuitPython nRF52840 DK](https://circuitpython.org/board/pca10056/)
