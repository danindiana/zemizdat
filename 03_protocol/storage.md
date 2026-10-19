# 03 · Storage: record layout, index, atomic commit, GC, recovery

Executable reference: `reference_py/zmproto.py` classes `NorFlash` and `Store`. Tests:
`test_zmproto.py::test_power_cut_at_every_byte`, `::test_power_cut_every_byte_with_gc`
[executed]. Real-flash validation is experiment E7.

## 1. Media assumptions

NOR flash (internal or SPI, e.g. 8 MB): programming clears bits (1→0) only; erase sets a 4 KiB
sector to `FF`. A power cut during programming may leave any subset of the intended bit
clearings in the interrupted byte; during erase, part of the sector. These are the assumptions
encoded in `NorFlash`. Weakly programmed cells that read inconsistently are **not** modelled;
recovery re-programs torn fields to a stable value to mitigate, and E7 must check.

## 2. Layout

```
sector (4 096 B)
  0   u32 magic 0x5A4D5331 ("ZMS1")
  4   u32 sequence (monotone across sectors)
  8   u16 state  FFFF open | FFFE closed
  10  u16 reserved
  12  records…

record
  0   u16 state  FFFF empty → FFFE writing → FFFC written → FFF8 committed   (0000 = killed)
  2   u16 len    CPO length
  4   32  id
  36  u8  reserved
  37  u8  flags  (own, pinned, epoch tag in bits 2..7)
  38  8   reserved (FF)
  46  u16 dead   FFFF live | anything else = deleted
  48  len CPO bytes
```

Separate `dead` flag: deleting never touches `state`, so a torn delete can never make a
committed record's length untrustworthy. (The first design reused `state`; the exhaustive
power-cut test showed a torn delete could make recovery stop parsing and lose every later
record in the sector. Fixed.)

## 3. Commit (two-phase, append-only)

```
1  program header with state=FFFE (writing), len, id, flags
2  program CPO bytes
3  program state=FFFC (written)
4  read back CPO, recompute id; mismatch → state=0000, close sector, return failure
5  program state=FFF8 (committed)          ← linearisation point
6  index insert
```

## 4. Mount / recovery

```
for each sector with valid magic, in sequence order:
    walk records:
        all-FF header            → end of data in this sector
        state = FFF8, len sane   → if dead ≠ FFFF: finish the delete (program 0000), skip
                                   else re-hash; ok → index (newest copy wins); bad → kill, stop
        anything else            → torn last write: kill (state=0000), close sector, stop
if no erased sector exists:       interrupted GC
    head sector intact            → finish GC
    head sector torn              → re-point index to the older copies, erase head
```

Recovery is `O(flash size)` with a re-hash per record (≈ 3 000 SHA-256 of 1 KiB: well under a
second with the SoC engine [estimate]).

## 5. Garbage collection

One erased spare sector is an invariant. Opening the spare as the new head when it is the last
free sector triggers GC: live records of the oldest closed sector are copied into the head, then
that sector is erased and becomes the spare. A crash between copy and erase leaves duplicates;
the newest copy wins at mount (I1 holds on the index). Capacity must satisfy
`C · max_record ≤ (sectors − 2) · usable_sector` so the victim's live data always fits.

## 6. Index

RAM: sorted array of `(sid64 u64, address u32)`, 12 B per record; binary search for `have()`;
insertion by memmove (3 000 entries: 36 KB moved worst case, negligible). Rebuilt at mount.
On the RA4M1 (32 KB SRAM) a 3 000-entry RAM index does not fit: use a flash-resident sorted
index with a 256-entry RAM fence table, or (recommended) do not use the RA4M1 as the protocol
processor at all.

## 7. Endurance (not a binding limit)

8 MB = 2 048 sectors; at 100 000 erase cycles per sector [typical SPI NOR datasheet figure;
confirm for the chosen part] that is 2.0 × 10⁸ sector erases. A sector holds ≈ 3.8 one-KiB
records; with GC write amplification ≤ 3 at ≤ 75 % fill, the flash absorbs ≈ 1.4 × 10⁵ new
records per day for five years [estimate]. Gemini's "≤ 5 000 objects/day for a 5-year life" is
about 30× too pessimistic and was not derived. The real per-day limit is the admission quota
(§9 of the spec), which exists for flood defence, not endurance.

## 8. Deduplication across resets

Budget resets touch counters only. The index and the user tombstone ring (512 × sid64, 4 KiB,
stored in its own sector pair with the same log discipline) persist, so deleted items are not
re-admitted until they age out of the ring (I7).
