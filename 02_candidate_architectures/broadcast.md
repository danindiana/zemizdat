# 02 · Candidate A — pure broadcast dissemination

Devices repeatedly broadcast whole pamphlets (as frames) on connectionless advertising; listeners
keep what they lack. No connections, no acknowledgements, no inventories.

| Aspect | Analysis |
|---|---|
| discovery | none needed: data frames are discovery |
| receive-only mode | native; a listener transmits nothing (Theorem F: it gets only what others volunteer) |
| one-to-many | one event serves every scanning receiver in its reception tile |
| redundancy | uncoordinated repetition: a receiver needing all `M` items from a random carousel waits a coupon-collector factor `≈ ln M` over ideal |
| collisions | unslotted ALOHA on 3 primary + 37 secondary channels; collapse beyond ~100–200 transmitters per domain at 10 Hz (`communication_bounds.md` §3) |
| payload limits | 255 B per AUX PDU; ~1 650 B per chained event (spec maximum); ZEMIZDAT uses 3-PDU chains |
| segmentation | ≤ 19 × 220 B chunks + manifest; per-chunk verification lets pieces combine across senders |
| no acknowledgements | loss handled by repetition only (Theorem E) |
| privacy | listeners invisible; transmitters reveal what they send; no addresses needed (anonymous adv) |
| power | dominated by receive duty, not by transmission (`battery_budget.md`) |

**When simple repeated broadcasting beats elaborate synchronisation [estimate + simulated]:**
when (i) the number of transmitters per interference domain is below ~100 at 10 Hz (or any
number, with rate control), (ii) libraries are small relative to contact capacity, and (iii) many
receivers share the same gaps (early in an event, or many listeners). Group A shows BCAST
matching everything else up to N ≈ 100 in one hall and collapsing at N ≥ 500.

**Verdict: CONDITIONAL PROCEED — as the transport, not the scheduler.** Unregulated BCAST is
**REJECTED** for crowds (it fails the 3 000-device scenario by construction). Broadcast with
density-adaptive rate control and a smarter choice of what to send is Candidate C.
