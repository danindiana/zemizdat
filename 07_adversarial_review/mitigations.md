# 07 · Mitigations, cheapest first

For each attack: required capability · affected property · failure mechanism · low-cost
mitigation (in v1) · expensive mitigation (not in v1) · residual risk · evidence needed.

| Attack | Capability | Affected | Mechanism | Low-cost (v1) | Expensive | Residual | Evidence |
|---|---|---|---|---|---|---|---|
| repeated duplicates | A2 | airtime | re-sending held items | dedup by sid before any work; duplicates count as "heard" (they even help suppression) | — | airtime consumed (same as a jammer at that rate) | E2 |
| unlimited unique injection | A3+A4 | storage, admission, airtime | valid junk objects | admission token bucket (60/min); pinning; user deletion + tombstones (time-stratified eviction tested and dropped) | per-author scarce credentials (breaks anonymity); PoW (asymmetric vs GPUs) | bounded fraction of storage per epoch is junk (Theorem D) | group E |
| invalid hashes / forged chunks | A2 | integrity, staging | garbage under honest sid | per-chunk leaf check on arrival (I9) | — | none for integrity | executed tests |
| malformed payloads | A2 | memory safety | parser bugs | strict bounded parser, no heap, fuzzing | formal verification of the parser (e.g. Frama-C) | radio-stack bugs below HCI | C fuzz; AT10 |
| false inventory claims (beacon lies) | A2+A4 | scheduling efficiency | fake "I differ in every bucket" or "I match" | beacons only *weight* the carousel; age weighting and floor keep everything moving; beacons optional | — | some airtime misallocated | sim (beacons on/off) |
| false delivery acknowledgements | — | — | v1 has no acknowledgements | nothing to forge | — | — | by design |
| forged suppression headers | A2 | availability of specific items | holders think item was just served | verified suppression: compare overheard bytes to own copy (I10) | — | none beyond airtime | group B `suppress` |
| replay | A1+A2 | — | objects are immutable; no freshness semantics | none needed | — | — | by design |
| Sybil identities | A4 | anything that counts peers | — | nothing counts peers | — | — | by design |
| exhausted storage | A3 | retention | see injection | see injection | — | see Theorem D | group E |
| resource exhaustion (battery) | A2 | battery | keep victim receiving/hashing | hashing bounded by radio rate; hourly radio-on cap; battery thresholds | — | victim's useful reception reduced | E6 |
| channel occupation / flooding | A5 | availability | ALOHA collapse | none in software beyond detection + UI warning; people carry data out of the area | other bands/PHYs (Coded PHY, sub-GHz) | total local outage while it lasts (Theorem H) | group B `flood` |
| compromised firmware (one device) | A2 | its own behaviour | acts as any of the above | same as above — nothing trusts any device | — | — | — |
| compromised release keys (< t) | A7 | updates | — | threshold policy | — | none | — |
| compromised release keys (≥ t) | A8 | all devices whose owners accept | malicious signed update | owner consent, reproducible builds, public log | hardware attestation of build provenance | owners who accept fast | process |
| intermittent channel unavailability | A5 | latency | outages | slots persist up to 120 s; chunks accumulate across outages | flash-persisted slots | longer latency | E5 |
| disrupting critical contacts | A10 | reachability | temporal min-cut | none in protocol; many independent movers is the only defence | — | partitions (Theorem C) | group D |
| library fingerprinting | A1 | privacy | content of transmissions/beacons | LISTEN mode; salted non-linear beacons, off by default; anonymous adv | private set reconciliation (PSI-based) | couriers recognisable by what they carry | `xor_digest_attack.py` |
| author localisation | A1 + DF | authorship privacy | first sighting of a new id | release-in-crowd | — | determined DF observer | E5 (density estimate) |

## Do minimal defences suffice?

* **Integrity, memory safety, resource bounds:** yes — cheap, local, executed tests pass.
* **Availability against a protocol-level flooder:** no software defence exists; the flooder is a
  jammer. What the minimal defences guarantee is that the damage ends when the flooder leaves
  (nothing corrupt or stuck remains) — evidence group B.
* **Retention against junk:** bounded, not prevented — evidence group E.
* **Privacy:** sufficient for LISTEN; for COURIERs only against address-based tracking.

Optional cryptographic credentials (author signatures, membership tokens) were evaluated and
**not** adopted: the threat model's dominant attacks (flooding, interdiction) are not addressed by
signatures, and credentials either create identities (privacy loss) or are Sybil-able.
