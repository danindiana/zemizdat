# 02 · Candidate D — store-carry-forward (with optional local relays)

Every COURIER is already store-carry-forward: it keeps what it receives and transmits it later,
elsewhere. D is therefore not an alternative to C but the mechanism that makes C work beyond one
room. The questions are about **which items to carry and forward**, and whether live relays add
anything.

| Topic | Finding |
|---|---|
| opportunistic mobility | the only inter-room / inter-district channel; its rate sets speed in Environments 2 and 3 (`temporal_graphs.md`) |
| epidemic routing | the carousel is epidemic routing with broadcast; replication is limited by storage and carousel rate rather than by explicit copy counters |
| controlled replication (spray-and-wait etc.) | needs per-message copy tokens and per-encounter handshakes; with broadcast every transmission already reaches all nearby — "copies" are not countable, and counting needs identities. Not adopted. |
| sparse networks | contact duration × airtime per contact limits what moves per encounter; late in a day the network is capacity-limited, not reachability-limited |
| dense gatherings | same as C |
| temporal connectivity | determines feasibility (Theorems C, L2); interdiction = temporal min-cut |
| intermediate couriers | high-mobility people between groups are the bridges; their loss is the interdiction attack (group D) |
| local broadcast forwarding | = the carousel |
| battery-aware scheduling | rate cap per hour, thresholds at 20 %/10 %, idle duty when alone |
| live relays (RELAY mode) | no benefit shown inside an interference domain; a doorway device already serves both sides as a COURIER. E3b tests it. |

## Erasure / fountain / network coding

Considered for the carousel: a holder could send random linear combinations (fountain-coded
chunks) so a receiver needs *any* `k` symbols instead of *specific* ones. Benefit: removes the
per-chunk coupon-collector tail across multiple senders. Costs: (i) per-symbol verification is
lost — a coded symbol cannot be checked against a manifest leaf without homomorphic hashing,
reopening the pollution attack that per-chunk leaves closed; (ii) decoding needs `k × 220 B` RAM
per object and GF(2⁸) arithmetic; (iii) mixing *across* pamphlets (network coding) defeats the
dedup-by-id model. The simulator's sliding-window chains with random offsets already spread
chunks evenly; ORACLE vs HYBRID (group A) shows the remaining gap is in *which pamphlet* is sent,
not in chunk-level redundancy. **Verdict: REJECT for v1** — benefit unproven, pollution resistance
lost. Re-evaluate only if E5 shows a large chunk-tail loss.

**Verdict for D:** **PROCEED** as an integral part of C; **REJECT** controlled-replication and
network coding for v1.
