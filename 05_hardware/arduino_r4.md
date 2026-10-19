# 05 · H1 — Arduino UNO R4 WiFi

Sources: Arduino ABX00087 datasheet; element14 product page (fetched 2026-10-19).

## Verified facts [spec]

* Main MCU Renesas RA4M1, Cortex-M4 at 48 MHz, **32 kB SRAM**, 256 kB flash, 8 kB EEPROM/data flash.
* Radio module ESP32-S3-MINI-1-N8 (Wi-Fi 4 + Bluetooth 5 LE). The RA4M1 has no radio.
* The RA4M1 runs at **5 V**, the ESP32-S3 at 3.3 V; they talk through a TXB0108 level translator;
  the ESP32-S3 UART pins are broken out on a header.
* Power: VIN 6–24 V → ISL854102 buck to 5 V → SGM2205 LDO to 3.3 V. USB-C feeds ~4.7 V to the
  RA4M1 rail (Schottky drop). There is **no** battery charger and no input that accepts a single
  Li-ion cell (3.0–4.2 V): VIN needs ≥ 6 V; the VRTC pad powers the RTC only.
* Arduino documents uploading custom firmware to the on-board ESP32-S3 ("UNO R4 WiFi Custom
  Firmware Upload to ESP32").

Not verified this session: the exact bridge protocol the stock ESP32-S3 firmware exposes to the
RA4M1 (believed to be a serial AT-command bridge; ArduinoBLE over HCI-on-serial is reported to
work). It does not change the conclusion below.

## Constraints for ZEMIZDAT as an RA4M1 application

| Need | RA4M1 | Verdict |
|---|---|---|
| receive state (4 slots) | 17.4 kB measured `sizeof(zm_rx)` | fits, but leaves ~14 kB for stack, radio bridge buffers, index |
| RAM index, 3 000 entries × 12 B | 36 kB | does not fit → flash-resident index required |
| library of 3 000 × 1 KiB | 3.25 MB | does not fit (256 kB) → external SPI NOR required |
| radio | via serial bridge to ESP32-S3 | every frame crosses a UART + level translator: added latency, a second firmware to maintain, and the ESP32-S3 is awake anyway |
| battery | no Li-ion path | needs an external boost to 5 V or a USB power bank |

## Verdict

**REJECT for the production device.** The RA4M1 contributes nothing the ESP32-S3 on the same
board cannot do better (it has 16× the SRAM and the radio), and it forces a second processor, a
bridge protocol and a 5 V rail.

**CONDITIONAL PROCEED as a bench harness**, used in one of two ways:
1. Flash ZEMIZDAT firmware **directly onto the board's ESP32-S3** (Arduino-documented path) and
   use the RA4M1 only as a USB-serial logger / power-cut controller for experiment E7 (it can
   drive a MOSFET that interrupts the ESP32-S3's 3.3 V at a programmed instant). This turns the
   UNO R4 into an H2 device with built-in fault injection.
2. Run the portable C core (`reference_c/`) on the RA4M1 with `ZM_SLOTS=4` as a
   memory-pressure test of the 32 kB profile — useful to keep the code honest, not for field use.

Assumptions: prices and availability not assessed; conclusion holds regardless of the bridge
protocol details.
