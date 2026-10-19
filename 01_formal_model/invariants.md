# 01 · Safety invariants (must hold on every honest device, in every execution)

Each invariant lists its enforcement mechanism and the executable evidence in this tree.
"Executed" means a test in this repository exercises it; it does **not** mean it was verified
on hardware.

### I1 — No duplicate local objects
`∀i ∈ H, ∀p: copies(i, p) ≤ 1` on the **logical** view (the index).

*Mechanism.* Receive path rejects any frame whose `sid` is already committed or tombstoned
(`have()` hook) before allocating a slot; `Store.commit` refuses an `id` already indexed.

*Subtlety found by testing.* Physically, a power cut between copying a record during garbage
collection and erasing the old sector leaves **two** committed copies. `mount()` indexes the
newest and leaves the older one for the next GC, so the logical invariant holds immediately
after mount. The invariant is therefore stated on the index, not on raw flash.

*Evidence.* [executed] `test_store_dedup_and_capacity`, `test_power_cut_every_byte_with_gc`
(Python); C receive path: every frame of every vector re-delivered after completion is
rejected with `ZM_E_HAVE` (46/46).

### I2 — Content integrity
A record enters `S_i` only if `id(bytes) = declared id`.

*Mechanism.* Every chunk is checked against its manifest leaf on arrival; the manifest itself
hashes to `id`. `Store.commit` recomputes `content_id` and re-reads flash after programming
(read-back verify) before setting `COMMITTED`. `mount()` re-hashes every committed record.

*Evidence.* [executed] 2 000 000 mutated frames fed to the C receive path under
AddressSanitizer + UBSan: 55 010 completions, 0 completions whose bytes fail re-hashing or
validation. Python: forged-fragment and forged-manifest tests.

*Caveat.* Integrity is relative to `id`. Nothing proves that the *author* is who they claim, or
that the content is true (**a hash proves sameness, not legitimacy**).

### I3 — Bounded memory
No input sequence makes the protocol engine allocate beyond a compile-time bound.

*Mechanism.* No heap in the receive path; staging is `ZM_SLOTS × 4 180 B` static; every length
field is checked against a constant before use; no recursion; TLV walk bounded by `meta_len ≤
256`.

*Evidence.* [executed] `sizeof(zm_rx) = 17 428 B` for `ZM_SLOTS = 4`; ASan/UBSan clean under 2 M
fuzzed frames. Assumes correct radio-stack behaviour below the HCI boundary (not verified).

### I4 — Bounded storage
`|S_i| ≤ C_i` and `Σ|p| ≤ F_i`.

*Mechanism.* Admission check before commit; one erased spare sector is always maintained so GC
can run.

*Evidence.* [executed] capacity test; simulator `test_capacity_respected`.

### I5 — Participation consent
A device never originates content without `ORIG`, never forwards a third-party pamphlet without
`FWD`, and **never transmits any radio packet** when neither is granted.

*Mechanism.* The scheduler's candidate set is `{own}` under `ORIG` only, `S_i` under `FWD`;
with `π ⊆ {RX, STORE}` the radio is put in **passive** scanning (no `SCAN_REQ`) and no
advertising set is ever created. Whether the controller emits anything at all in passive scan
is a property of the radio stack: experiment **E-L** (spectrum check) must confirm it.

*Evidence.* [executed, simulator] `test_listen_mode_never_transmits`.

### I6 — Crash consistency
After a power cut at any instant, no committed record contains incomplete or unverified data,
and every record whose commit was acknowledged before the cut survives (except a delete that
was in flight, which may or may not take effect).

*Mechanism.* Monotone state field `FFFF→FFFE→FFFC→FFF8` (bits only cleared); deletion uses a
**separate** 2-byte flag. A record is trusted iff `state == FFF8` exactly and its payload re-hashes;
any other non-empty state marks the last write in the sector, which is killed and the sector
closed. Interrupted GC is detected at mount by the absence of an erased spare and is completed or
rolled back.

*Bug found and fixed by the exhaustive test.* The first design reused the state field for
deletion. A torn `FFF8→0000` produced an unrecognisable state, recovery treated it as the last
write and stopped parsing, and **every later record in the sector was lost**. The current design
separates the deletion flag; the test that found it now passes.

*Evidence.* [executed] `test_power_cut_at_every_byte` (6 seeds × ~400 cut points) and
`test_power_cut_every_byte_with_gc` (3 seeds × every programmed byte and every erase, with GC
forced by 1 KiB sectors). Model of NOR: torn byte = random subset of intended 1→0 transitions;
torn erase = prefix restored to `FF`. Real NOR can also leave weakly programmed cells that read
inconsistently; recovery re-programs torn fields to a stable value, but this residual risk needs
E7 on real flash.

### I7 — Persistent deduplication across budget resets
`EPOCH_RESET` changes only `B_i`. `S_i` and `D_i` are untouched, so items already held or
explicitly deleted are not re-admitted after a budget refill.

*Evidence.* By construction (separate state). `D_i` is bounded (ring of 512 sid64 = 4 KiB); an
item deleted more than 512 deletions ago can return. This is a stated limitation, not a bug.

### I8 — Offline operation
No data-plane transition references a network address, clock service, or remote authority.

*Evidence.* By inspection of `zmproto.py` and `zm_core.c`: no I/O except the radio frame and
flash hooks. Firmware updates (governance plane) are never required for data-plane operation.

### I9 — Per-fragment authenticity (added)
A chunk is stored in a staging slot only if it matches the leaf hash committed to by the
manifest. A forged chunk cannot occupy or poison a slot.

*Evidence.* [executed] `test_forged_fragment_rejected_and_does_not_poison`; C fuzz.

### I10 — Suppression requires verified bytes (added)
A device suppresses its own transmission of `p` only after overhearing a frame of `p` whose bytes
equal its own copy. Forged headers cannot silence honest holders.

*Evidence.* **Argued, not demonstrated.** In simulation group B (N = 500, 30 min, up to 20 %
forgers) naive and verified suppression both reached 100 % — the hall had spare capacity and a
forged header only deprioritises an item for one round. The attack matters when airtime is
scarce and the attacker targets specific items persistently; that case was not simulated.
