# 09 · Executive verdict — ZEMIZDAT-ARGON-1.0

**Can thousands of cheap, battery-powered devices exchange and propagate short written
pamphlets through spontaneous wireless encounters, without servers, accounts or identities?**

**Yes, conditionally — with a simpler design than a mesh network, and with hard limits that are
physics, not engineering.** Evidence is analytical, executed reference code, and simulation. No
hardware has been built or measured.

## What works (and how we know)

* **A connectionless broadcast carousel**, with no connections, keys, identities, routing or
  reconciliation protocol, serves everyone in range, including devices that never transmit.
  Simulated: 100 % of pamphlets everywhere within an hour up to ~500 devices per hall; 95 % at
  1 000; 98 % across six rooms of 500 people who walk between rooms; 100 % across a simulated
  city of 3 000 in 24 h.
* **Integrity from content addressing alone.** A hash-list identifier lets each 220-byte chunk be
  verified on arrival and collected from anyone, any time. Executed: Python and C implementations
  agree byte-for-byte; 2 million fuzzed frames under memory sanitizers produced no memory errors
  and no invalid object.
* **Crash-safe storage.** Executed: power cut at every byte of a write sequence, including garbage
  collection, never yields a corrupt or duplicated record (after a design bug this test found
  was fixed).

## What does not work, or only partly

* **A crowd adds receivers, not capacity.** One hall's shared airtime moves ~300 kB/s of pamphlet
  bytes. At 3 000 devices in one room, about 40 % of 2 400 one-KiB pamphlets reach the average
  person in an hour (simulated); everyone getting everything takes ≥ 20–24 minutes even with
  perfect scheduling (calculated).
* **Without density-adaptive rate control, broadcasting collapses** (0 % at 3 000 devices). Whether
  a real device can see the interference it needs to see for that controller is **the largest
  open risk** (Q1).
* **Flooding is jamming.** 20 % hostile transmitters cut a 500-device hall to 29 %; no protocol
  fixes that. Storage floods can be bounded (60/min admission quota keeps 82–88 %) but never
  prevented while publishing is anonymous (proved).
* **Interdiction beats majorities.** Removing the few people who carry pamphlets between groups
  partitions the network, whatever fraction of everyone else cooperates (proved; simulated).
* **Privacy is mode-dependent.** Listening is silent and private. Forwarding necessarily reveals
  what you carry; any inventory summary reveals more (the previously proposed digest leaked whole
  libraries — executed attack).

## Verdicts

| Item | Verdict |
|---|---|
| Hybrid carousel (crowd mode + burst mode) with store-carry-forward | **CONDITIONAL PROCEED** |
| Pure fixed-rate broadcast | **REJECT** (crowds) |
| Pairwise anti-entropy as primary | **REJECT**; **CONDITIONAL** as v2 courier sync |
| Standard BLE Mesh | **REJECT** |
| Summary beacons | optional, off by default |
| RELAY mode | **REJECT** (no shown benefit) |
| ESP-NOW link | **UNRESOLVED** (bench test) |
| Arduino UNO R4 WiFi for production | **REJECT**; bench helper only |
| ESP32-S3 | **CONDITIONAL PROCEED** (prototype; energy unknown) |
| nRF52840 + SPI NOR | **CONDITIONAL PROCEED** (production candidate) |
| Governance: threshold-signed, owner-consented updates, no kill switch | **PROCEED** (design) |

## The one recommendation

Build two ESP32-S3 and two nRF52840 boards and test whether anonymous, chained, non-connectable
extended advertising carries the reference test vectors to a silent receiver intact
(`NEXT_ACTION.md`). If it does not, the architecture changes before anything else is worth doing.

## Relation to the earlier (Gemini) run

That run reached a similar architectural shape but could not execute anything; its worked
example digest was fabricated, its inventory digest leaked libraries, its capacity figures were
off by one to two orders of magnitude, and its code was truncated. 21 specific issues are listed
in `AUDIT_OF_GEMINI_RUN.md`.
