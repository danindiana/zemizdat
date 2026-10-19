# 09 · Architecture decision record — ZEMIZDAT v1

**Status:** CONDITIONAL PROCEED (pending E1, E5, E6, E7).
**Date:** 2026-10-19. **Evidence:** analysis + executed reference code + simulation; no hardware.

## Decision

1. **Data link:** connectionless BLE 5 extended advertising, non-connectable, non-scannable,
   anonymous; 3-PDU AUX chains on 2M PHY. No connections, no pairing, no network keys.
2. **Content identity:** hash-list id over 220-byte chunks; per-chunk verification on arrival;
   immutable objects ≤ 4 064 B; no author field, no hop count.
3. **Dissemination:** a carousel on every device permitted to transmit, with
   * density-adaptive rate control (crowd mode), holding primary/secondary load ≈ 0.25/0.15;
   * burst mode when ≤ 8 transmitters are in range (full scan duty, 100 events/s);
   * least-recently-heard weighting and verified suppression;
   * no reconciliation protocol; summary beacons optional and **off** by default.
4. **Participation:** permission bits RX/STORE/ORIG/FWD; presets LISTEN, EXCHANGE, COURIER. LISTEN
   never transmits. No RELAY mode.
5. **Storage:** log-structured NOR store with separate delete flag, one spare sector, mount-time
   recovery including interrupted GC; RAM index of (sid64, address).
6. **Budgets:** 60/min admission quota; refuse when full except evicting unpinned items older than
   24 h; transmit and radio-on caps; battery thresholds.
7. **Governance:** separate plane; ROM/bootloader signature + threshold-signed release policy +
   physical owner consent; anti-rollback; USB-only updates in v1; no kill switch.
8. **Hardware:** prototype on ESP32-S3 (incl. the UNO R4 WiFi's own module, flashed directly);
   production candidate nRF52840 + 8 MB SPI NOR; UNO R4's RA4M1 rejected except as a bench helper.

## Alternatives rejected, and why (one line each)

* Pairwise anti-entropy as the primary design — listeners can never receive (0 % in every
  simulated scenario); per-encounter inventories; connection assumptions fragile.
* Fixed-rate broadcast — collapses beyond a few hundred transmitters per hall (0 % at 3 000).
* BLE Mesh — provisioning, shared keys, sequence numbers (identities), relay flooding.
* XOR-fold digests — linear, leak the library (executed attack).
* Merkle / Bloom / IBLT reconciliation in v1 — interactive or lossy or unnecessary in the dominant
  broadcast regime; rateless IBLT kept for a possible v2 courier sync.
* Erasure / network coding — loses per-chunk verification; no demonstrated gain.
* Time-stratified eviction — does not protect against continuous floods (corrected simulation).
* Proof-of-work anti-spam — favours GPU attackers over MCU authors.
* Author signatures in v1 — create linkable identities; do not address the dominant threats.

## Conditions that would reverse the decision

| If… | then… |
|---|---|
| E1: chained anonymous ext. advertising unavailable on both stacks | fall back to single-PDU events (≈ −34 % crowd goodput) or ESP-NOW (ESP32-only) |
| E5: no usable observable for undecodable interference (Q1) | crowd mode gets a conservative fixed cap; drop the claim of usefulness in 1 000+ device halls |
| E6: ESP32-S3 scan current > 25 mA average at 30 % | ESP32-S3 prototype only; move to nRF52840 earlier |
| E7: real-flash power cuts corrupt records | stop; storage redesign |
| field data: most encounters are two large couriers with |D| ≪ M | add rateless-IBLT connection sync (v2) |

## Assumptions this decision depends on

Listed with sensitivities in `04_mathematical_analysis/uncertainty.md` and
`08_verification/evidence_gaps.md`; the three that matter most are rate-control observability,
reception/interference radius ratio in crowds, and chaining support.
