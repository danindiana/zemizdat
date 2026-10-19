# 01 · System definition

Status labels used throughout this tree: **[proved]** (argument given here), **[executed]**
(checked by code in this repository), **[simulated]** (output of `06_simulation`), **[spec]**
(manufacturer or standards document), **[estimate]** (back-of-envelope with stated assumptions),
**[assumption]** (a modelling choice that an experiment must confirm or replace).

## 1. Entities

| Symbol | Meaning |
|---|---|
| `V = {v_1..v_N}` | devices present during an observation interval `[0, T]` |
| `P = {p_1..p_M}` | distinct pamphlets contributed during that interval (the *event collection*) |
| `id(p)` | 32-byte content identifier (§3) |
| `sid(p)` | first 8 bytes of `id(p)`; used on the air and in the index |
| `S_i(t) ⊆ P` | the **verified, committed** library of device `i` at time `t` |
| `π_i ⊆ {RX, STORE, ORIG, FWD}` | user-granted permissions (see `03_protocol/state_machine.md`) |
| `C_i` | locally configured capacity in records; `F_i` the byte capacity |
| `B_i(t)` | remaining budgets: radio-on time, transmit events, admissions, flash writes |
| `H ⊆ V` | honest devices (run unmodified firmware, follow `π`) |

A device's full local state is

```
σ_i = ⟨ S_i, Π_i, A_i, π_i, B_i, Q_i, D_i ⟩
  S_i  committed records on flash (content + 48-byte header)
  Π_i  staging slots: ≤ K_slot partially received objects (manifest + verified chunks)
  A_i  overhearing table: last time each held item was heard on air (for scheduling)
  Q_i  scheduler state (event-rate estimate, current rate λ_i, salt for beacons)
  D_i  user tombstones: sid64s the owner deleted and does not want back
```

`S_i` and `D_i` are durable; `Π_i`, `A_i`, `Q_i` are volatile and may be lost at any power cut
without violating any safety property.

## 2. Communication model

Time-varying **reception graph** `G_rx(t) = (V, E_rx(t))`: `(u, v) ∈ E_rx(t)` when a frame sent by
`u` at `t` would be decoded by `v` in the absence of other transmissions. **Interference
relation** `E_int(t) ⊇ E_rx(t)`: `u` can destroy a frame arriving at `v`. In crowds the
interference range exceeds reception range (bodies attenuate the wanted signal more than
they bound the interferer's), so many disjoint reception neighbourhoods share one
interference domain. This asymmetry — absent from Gemini's model — is what makes spatial
reuse inside one hall small **[assumption, to be measured in E5]**.

A frame `f` sent by `u` at `t₀` with airtime `τ` is decoded by `v` iff
1. `RX ∈ π_v` and `v`'s radio is listening on that channel throughout `[t₀, t₀+τ]` (duty
   cycle `δ_v`);
2. `(u, v) ∈ E_rx` throughout;
3. no `w` with `(w, v) ∈ E_int` transmits on the same channel overlapping the frame (ALOHA
   collision model; capture is ignored, which is pessimistic);
4. link CRC passes (residual loss `p_loss`).

The BLE-5 extended-advertising specialisation (primary pointer on channels 37/38/39 plus an
AUX chain on one of 37 secondary channels) is in `04_mathematical_analysis/communication_bounds.md`.

**No assumption** is made about clocks being synchronised, identities being stable, or any
pairwise link being bidirectional.

## 3. Content identity (deterministic, content-derived)

Canonical bytes `c = canonical(p)` (12-byte header ‖ ordered TLV metadata ‖ UTF-8 body,
`|c| ≤ 4064`). Split `c` into 220-byte chunks `c_0..c_{n-1}`, `n ≤ 19`.

```
leaf_k = SHA-256(0x00 ‖ u8 k ‖ c_k)[0:8]
id(p)  = SHA-256(0x01 ‖ u16le |c| ‖ leaf_0 ‖ … ‖ leaf_{n-1})
```

This is a depth-1 hash list instead of `SHA-256(c)`. It costs one extra *manifest* frame per
multi-chunk pamphlet (≈17 % airtime for a 1 KiB pamphlet: 6 frames instead of 5) and buys:
per-fragment verification on arrival, safe accumulation of fragments from different senders
and different encounters, and immunity of reassembly to a single forged fragment. A
single-chunk object (≤ 208-byte body) needs no manifest: its one fragment is self-certifying.
Identity is **byte identity**: two Unicode-equivalent texts with different byte sequences are
two pamphlets (receivers check UTF-8 well-formedness but do not normalise — NFC tables do not
fit the target MCUs).

Three identities are kept separate:

| | what it names | where it lives | covered by `id`? |
|---|---|---|---|
| content identity | the exact bytes | `id`, `sid` | yes (definition) |
| transport identity | which frame of which object | `sid`, `idx`, `total` in the frame header | `sid` binds to `id`; `idx/total` bound through the manifest leaves. No hop count: it would mark the author (hop 0) |
| author identity | who claims authorship | nothing in v1 (TLV type 0x10 reserved) | — |

## 4. Valid operations (atomic state transitions at device `i`)

| Operation | Guard | Effect |
|---|---|---|
| `AUTHOR(c)` | `ORIG ∈ π ∧ STORE ∈ π ∧ valid(c) ∧ |S|<C` | commit `c` (two-phase, §storage) |
| `RX_MANIFEST(m)` | `RX ∈ π`, `sid(id(m)) ∉ S ∪ D`, free slot or stale slot | open slot with `m` |
| `RX_FRAG(f)` | `RX ∈ π`, slot for `f.sid` with manifest, `leaf(f) = m.leaf[f.idx]` | store chunk in slot |
| `COMPLETE(slot)` | all chunks present, `valid(c)` | `ADMIT(c)` |
| `ADMIT(c)` | `STORE ∈ π`, admission policy (§budgets) | commit `c`, else drop |
| `EMIT(p, w)` | `p ∈ S`, (`p` own ∧ `ORIG`) ∨ (`p` third-party ∧ `FWD`), tx budget | send an event carrying window `w` of `p`'s frames |
| `EMIT_SDB` | `(ORIG ∨ FWD) ∈ π`, beacon option enabled | broadcast salted digests |
| `OVERHEAR(f)` | `RX ∈ π`, `f.sid ∈ S`, bytes equal own copy | `A[p] ← now` (suppression signal) |
| `DELETE(p)` | user action | tombstone record, `D ← D ∪ {sid(p)}` |
| `EPOCH_RESET` | timer | refill budgets; **does not touch `S`, `D`** |

## 5. Objective functions (not interchangeable)

Let `R = {v ∈ H : RX, STORE ∈ π_v}` (willing honest receivers).

| Objective | Definition | Achievable when |
|---|---|---|
| `O_all` | `∀v∈R: S_v(T) = P` | storage `≥ M·L̄` on every device **and** temporal connectivity **and** enough airtime. Fails at the first bound that binds. |
| `O_α` | `∀p: |{v∈R : p∈S_v(T)}| ≥ α|R|` | the realistic engineering target |
| `O_α^{q}` | `O_α` for a `q`-quantile of pamphlets (e.g. 90 % of pamphlets reach 80 % of receivers) | what the simulator reports (`frac_reach80`) |
| `O_will` | `∀p ∃v∈R∖{author(p)}: p∈S_v(T)` | one successful contact per author |
| `O_union` | `⋃_{v∈R} S_v(T) = P` | `O_will` suffices |
| `O_surv` | `∀p ∃v∈H: p∈S_v(T)` | trivially at `t=0`; under author seizure needs `O_will` first |
| `O_recon` | every participant can rebuild `P` after a later synchronisation | needs `O_union` *and* a later connected period with enough storage |

Implications **[proved]**: `O_all ⇒ O_α` for every α; `O_α ⇒ O_will` iff `α|R| ≥ 2` (one
holder may be the author); `O_will ⇒ O_union` (the extra holder is in `R`); `O_union ⇒ O_surv`
(`R ⊆ H`). None of the converses hold: a single courier holding everything satisfies
`O_union` with `α = 1/|R|`.

What a device can **know**: none of these predicates is locally decidable without an
external definition of `P` (Theorem G in `impossibility_results.md`). The UI must therefore
show "pamphlets held / heard of" — never "complete".

## 6. Resource limits per device class

| | RA4M1 (UNO R4 MCU) | ESP32-S3 | nRF52840 |
|---|---|---|---|
| SRAM | 32 KB [spec] | 512 KB [spec] | 256 KB [spec] |
| on-chip flash | 256 KB + 8 KB data [spec] | 8 MB on ESP32-S3-MINI-1-N8 (part number) [spec: module name] | 1 MB [spec] |
| receive state, 4 slots, measured `sizeof(zm_rx)` | 17 428 B [executed] | 17 428 B | 17 428 B |
| RAM index at 12 B/entry for 3 000 entries | 36 KB — does not fit | fits | fits |
| radio | none (via ESP32-S3 over a level-translated UART) | BLE 5 + Wi-Fi/ESP-NOW | BLE 5 |

## 7. Threat model (summary; full version in `07_adversarial_review/threat_model.md`)

Adversaries may: run modified firmware; transmit arbitrary well-formed or malformed frames;
generate unlimited valid objects; rotate radio addresses freely (Sybil); forge headers; replay
anything; listen to everything in range; stay silent (black-hole); occupy the channel
(equivalent to jamming); physically seize devices; and compromise a minority of firmware
signing keys. They cannot: break SHA-256 or Ed25519; find 64-bit second preimages; or
alter firmware on an honest device without passing its update policy.

## 8. Engineering hypotheses vs established results

| Claim | Status |
|---|---|
| Broadcast reaches many receivers per transmission | established (physics) |
| BLE-5 controllers on ESP32-S3 and nRF52840 deliver chained extended advertising (≤ 1650 B) to the host as one report | **hypothesis** — Nordic forum reports and spec say yes; E1 must confirm on both stacks |
| Interference range ≫ reception range in a dense crowd | **hypothesis** — E5 |
| A host can process ≥ 200 advertising reports/s | **hypothesis** — E5 |
| Per-connection application goodput ≈ 40 kB/s and ≈ 1.5 MB/s aggregate per domain | **hypothesis** used only for the pairwise baselines — E5 |
| Scan duty of 30 % is affordable on a 2 000 mAh cell | nRF52840: yes by datasheet arithmetic; ESP32-S3: **unknown** until E6 |
