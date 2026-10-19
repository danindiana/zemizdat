# 02 · Candidate B — pairwise anti-entropy over connections

Devices discover each other, open a BLE connection, exchange inventories (or blindly push), and
transfer exactly what the other lacks with link-layer acknowledgements.

Two variants are simulated: **PAIRWISE** (blind push: send items in random order, receiver
aborts duplicates after the first chunk) and **AE_INV** (full sorted sid64 inventory exchange,
then exact differences).

| Aspect | Analysis |
|---|---|
| connection overhead | advertise → CONNECT_IND → MTU/DLE/PHY update → GATT discovery: modelled as 0.4 s [assumption]; competes for the same primaries as everyone's advertising |
| inventory cost | 8 B × (|S_a| + |S_b|) per encounter for AE_INV: 48 KB for two 3 000-item libraries, repeated at every re-encounter, even when identical |
| dense scalability | connections occupy data channels in parallel (37 channels); aggregate goodput per domain is the binding constraint — modelled as 1.5 MB/s [assumption, E5] |
| RAM | connection context + inventory streaming buffer; modest on ESP32/nRF, tight on RA4M1 |
| duplicates | none with AE_INV; ~1 chunk per duplicate with blind push |
| repeated encounters | AE_INV pays the inventory each time; blind push re-sends headers |
| when it wins | two devices with large, mostly overlapping libraries, long contact (courier-to-courier bulk sync) |
| fatal flaw for this project | **a LISTEN device can never participate** — a BLE connection requires it to transmit. In every simulated configuration listener completeness is exactly 0. |
| privacy | each connection exchanges (and can log) the two inventories; connection addresses persist for the session |

**Verdict: REJECT as the primary architecture** (fails O5/O9 for listeners and leaks libraries).
Gemini rejected it for "catastrophic collapse"; the simulation does not support that reason —
for transmitting devices pairwise anti-entropy is competitive in a dense hall *under the stated
link assumptions* (see `comparison.md`). **CONDITIONAL** as a v2 add-on for courier-to-courier
bulk sync with rateless IBLT, if E5 confirms connection goodput.
