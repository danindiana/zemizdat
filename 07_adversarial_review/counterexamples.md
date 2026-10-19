# 07 · Self-adversarial review: counterexamples against the preferred architecture

The preliminary favourite (after groups A/B) was: rate-controlled chained broadcast carousel,
weighted by beacon digests and overhearing, with verified suppression. Below, each attempt to
break it, what happened, and what changed. "Changed design" entries are already reflected in
`03_protocol/`.

### CX1 — A crowd so dense that discovery traffic itself saturates the channel
*Attack:* 3 000–5 000 devices in one hall, each advertising at 10 Hz.
*Result:* unregulated broadcast collapses (BCAST, group A: mean completeness 0 at N = 3 000;
`G_p + G_a` ≫ 1). Discovery **is** data here, so there is no separate discovery overhead to
saturate — but uncontrolled data does.
*Satisfies properties?* Safety yes; liveness no without rate control.
*Intrinsic?* Yes (ALOHA). *Cheaper alternative?* None; rate control is the minimum.
*Distinguishing experiment:* E5(a) vs E5(b).

### CX2 — The rate controller cannot see who is interfering
*Attack (on our own idealisation):* the simulator's controller knew its interference domain's
transmitter count; a real device counts only what it decodes.
*Result (group G, N = 1 000, 30 min):* idealised controller 0.82; decodable-count-only
controller (`κ = 1`) 0.47 with combined load `G ≈ 1.5`; `κ = 3` 0.76; `κ = 10` 0.85. **This is the largest open risk in the design.**
*Recoverable?* Yes if an observable for undecodable interference exists (RSSI energy, truncated
chain ratio). *Intrinsic?* Implementation-specific (depends on radio-stack access).
*Changed design:* explicit `κ_INT` parameter + research question Q1; acceptance test AT7.
*Experiment:* E5(c).

### CX3 — A device that repeatedly presents new identities (Sybil)
*Result:* nothing in the protocol counts devices or trusts senders, so identities buy nothing.
A Sybil flooder is just a flooder (CX6/CX7). *Satisfies properties:* yes.

### CX4 — A mobile node carrying an enormous library
*Attack:* a courier with 10⁴–10⁵ items meets fresh devices.
*Result:* no inventory exchange to blow up (no reconciliation by default); receivers' admission
quota and capacity bound intake; the courier's carousel weights by "not heard recently", so it
does not monopolise airtime beyond its rate-controlled share. With beacons on, M = 10⁵ makes each
bucket hold ~1 560 items — the digest becomes nearly uninformative (`synchronization.md`), which
is one more reason beacons are off by default.
*Satisfies properties:* yes. *Experiment:* E4 scaled.

### CX5 — A library that is full before rare publications arrive
*Result:* naive admission refuses everything new until the owner deletes. v1: refuse, but allow
eviction of unpinned items older than 24 h; pin what you care about. Rare items still lose against
volume (Theorem D).

### CX6 — Unlimited unique-content injection (flooder) with finite storage
*Result (group E, capacity 600, flooders at 5 events/s, h = 0.95):* naive 0.24; strata 0.39;
quota 60/min 0.82. None restores 1.0 (Theorem D). *Changed design:* 60/min admission quota as
default; stratified eviction dropped after the corrected simulation showed it does not help
against continuous floods.

### CX7 — Flooding as channel occupation
*Result (group B):* with 5 % of devices flooding at 50 events/s the hall is already at the edge
(HYBRID mean ≈ 1.0 at h = 0.95, ≈ 0.86 at h = 0.90, ≈ 0.29 at h = 0.80). Pairwise anti-entropy is
charged for the flooders' AUX traffic on the shared 37 channels (an earlier model version wrongly
spared it) but still degrades far less (≈ 0.80 → 0.78 at h = 0.8), because connection data never
needs the 3 primary channels the flood saturates. Its listeners remain at 0.
*Intrinsic:* yes — a protocol-level flooder is a jammer (Theorem H). *Recoverable:* when it stops.

### CX8 — Forged suppression headers
*Result (group B, `suppress`):* no measurable effect at N = 500 with either naive or verified
suppression (both 100 %): spare capacity absorbs a one-round deprioritisation. The vulnerability
is real by construction (a forged header costs the attacker 1 frame and suppresses every honest
holder in range for that item), so the fix is kept because it costs one 220-byte comparison —
but its benefit is argued, not shown. *Changed design:* I10.

### CX9 — A node falsely advertising a complete (or empty) inventory
*Result:* beacons only weight the carousel, never gate it; age weighting and the floor keep every
item moving. A liar can misdirect a fraction of airtime in its tile. *Changed design:* beacons
optional and off by default; groups C and H show no gain in city or rooms and a loss in the densest halls.

### CX10 — Power loss during flash writes
*Result:* the first storage design **failed**: a torn delete made recovery stop parsing and lose
all later records in the sector — found by the exhaustive power-cut test. *Changed design:*
separate deletion flag; interrupted-GC recovery. Now passes every-byte cuts including GC
[executed]. *Remaining:* real NOR behaviour (E7).

### CX11 — An otherwise cooperative network with disconnected temporal components
*Result (group D):* two rooms of 200 joined only by bridge couriers: with bridges, mean
completeness ≈ 0.84 (2 bridges) / 1.00 (8 bridges); with bridges silenced ≈ 0.48–0.50 — each
side keeps only its own share, regardless of cooperation. *Intrinsic:* yes (Theorem C).

### CX12 — Devices whose clocks differ significantly
*Result:* nothing compares clocks across devices; all timers are local monotonic. Unaffected.

### CX13 — A passive receiver surrounded by devices that only answer targeted requests
*Result:* receives nothing (Theorem F) — the pairwise baselines demonstrate it (listener
completeness 0 everywhere). The carousel exists precisely to avoid this.

### CX14 — Two-person encounters in a city (found by our own simulation)
*Attack on the design, not by an adversary:* the crowd-optimised carousel (30 % scan duty,
25 events/s cap, suppression that skips slots) wastes brief contacts.
*Result:* city, 24 h, N = 3 000: pairwise anti-entropy brought couriers to 100 %, the hybrid only
to ≈ 50 %. *Changed design:* **burst mode** (≤ 8 transmitters nearby → full scan duty, 100 events/s,
refill suppressed slots). Re-simulated: see group C in `06_simulation/README.md`.
*Experiment:* E3/E4 with two devices walking past each other.

### CX15 — Author located by first sighting
*Result:* with no hop count, the first transmission of a new id still marks its first
transmitter to a direction-finding observer. *Changed design:* hop field removed; release-in-
crowd rule. *Residual:* bounded, not eliminated.

## Did the review succeed?

No single counterexample invalidated the architecture's core (connectionless carousel + content
addressing + local limits), but four forced design changes (burst mode, verified suppression,
separate delete flag, hop removal) and one remains open and decisive (CX2: rate-control
observability). The review is therefore **not** declared successful on coherence; it is
conditional on E5.
