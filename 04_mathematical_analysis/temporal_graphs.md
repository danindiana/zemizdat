# 04 · Temporal graphs: when does adding cooperative people help?

The mission's thesis: many independent cooperative devices create many communication
opportunities, so suppression gets expensive. This file turns that into conditional,
falsifiable statements. Labels: **[proved]**, **[heuristic]** (standard approximation, stated
assumptions), **[simulated]**.

## 1. The right objects

* **Temporal graph** `𝒢 = (V, {(u, v, t, d)})`: contacts with start `t` and duration `d`.
* **Temporal path / reachability**: `u ⇝ v` within `[0, T]` if a time-respecting sequence of
  contacts, each long enough to move the object (`d ≥ τ_min`), leads from `u` to `v`.
* **Temporal cut**: a set of contacts (or of devices) whose removal destroys all `u ⇝ v` paths.
* The **travelling-salesman** analogy is not the right model: nobody plans a tour. The
  questions are *reachability under random contacts* (epidemics) and *interdiction* (an
  adversary removes nodes/contacts to cut reachability) — a network-interdiction / min-cut
  problem on the temporal graph.

## 2. Homogeneous mixing: the epidemic baseline [heuristic]

Assumptions: each device meets others at rate `β` (contacts/hour), partners uniformly random;
a fraction `c` are couriers (forward); a contact transfers a given missing pamphlet with
probability `γ` (enough duration and airtime); no storage limit; independence between contacts.
Then the fraction `x` of couriers holding pamphlet `p` follows the logistic SI equation
`ẋ = β γ c · x (1 − x)`, and the time from one holder to a fraction `α` of couriers is

```
T_α ≈ [ ln(cN − 1) + ln(α / (1 − α)) ] / (β γ c)
```

Non-couriers (LISTEN, EXCHANGE) acquire `p` at rate `β γ c x` and lag couriers slightly.

Consequences, each a falsifiable prediction:

1. **Adding cooperative couriers at fixed per-device contact rate speeds things up roughly as
   `1/c`** (`T ∝ 1/c`, plus a `ln` term).
2. **Adding people at fixed per-person contact rate does *not* speed things up**: `T` grows like
   `ln N`. More people only help if they also raise each person's contact rate (density ↑,
   same area) — then `β ∝ N/A` and `T ∝ (A/N) ln N` falls.
3. City parameters (`N = 3 000`, `β = 1.5 /h`, `c = 0.5`, `γ ≈ 1`): `T_50 ≈ ln(1 499)/0.75 ≈ 9.8 h`
   under homogeneous mixing. Community structure (80 % of contacts within one of 20
   communities) slows cross-community spread; the simulator measures the real value.
4. `γ` is not constant: as libraries grow, a fixed contact duration moves a fixed number of
   pamphlets, so `γ` for any *particular* pamphlet falls roughly as `(capacity per contact) /
   (difference between libraries)`. Late in the day the network is **contact-capacity
   limited**, not reachability limited.

## 3. When does adding people *hurt*? [proved + simulated]

In a single interference domain, airtime is fixed (~1 500 frames/s, `communication_bounds.md`).
Adding transmitters adds receivers (good: broadcast serves them for free) but adds no
capacity, and without rate control it destroys capacity (ALOHA collapse past ~100–200
transmitters). So in Environment 1 the answer to "does adding cooperative devices help?" is:
**yes for receivers, never for capacity, and catastrophically no without rate control.**

## 4. Interdiction: a few disruptions vs a large cooperative majority [proved]

**Bridge bound.** Partition the population into `k` regions whose only temporal connections are
`b` bridge couriers (people who move between them) or `b` chokepoints. Removing those `b` (seizing
devices, closing doors, jamming the chokepoints) leaves each pamphlet confined to its origin
region: the fraction of the population any pamphlet reaches is at most the size of its region,
≤ `max_j |V_j| / N` — regardless of `h`. With `k` equal regions, `≤ 1/k`.

The cost to the adversary is the **minimum temporal cut**, not the number of cooperative
devices. Robustness therefore comes from *how many independent bridges exist and how they move*:

* Fragile: few, predictable bridges (one exit, a handful of commuters) — interdiction cost `b`.
* Robust: many people moving independently between regions — the min cut is large, and since
  contacts are created by ordinary movement, cutting them means restricting movement itself.

Simulated instance (group D): two rooms, bridges silenced vs present
(`06_simulation/README.md`).

**Percolation view.** If each courier, before its copy is evicted or its battery dies, passes a
pamphlet on to `R₀ = β γ c · τ_life` others on average, global spread needs `R₀ > 1`; below 1 every
pamphlet dies out locally [heuristic, branching-process approximation; ignores geometry and
repeated contacts]. Storage eviction and short battery life lower `τ_life`; that is the link
between the storage policy and network-scale reachability.

## 5. What we can and cannot claim

Can claim (conditional): with rate control, broadcast dissemination in a dense hall reaches
most receivers in tens of minutes; across rooms, speed is set by how often people move between
rooms; across a city, by contact rate and contact capacity; and the cost of suppression equals
the size of the temporal min-cut.

Cannot claim: that a cooperative majority guarantees anything; that results on random-mixing
models transfer to real geography; any number for real cities (no mobility traces were used —
evidence requirement R6 in `08_verification/evidence_gaps.md`).
