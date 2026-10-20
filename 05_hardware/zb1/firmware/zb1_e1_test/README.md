# E1 harness — extended advertising, chaining and anonymity on ZB-1

Firmware for experiment **E1** in [`08_verification/test_plan.md`](../../../../08_verification/test_plan.md):

> Can the stack send anonymous, non-connectable, chained extended advertising with ≥ 720 B of data,
> and can the peer's host receive the chain as one report?

The firmware runs on two ZB-1 boards, or on any ESP32-S3 board using the pins in `pinmap.csv`.
* **Board A** transmits.
* **Board B** passively scans, reassembles each chain and checks a SHA-256 over it.
* An **nRF52840 dongle** running Nordic's BLE sniffer, with Wireshark, shows what is actually on air.

**Status:** compiles cleanly for `esp32:esp32:esp32s3` and for the ZB-1 board definition
(arduino-esp32 2.0.9, NimBLE-Arduino 1.4.3, 2026-10-19). It has **not been run on hardware yet.**

## Build

The harness needs three build flags. Pass them on the command line, or set the same values with
`#define` in `NimBLE-Arduino/src/nimconfig.h`:

```
-DCONFIG_BT_NIMBLE_EXT_ADV=1
-DCONFIG_BT_NIMBLE_MAX_EXT_ADV_DATA_LEN=1650
-DCONFIG_BT_NIMBLE_MSYS1_BLOCK_COUNT=24
```

```bash
arduino-cli compile --fqbn esp32:esp32:zemizdat_zb1 \
  --build-property "compiler.cpp.extra_flags=-DCONFIG_BT_NIMBLE_EXT_ADV=1 -DCONFIG_BT_NIMBLE_MAX_EXT_ADV_DATA_LEN=1650 -DCONFIG_BT_NIMBLE_MSYS1_BLOCK_COUNT=24" \
  --build-property "compiler.c.extra_flags=-DCONFIG_BT_NIMBLE_EXT_ADV=1 -DCONFIG_BT_NIMBLE_MAX_EXT_ADV_DATA_LEN=1650 -DCONFIG_BT_NIMBLE_MSYS1_BLOCK_COUNT=24" \
  05_hardware/zb1/firmware/zb1_e1_test
```

The sketch refuses to compile if extended advertising is off or the data limit is below 1650. With
the default limit (251), NimBLE copies a larger payload into a 251-byte buffer.

## Modes

M5 is the default: it is the E1 pass/fail case. Airtime is estimated from PDU sizes and does not
include the ≥ 300 µs gaps between chained PDUs. Primary-channel ADV_EXT_INDs add about 0.4 ms.

| Key | Mode | AD bytes | AUX PDUs | Secondary airtime | Purpose |
|---|---|---|---|---|---|
| `0` | M0 200 B, anonymous, 2M | 205 | 1 | ≈ 0.9 ms | single AUX_ADV_IND baseline |
| `1` | M1 1088 B, anonymous, 2M | 1113 | 5 | ≈ 4.8 ms | long chain |
| `2` | M2 1088 B, **with address**, 2M | 1113 | 5 | ≈ 4.8 ms | control: AdvA must appear here, proving M1/M5 omit it on purpose |
| `3` | M3 1580 B, anonymous, 2M | 1615 | 7 | ≈ 7.0 ms | controller data-length ceiling |
| `4` | M4 1088 B, anonymous, **1M** | 1113 | 5 | ≈ 9.6 ms | PHY comparison (range vs airtime) |
| `5` | **M5 705 B, anonymous, 2M** | 720 | **3** | ≈ 3.1 ms | **the protocol's event: AUX_ADV_IND + 2 × AUX_CHAIN_IND** (spec `L_CHAIN = 3`) |

**Other keys**

| Key | Action |
|---|---|
| `t` | toggle TX |
| `r` | toggle RX (passive extended scan) |
| `d` | scan duty 30 % ↔ 100 % (the E1 procedure uses 30 %) |
| `p` | TX power 0 ↔ +9 dBm |
| `b` | re-send with a new sequence number |
| `s` | statistics |
| `z` | zero the statistics |
| `h` | help |
| BOOT button | next mode |

**The payload is a test stream, not the ZEMIZDAT wire format:**
* `'ZM'`, seq, length, a deterministic body and a SHA-256;
* split into ≤ 248-byte Manufacturer Specific Data structures with company ID 0xFFFF (Bluetooth SIG test ID) and a chunk index.

The receiver checks chunk order, length and hash. For real protocol frames through `zm_core.c`,
use [`../zb1_bringup`](../zb1_bringup).

## Procedure (matches test_plan.md E1)

1. **Set up two boards.** Board A sends M5 at 2 events/s (the default 500 ms interval). Board B
   receives: press `r`, with the scan at 30 % duty.
2. **Run at each distance.** 10 minutes each at 1, 5 and 10 m line of sight, and at 5 m through
   two people. On B, press `z` at the start and `s` at the end of each run.
3. **Sniffer, M5.** Filter `btle.advertising_header.pdu_type == 0x07`.
   * The ADV_EXT_IND AuxPtr leads to an AUX_ADV_IND on 2M, followed by **2 AUX_CHAIN_IND**.
   * **No AdvA** field appears in any of them.
4. **Sniffer, M2 (control).** AdvA is present, with a non-resolvable private address. If AdvA is
   absent in M2 as well, the sniffer is not decoding the field and step 3 proves nothing.
5. **Characterisation.** Repeat at 1 m with M1, M3 and M4 to find the chain length and PHY limits.
   Report `truncated` counts and the fragment histograms.

**Pass (from test_plan.md):**
* At 1 m, ≥ 90 % of caught events arrive intact. The harness prints this as "intact streams";
  M5 is the case that counts.
* No AdvA in M5.

**If it fails:**
* No chaining → `L_CHAIN = 1` profile.
* No anonymity → rotating NRPA, as in M2.

The fragment histograms count HCI report fragments, which the controller sizes itself. They are a
proxy for PDUs received; the sniffer gives the real count.

## Changes from the contributed draft

The harness came in as a draft. It was reviewed against the NimBLE-Arduino 1.4.3 source and
compiled here; these changes were needed:

| # | Draft | Problem (verified) | Fix |
|---|---|---|---|
| 1 | `#include "host/ble_gap.h"` etc. | Fails to compile: those paths exist only in ESP-IDF builds. In Arduino they are `nimble/nimble/host/include/host/...` | NimBLE's own conditional include pattern |
| 2 | `disc.addr.type == BLE_ADDR_ANY` | Compile error: `BLE_ADDR_ANY` is a *pointer to an all-zero address*, not a type code | Compare with `0xFF`. That is the HCI "anonymous, no address" type, which NimBLE passes through unchanged (`ble_hs_hci_evt.c`) |
| 3 | `CONFIG_BT_NIMBLE_EXT_ADV_MAX_SIZE 1650` | Not a NimBLE option, so it is silently ignored. The real one is `CONFIG_BT_NIMBLE_MAX_EXT_ADV_DATA_LEN` (mapped to `MYNEWT_VAL_BLE_EXT_ADV_MAX_SIZE`, default 251). With 251, `ble_gap_ext_adv_set_data` copies the 1,113-byte M1 payload into a 251-byte buffer: memory corruption, not an error code | Correct option name; `#error` guard if it is below 1650 |
| 4 | 1,600-byte stack buffers in the RX callback | The callback runs on the NimBLE host task, whose stack is 4 KB. That buffer plus mbedTLS and `printf` risks overflowing it | Static buffers |
| 5 | Single reassembly buffer shared by every advertiser | Any nearby phone's extended advertising interleaves with the test chain and corrupts it | Reassembly keyed by (address type, address, SID); interleaving counted. Legacy PDUs ignored |
| 6 | Bad-stream detection checked bytes 5–6 only | Could also match unrelated data | Also checks the 0xFF/0xFFFF header; the verifier checks chunk order |
| 7 | `mbedtls_sha256_*_ret` | Removed in mbedTLS 3, which arduino-esp32 core 3.x uses | Version switch |
| 8 | Only 200 / 1088 / 1580-byte modes, 100 % scan, TX +9 dBm | Did not cover the E1 definition (≈ 720 B, 3 PDUs, 30 % scan) | Added M5 as the default, a duty toggle, a fragment histogram and a pass-rate line. TX defaults to 0 dBm (as in the battery budget); `p` selects +9 |
| 9 | "M1 ≈ 4.6 ms airtime" | Underestimate | ≈ 4.8 ms secondary + 0.4 ms primary radio time. Event span is longer still, because of the inter-PDU gaps |

## Unknowns this run will settle

* The ESP32-S3 controller's maximum advertising data length. It is read by the host at start-up;
  if M3 fails with a `set_data` error, the limit is below 1615 B.
* Whether the controller honours the anonymous bit. M5 vs M2 on the sniffer will show it.
* The real chain-completeness rate at 30 % scan duty. This feeds `L_CHAIN` and experiment E5.
