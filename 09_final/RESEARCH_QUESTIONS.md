# 09 · Open research questions (ranked by how much they could change the design)

**Q1 — Can a device observe the interference it cannot decode?** (decisive)
Rate control with only decodable neighbours collapses a 1 000-device hall (0.47 vs 0.82,
simulated). Candidates: RSSI energy sampling on idle secondary channels (nRF radio driver),
the controller's truncated-chain status ratio, missed-AUX-after-pointer ratio, or a configured
`κ_INT` from venue type. Experiment: E5(c). If none works, crowd mode needs a conservative fixed
cap (e.g. ≤ 0.5 events/s per device whenever more than ~20 transmitters are decodable), trading
throughput for stability.

**Q2 — Do both target stacks deliver chained, anonymous, non-connectable extended advertising
to the host intact?** E1. Without chaining every crowd number drops by about a third.

**Q3 — What are the real reception and interference radii in a dense crowd?** The ratio sets
spatial reuse; the simulator's `r_rx` sweep moves N = 1 000 results from 0.46 to 1.00. E5 with
near/far receivers; ideally a measurement at an actual event.

**Q4 — ESP32-S3 BLE receive current.** E6. Decides whether H2 is more than a prototype.

**Q5 — Is ESP-NOW v2 a better data link for an ESP32-only population?** E5b.

**Q6 — Content-neutral storage defence that beats a continuous flood.** Group E shows every
tested policy degrades under a continuous flood (Theorem D says some degradation is unavoidable).
Open: admission tied to *physical* scarcity the attacker also pays for (e.g. objects first heard
in ≥ k distinct time windows), and its effect on genuinely rare pamphlets.

**Q7 — Real mobility.** Replace the synthetic city with public encounter traces; measure min-cut
sizes between districts (how many *forwarding* movers connect them).

**Q8 — Author localisation.** How well does "release in crowd" hide first transmitters from a
direction-finding observer? Needs an RF experiment with an attacker array.

**Q9 — Library privacy for couriers.** Is there a cheap way to forward without being
fingerprintable by content (e.g. carrying random subsets, delayed forwarding)? Trades
dissemination speed for privacy; unexplored.

**Q10 — v2 courier sync.** When does a rateless-IBLT connection between two large couriers beat
the carousel on airtime and energy? Only relevant if field libraries exceed ~10⁴ items.
