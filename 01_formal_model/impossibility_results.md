# 01 · Fundamental limits and impossibility boundaries (mission §17 A–H)

Each result is labelled with how it is established. Numbers come from
`04_mathematical_analysis/scripts/*.py` (executed) unless marked otherwise.

## A. Storage lower bound for universal completeness [proved]

`O_all` requires every receiver to store `M` records: `F_i ≥ M·(L̄ + h)`, where `h` is per-record
overhead. In this design `h = 48 B` header + 12 B RAM/flash index entry, and canonical length is
`12 + body`. For `M = 3 000` pamphlets with 1 024-byte bodies: `3 000 × (1 036 + 48) = 3.25 MB`
of flash per device (plus the 12 B × 3 000 = 36 KB index). Network-wide, full replication of
3 000 × 3 000 is 9.75 GB. Consequences:

* RA4M1 (256 KB code flash + 8 KB data flash) cannot hold even ~230 such pamphlets.
* nRF52840 internal 1 MB (minus firmware) holds roughly 600–700; an external 8 MB SPI NOR is
  needed for the 3 000-pamphlet scenario.
* ESP32-S3-MINI-1-N8's 8 MB flash holds the scenario with room for two firmware slots.

## B. Communication lower bound [proved + estimate]

Each receiver must decode at least the frames it lacks: for a 1 KiB pamphlet, 5 chunks + 1
manifest = 6 frames of 236 B. No coding scheme reduces the *received* information below the
entropy of what is missing; erasure/fountain coding can only remove the *coupon-collector*
redundancy of uncoordinated repetition (see `02_candidate_architectures/comparison.md` §coding).

Broadcast saves **transmissions**, not receptions: one event serves every receiver in its
reception tile. The intrinsic gain over unicast is the number of receivers per tile that still
lack the item — not `N`. For 3 000 people at 1 /m² with ~10 m reception tiles inside one ~35 m
interference domain, one copy per tile is needed: ≈ 30 copies instead of ≈ 3 000, a ~100×
reduction in bits on air [estimate]. Gemini's "3 000×" assumed every device hears every
transmission; its "102 hours" unicast figure assumed a single 200 kbit/s channel. BLE
connections use 37 data channels, and at an assumed 13.6 Mbit/s effective aggregate the same
unicast load takes ≈ 1.6 h. The advantage of broadcast is real but about two orders of magnitude,
not three and a half [estimate].

Per-receiver lower bound in the auditorium: optimal domain goodput ≈ 1 254 frames/s for 1 KiB
pamphlets sent as 3-PDU chains [estimate, `airtime_model.py`], split over ≈ 30 tiles, at 30 % scan
duty → ≈ 12.5 frames/s per receiver → **≥ 24 minutes** to receive 3 000 × 6 frames even with
perfect scheduling. Scan duty is therefore a first-order design variable (energy vs latency).

## C. Contact-network limitation [proved]

If the temporal graph restricted to the participants has a cut that is crossed only finitely
often (Theorem L2), no protocol delivers across it. Majority cooperation does not help: in the
barbell experiment, silencing a handful of bridge couriers confines every pamphlet to its side
regardless of how cooperative the rest are [simulated, group D].

## D. Anonymous publishing × finite storage × guaranteed retention [proved]

*Claim.* No content-neutral protocol can simultaneously provide (1) publishing without any scarce
credential, (2) finite per-device storage `C`, and (3) retention, by every honest courier that
receives it, of every honest pamphlet.

*Proof.* Under (1) an adversary can produce `C + 1` valid objects at negligible cost and, by
rotating addresses, make them indistinguishable in origin from `C + 1` honest authors. A device
with capacity `C` that receives these plus one honest pamphlet must drop or evict at least one of
`C + 2` objects that the policy cannot tell apart (content-neutral). The adversary chooses
arrival order after seeing the policy; for any deterministic policy it can place the honest item
where it is dropped; for a randomised policy the honest item is dropped with probability ≥
`1/(C+2)` per such episode, and the adversary can repeat episodes. ∎

*Engineering consequence.* Defences can only bound **how fast** and **how much** a single
flooder pollutes: per-time admission quotas, user pinning, refusal when full. (Time-stratified
reservoirs were also evaluated; they protect only against *bursty* floods — group E.) Proof-of-work does not rescue (1):
a battery MCU author computes perhaps 10⁴–10⁵ SHA-256/s while a GPU adversary computes ≥ 10⁹/s,
so any difficulty that costs the attacker meaningfully locks out honest MCU authors
[estimate; MCU hash rate to be measured].

## E. Zero retransmission × reliable delivery under loss [proved]

With per-frame loss `p` and no feedback, a `k`-frame object sent once arrives intact with
probability `(1−p)^k`. Reaching `1−δ` requires each frame (or each coded symbol) be sent
`r ≥ ln(δ/k)/ln p` times (union bound). With feedback (pairwise) the redundancy can be adaptive
but never zero. Passive LISTEN receivers provide no feedback, so repetition is unavoidable in any
design that serves them.

## F. Completely silent reception [proved]

A device that never transmits can acquire only what neighbours transmit unprompted. If every
neighbour only answers explicit requests, it acquires nothing. Corollary: any architecture that
includes LISTEN must include unsolicited transmission (a carousel), which pairwise anti-entropy
alone does not. [Simulated confirmation: listener completeness 0 under PAIRWISE and AE_INV.]

## G. Local completeness detection [proved]

In an open population with unknown `N` and `M`, no device can decide `S_i = P`: an unseen device
holding `p' ∉ S_i` is indistinguishable from its absence. Completeness can only be declared
relative to an externally defined collection (e.g. a signed event manifest listing ids — which
would itself be a centralised artifact; out of scope for v1).

## H. Adversarial physical interference [proved]

If energy on all 40 BLE channels (or the chosen Wi-Fi channel) keeps SINR below the decoding
threshold throughout a region and interval, throughput there is zero; no software measure
changes that. What survives: (i) safety (nothing corrupt is committed — I2), (ii) store-carry-
forward across space and time (people walk out of the jammed area), (iii) detection (a device
can tell the user "channel unusable"). A flooding device that ignores rate control is, at the
physical layer, a jammer: in the simulator (500-device hall, flooders at 50 events/s), 5 %
flooders are absorbed (0.997), 10 % cut mean completeness to 0.86 and 20 % to 0.29 [simulated,
group B]. "Uncensorable", "untraceable" and "jam-proof" are therefore not
claims this project can make.

## I. Reconciliation discloses the library (added) [proved + executed]

Any set-reconciliation message that lets a counterpart compute what it lacks also lets anyone in
radio range who knows the pamphlet universe `U` learn about the sender's library. For XOR-fold
digests (Gemini's design) this is literal linear algebra: one beacon recovers 100 % of the library
at `M = 300` and 97 % at `M = 1 000`, and leaves only 1 273 of 3 000 bits undetermined at `M = 3 000`
[executed, `xor_digest_attack.py`]. Bloom/cuckoo filters let anyone test membership of any known
item; IBLTs decode `U ∖ S` when it is small. Salted non-linear digests (adopted) stop trivial
linking across beacons but still reveal which buckets differ. **Only LISTEN is library-private.**
Forwarding is inherently disclosing: a courier's transmissions are its library.

## J. Anonymity × Sybil resistance (added) [argument]

Without a scarce identity, a single adversary can appear as any number of devices; therefore any
mechanism that counts devices (votes, "heard from k distinct sources", per-peer quotas) is
defeated by address rotation. Every defence in this design is per-receiver and per-time, never
per-sender.
