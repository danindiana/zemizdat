# 04 · Storage bounds and the capacity-planning model

## 1. The original formula `C = ⌈N·K·(1+s)⌉`

`N` = contributors you expect to *encounter*, `K` = pamphlets per contributor, `s` = margin.
It conflates **encounters** with **reachable content**. A single encounter with a courier carries
that courier's entire library. Two failure modes:

* *Under-provisioning:* expecting 10 encounters (C = 12) and meeting one courier with 2 500
  items: storage fills on the first encounter and 99.5 % of reachable content is refused.
* *Over-provisioning:* 500 expected encounters in a 200-person conference counts the same
  people repeatedly.

## 2. Replacement model

Separate what the owner can estimate from what the device must enforce.

```
M_reach  = N_pop · K           # distinct pamphlets in the community/event, NOT encounters
f        = fraction of it the owner wants to be able to keep (0..1)
C_slots  = min( floor( F_alloc / (L̄ + 48) ),  ceil( M_reach · f · (1+s) ) )
```

* `F_alloc` = flash given to the library; `48` = record header; index RAM = 12 B × C_slots.
* Expected distinct items seen after `m` encounters with couriers each holding an independent
  random fraction `q` of the pool: `M_reach (1 − (1−q)^m)`. With `q` ≈ 0.5 (a well-mixed
  conference after an hour), three encounters already expose 88 % of everything — encounter
  count is a poor proxy for reachable content.

## 3. Budgets the firmware enforces independently

| Budget | Unit | Enforced by | Independent of others? |
|---|---|---|---|
| flash capacity | records, bytes | admission | yes |
| RAM working set | static (`K_SLOT`, index) | compile time + C_slots | yes |
| daily receive budget | admissions/min token bucket | admission | yes |
| daily transmit budget | events/hour | scheduler | yes |
| flash-write budget | implied by admissions | — | endurance not binding (§storage.md 7) |
| computation | SHA-256 per received chunk; bounded by receive rate | radio duty | yes |
| radio duty cycle | δ_active, δ_idle, hourly radio-on cap | scanner | yes |
| battery reserve | % thresholds | power manager | yes |

All are enforceable locally without trusting anyone. None can guarantee *usefulness* of what is
admitted (Theorem D).

## 4. Admission fairness under storage exhaustion

Honest statement of the limit (Theorem D): with anonymous publishing and finite storage, a
flooder in range can always displace some honest content; defences only bound the rate and the
share. Content-neutral defences evaluated in simulation group E:

1. **naive** — admit until full, then refuse. A flood early in the day locks storage for the
   rest of it.
2. **quota** — token bucket on admissions per minute (all sources). Slows a flood; also slows
   honest intake in bursts.
3. **strata** — capacity divided over time epochs; a flood can occupy only its epoch's share.

Simulated outcome (group E: N = 500, capacity 600, flooders at 5 events/s, 60 min; mean
completeness at h = 0.98 / 0.95): naive 0.53 / 0.24; quota 60/min **0.88 / 0.82**; quota 150/min
0.58 / 0.49; strata 0.60 / 0.39; quota 150 + strata 0.63 / 0.60. The first strata implementation
in the simulator was wrong (it treated a continuous flood as a single epoch and reported 1.00);
corrected, strata does not protect against continuous floods. v1 uses the 60/min quota. It does
bind honest traffic briefly at the start of a dense event (≈ 4 300–5 200 refused completions per
device in the benign 500-device run, all re-received later; coverage times unchanged at 60 s
resolution).

## 5. Universal-completeness lower bound

`F ≥ M (L̄ + 48)` per device. For M = 3 000 one-KiB pamphlets: 3.25 MB per device, 9.75 GB across
3 000 devices. Collective retention (`O_union`) needs only that *some* device keeps each item:
with random retention of a fraction `f` per device and `n` devices that saw an item, the item
survives with probability `1 − (1−f)^n` — for `f = 0.2`, `n = 30`: 0.9988 [proved arithmetic].
Full replication is therefore a choice made for *reading* convenience, not for survival.
