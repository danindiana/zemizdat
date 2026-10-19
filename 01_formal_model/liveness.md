# 01 · Liveness (conditional) — what must be assumed, and why each assumption is necessary

Safety (I1–I10) holds unconditionally. Liveness cannot: every statement below is conditional
and each condition comes with a counterexample showing it cannot simply be dropped.

## Theorem L1 — conditional eventual dissemination [proved]

Let `A ⊆ H` be honest devices with `{RX, STORE, FWD} ⊆ π_v`, capacity `C_v ≥ |P_A|` (no eviction
is ever needed), and no user tombstone on any item of `P_A`, where `P_A` is the set of pamphlets
held by at least one member of `A` at some time. Assume:

* **(C1) recurrent cut contact.** For every non-trivial partition `(X, A∖X)`, reception-graph
  contacts from `X` to `A∖X` with duration `≥ τ_min` occur infinitely often.
* **(C2) uniformly positive per-contact success.** There is `ε > 0` such that, conditioned on the
  whole history up to the start of any such contact `(u → w)` and for any item `p ∈ S_u ∖ S_w`,
  the probability that `w` completes `p` during the contact is `≥ ε`.

Then with probability 1 every `v ∈ A` eventually holds all of `P_A`.

*Proof.* Let `Φ(t) = Σ_{v∈A} |P_A ∖ S_v(t)|`, a non-negative integer. No eviction and no
deletion means `Φ` is non-increasing. If `Φ(t) > 0`, pick `p` and its holder set `X_p(t) ∩ A`,
non-empty by definition of `P_A` and not all of `A`. By (C1) cut-crossing contacts recur; by (C2)
each succeeds with conditional probability `≥ ε`, so the probability that `k` consecutive ones
all fail is `≤ (1−ε)^k → 0`. Hence `Φ` decreases in finite time almost surely; being a
non-negative integer, it reaches 0 almost surely. ∎

*Rate.* If cut-crossing contacts arrive at rate `≥ β_min`, each decrement takes expected time
`≤ 1/(β_min ε)`, so `E[T_complete] ≤ Φ(0)/(β_min ε)`. This bound is crude (it serialises
everything) and is not used for engineering numbers; the simulator is.

(This replaces Gemini's version, which invoked the second Borel–Cantelli lemma without the
independence it requires, and asserted "with probability 1, lim Pr[…] = 1", which conflates
almost-sure and in-probability convergence.)

## What (C2) unpacks into, for ZEMIZDAT-PROTO-1.0

`ε > 0` requires all of the following. Each line names the counterexample that breaks liveness
when the condition is removed.

| Condition | Mechanism that provides it | Counterexample if absent |
|---|---|---|
| contact lasts `≥ τ_min ≈ ⌈F/L⌉` events at the current rate | contacts long enough; burst rate in sparse encounters | a pedestrian passing at 1.5 m/s through a 10 m range for 6 s at 0.1 events/s |
| every held item has scheduler weight `≥ w_min > 0` | `eps` floor in the weighting; age weighting grows without bound up to `age_cap` | a deterministic scheduler always sending the "most demanded" item starves the rest |
| transmission continues when no *visible* neighbour needs anything | `listen_floor > 0` | LISTEN devices send no beacons, so a digest-only scheduler sees "no demand" and falls silent: the listener starves forever |
| channel load bounded below collapse | density-adaptive rate control (`G ≈ 0.25` primary, `0.15` secondary) | unregulated 10 Hz advertising: at 1 000 transmitters per domain the per-event success is `≈ 0.002` [estimate, `airtime_model.py`]; the simulator's fixed-rate BCAST reaches 39 % in 60 min at N = 1 000 and 0 % at N = 3 000 [simulated] |
| a staging slot eventually frees | slot timeout (120 s); "refuse rather than thrash" | `K_slot` stale partials whose missing chunks never return block all new objects |
| adversarial occupation is not continuous | none possible in software | continuous broadband energy on 2.4 GHz (Theorem H) |
| storage not exhausted by junk | admission quota **and** `C ≥ |P_A|` | naive admission with a flooder in range: `C` fills with junk, honest items are dropped (group E) |

## Theorem L2 — liveness is impossible without (C1) [proved]

If some partition `(X, A∖X)` has only finitely many cut contacts, an item held only in `X` after
the last one never reaches `A∖X`. The barbell experiment (group D) is the executable instance:
with the bridge couriers silenced, each half stays at roughly its own share of the collection.

## Theorem L3 — liveness under finite capacity is not monotone [proved by example]

With `C_v < |P_A|` and any eviction rule, `S_v(t)` need not converge. Two devices with `C = 1`
holding `p` and `q` and "replace on arrival" eviction swap forever. So under finite capacity the
right objective is `O_α` / `O_union` (collective retention), never `O_all`, and the correct
liveness statement is about **coverage** of each item over time, which the simulator measures.

## Liveness for LISTEN devices

A LISTEN device cannot request anything (it never transmits), so its liveness depends entirely on
(C2) holding for transmissions *it happens to overhear*. Sufficient: at least one FWD holder of
`p` within reception range infinitely often, with `listen_floor > 0`. Necessary: some
transmitting holder in range infinitely often — if every neighbour only answers explicit requests
(pairwise protocols), the LISTEN device acquires nothing (Theorem F). The pairwise baselines in
the simulator confirm this: listener completeness is exactly 0 [simulated, group A].
