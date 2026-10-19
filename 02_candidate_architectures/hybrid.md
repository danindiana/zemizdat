# 02 · Candidate C — hybrid: broadcast transport + demand-aware carousel

What "hybrid" ended up meaning after analysis — not "broadcast for discovery + connections for
transfer" (that inherits B's listener exclusion and connection costs), but:

* **transport:** connectionless chained advertising only (Candidate A's medium);
* **rate:** density-adaptive, holding primary/secondary load near `G ≈ 0.25 / 0.15`;
* **choice:** weighted carousel — items not heard recently go first (overhearing), optionally
  weighted by salted bucket-digest beacons from neighbours;
* **suppression:** a holder that overhears a verified frame of an item it holds deprioritises it;
* **listeners:** served by the same transmissions; a floor keeps sending even when all
  beaconing neighbours match.

Questions from the brief:

| Question | Answer |
|---|---|
| When is broadcasting preferable? | Whenever ≥ 2 receivers in a tile share a gap, and always when listeners are present. |
| When is pairwise preferable? | Two large, mostly identical libraries with a long contact (then exact reconciliation saves airtime). Not in v1. |
| Can a device switch strategies dynamically? | Yes, and it must. Crowd mode (many transmitters): shared airtime is scarce → rate control, suppression frees airtime. Burst mode (≤ 8 transmitters): contact time is scarce → full scan duty, high event rate, suppressed slots refilled. Without burst mode the hybrid loses badly to pairwise sync in the city model; with it, it matches pairwise for couriers and still serves listeners. |
| How does congestion affect the decision? | It sets the event budget; it does not change what to send. Without rate control, everything collapses. |
| Do passive participants remain useful? | They receive at no airtime cost; they do not forward. They are invisible to beacon demand, which is why the floor and age weighting exist. |
| How to avoid excessive control traffic? | Beacons optional and ≤ 1 frame per 4 s; no per-peer state; suppression is implicit (overhearing). |

**Verdict: PROCEED** (with Candidate D's store-carry-forward built in). Evidence and
assumptions: `comparison.md`, `06_simulation/README.md`.
