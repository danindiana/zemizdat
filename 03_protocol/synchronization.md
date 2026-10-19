# 03 · Content synchronisation: what was compared, what was chosen

Numbers below are from `04_mathematical_analysis/scripts/sync_costs.py` (closed-form,
**theoretical**) and the simulator (**simulated**). Content bytes for comparison: a 1 KiB
pamphlet is 1 068 B on air (CPO + manifest leaves).

## 1. The question is not "which reconciliation algorithm"

Reconciliation answers *which ids does my counterpart lack?* In ZEMIZDAT's dominant regime —
a broadcast medium shared by many receivers with different gaps — there is no single
counterpart. Every reconciliation message is either addressed to one peer (wasting the
broadcast medium) or summarises one device's library to everyone (disclosing it, §5). The
carousel sidesteps the question: holders send what has not been heard recently; receivers keep
what they lack. Reconciliation matters only for (a) deciding to stay silent when everyone nearby
already matches (energy), and (b) pairwise bulk sync between two large libraries.

## 2. Comparison (bytes on air, both directions; RTT = interactive round trips)

| M | |D| | sorted inventory | 64-bucket digest + lists | 16-ary Merkle | Bloom 1 % | IBLT + estimator | rateless IBLT |
|---|---|---|---|---|---|---|---|
| 50 | 10 | 800 / 1 | 398 / 2 | 2 560 / 2 | 60 / 1 | 16 965 / 2 | 247 / 1 |
| 1 000 | 10 | 16 000 / 1 | 1 586 / 2 | 3 840 / 3 | 1 198 / 1 | 16 965 / 2 | 247 / 1 |
| 3 000 | 10 | 48 000 / 1 | 4 086 / 2 | 3 840 / 3 | 3 594 / 1 | 16 965 / 2 | 247 / 1 |
| 3 000 | 3 000 | 48 000 / 1 | 24 336 / 2 | 1 152 000 / 3 | 3 594 / 1 | 75 270 / 2 | 52 728 / 1 |
| 100 000 | 10 | 1 600 000 / 1 | 125 336 / 2 | 6 400 / 5 | 119 813 / 1 | 16 965 / 2 | 247 / 1 |
| 100 000 | 100 000 | 1 600 000 / 1 | 800 336 / 2 | 64 000 000 / 5 | 119 813 / 1 | 1 966 770 / 2 | 1 755 065 / 1 |

Working RAM for the structure at |D| = 10: inventory 256 B (streamed from the flash index),
digest 512 B, Merkle 256 B per level, Bloom 1.2 KB at M = 1 000 and 120 KB at M = 100 000 (does
not fit a 32 KB MCU), IBLT with estimator ≈ 17 KB, rateless IBLT ≈ 0.3 KB.

Persistent index (all methods): 12 B × M in RAM (sid64 + address), or a sorted flash index if
RAM is short (RA4M1).

## 3. Reading the table

* **Content dominates whenever |D| is large.** A fresh device meeting a 3 000-item courier must
  receive ≈ 3.2 MB of content; any reconciliation scheme's overhead (≤ 75 KB) is noise. Gemini's
  claim that IBLT "fails catastrophically" in this case conflated fixed-size IBLTs with rateless
  IBLTs (Yang et al., SIGCOMM 2024), which need no prior estimate of |D| and cost ≈ 1.35 |D|
  symbols using only XOR and hashing — no GF(2⁶⁴) algebra (that is PinSketch/BCH).
* **Reconciliation pays only for |D| ≪ M.** At M = 3 000, |D| = 10, a sorted inventory costs
  48 KB to discover 10.7 KB of missing content; rateless IBLT costs 247 B.
* **Bloom/cuckoo filters are one-sided and lossy**: a 1 % false-positive rate means 1 % of the
  missing items are never sent by that peer; harmless in a carousel, a liveness hole in
  pairwise-only sync unless filters are re-salted per encounter.
* **Merkle trees** need `log₁₆ M` interactive rounds — impossible on a connectionless medium,
  expensive for large differences.

## 4. Decision for v1

1. **Default: no reconciliation.** Demand-agnostic carousel with verified overhearing
   (`ZEMIZDAT_PROTO_1.0.md` §5).
2. **Optional: salted 64-bucket digest beacons (SDB)**, one 168-byte frame, used only as a
   *weight* in the carousel and to fall silent among identical neighbours. Linear in nothing,
   so not invertible; costs a streaming pass over the index per distinct salt received.
3. **Not in v1: exact pairwise sync.** If field data show courier-to-courier encounters with
   M ≥ 10⁴ and |D| ≪ M are common, add rateless IBLT over a connection as v2 (RA4M1 excluded).

The simulator's evidence for (1)–(2) is in `06_simulation/README.md` (group F ablations: age
weighting vs digest weighting; group C: beacons in sparse encounters).

## 5. Privacy of any reconciliation summary

See `01_formal_model/impossibility_results.md` §I. Executed demonstration: Gemini's XOR-fold
beacon reveals 100 % of a 300-item universe library and 97 % of a 1 000-item one from a single
beacon (`04_mathematical_analysis/results/xor_digest_attack.json`). The salted SHA-256 digest
removes linearity and cross-beacon linkability, but an observer who can enumerate plausible
library contents for one bucket can still test them. LISTEN devices send nothing and are the
only fully library-private participants.

## 6. Canonicalisation, revisions, metadata

* Identity is over exact bytes; authors' software normalises text (NFC) before signing off. A
  receiving MCU checks only UTF-8 well-formedness.
* Revisions are new objects. A revision MAY carry TLV 0x01 (parent id) so readers can thread
  them; nothing is ever mutated or superseded in storage.
* Metadata that should not affect identity (hop count, local receive time, user tags) lives
  outside the CPO — in the local record header (flags, receive epoch) — and is
  never hashed.
