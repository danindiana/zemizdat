# 03 · ZEMIZDAT-WIRE-1.0 — byte-exact formats

All integers little-endian. Every layout below is implemented by
`reference_py/zmproto.py` and `reference_c/zm_core.c`; the two agree byte-for-byte on the vectors
in `reference_c/vectors.txt` [executed]. Hex dumps in this file were **produced by running the
reference code**, not written by hand.

## 1. Canonical Pamphlet Object (CPO) — what is stored and hashed

```
off  size  field        rule
0    1     version      0x01
1    1     encoding     0x00 = UTF-8 text (only value defined in v1; others → reject)
2    2     body_len     1 .. 4052 − meta_len
4    2     meta_len     0 .. 256
6    4     pow_nonce    free (reserved for optional anti-spam work; 0 by default)
10   2     reserved     must be 0x0000
12   M     meta TLVs    type u8 (≠0, strictly ascending), len u8, value; total = meta_len
12+M B     body         well-formed UTF-8 (RFC 3629), no terminator
```

Total canonical length `L = 12 + M + B ≤ 4064`. Compression is deliberately **not** in v1
(decompression bombs, extra code on the MCU, ~2× gain on short text is not worth it).

Defined TLVs: `0x01` parent id (32 B, reply/thread), `0x02` language tag (≤ 8 ASCII),
`0x03` coarse date (u16 days since 2026-01-01 — privacy-reducing, off by default), `0x10`
reserved for an optional author signature (v2). Unknown TLV types are kept and ignored, so v1
receivers accept objects carrying v2 metadata.

## 2. Content identifier

```
chunks   c_k = CPO[220k : 220(k+1)],  n = ceil(L/220) ≤ 19
leaf_k   = SHA-256(0x00 ‖ u8 k ‖ c_k)[0:8]
id       = SHA-256(0x01 ‖ u16 L ‖ leaf_0 ‖ … ‖ leaf_{n−1})
sid64    = id[0:8]
bucket   = id[0] >> 2          (0..63)
```

Covered by `id`: every CPO byte, the length, the chunk boundaries and order. **Not** covered:
anything in frame headers except through `sid64` and leaf matching.

*Note on FRAG byte 2.* Gemini's draft (and an early version of this one) carried a hop count
there. It was removed: a hop count of 0 tells every listener that the transmitter is the author,
and nothing in the v1 scheduler needs it.

## 3. Frames (payload of one manufacturer-specific AD structure)

Every frame starts with `magic = 0x5A`, then `vt = (version << 4) | type`. Receivers drop any frame
whose version nibble ≠ 1 **without parsing further** (forward compatibility = ignore, never
half-parse). Maximum frame size 236 B.

### 3.1 FRAG (type 0x2) — 16-byte header + 1..220 B chunk

```
0   1  magic      0x5A
1   1  vt         0x12
2   1  reserved   sent as 0, ignored by v1 receivers (see note in §2)
3   1  idx        0 .. total−1
4   1  total      1 .. 19
5   1  reserved   0
6   2  chunk_len  1 .. 220; must be 220 unless idx = total−1
8   8  sid64
16  n  chunk      CPO[220·idx : 220·idx + chunk_len]
```

### 3.2 MANIFEST (type 0x3) — 6 + 8·total bytes (22 .. 158 B)

```
0   1  magic      0x5A
1   1  vt         0x13
2   1  total      2 .. 19     (single-chunk objects have no manifest)
3   1  reserved   0
4   2  length     L, with 220(total−1) < L ≤ min(220·total, 4064)
6   8n leaves     leaf_0 .. leaf_{total−1}
```

The manifest carries no id: the receiver **computes** `id` from it, so a manifest cannot claim
someone else's id. A forged manifest is simply a different (garbage) object.

### 3.3 SDB — summary digest beacon (type 0x1) — 168 bytes, OPTIONAL in v1

```
0    1    magic       0x5A
1    1    vt          0x11
2    1    flags       bits 1..3 congestion level 0..7; others 0
3    1    reserved    0
4    4    salt        fresh random per beacon
8    128  digest[64]  u16: trunc16(SHA-256(salt ‖ sorted sid64s of bucket b))
136  32   wants[4]    sid64 of objects held *partially* (manifest seen, chunks missing); 0 = empty
```

Replaces Gemini's XOR folds, which are linear and leak the library (see
`01_formal_model/impossibility_results.md` §I). False "bucket equal" probability is 2⁻¹⁶ per
bucket per beacon and is not persistent because the salt changes.

## 4. Radio encapsulation

**BLE 5 (normative for v1):** non-connectable, non-scannable extended advertising,
**anonymous** (no AdvA) where the stack supports it, otherwise a non-resolvable private address
rotated at least every 60 s and whenever the advertised content set changes. Secondary PHY 2M,
primary 1M. Each frame is one AD structure:

```
len (1) = 3 + frame_len | type 0xFF | company id (2) | ZEMIZDAT frame (≤ 236)
```

An advertising event carries `L_chain = 3` PDUs (AUX_ADV_IND + 2 × AUX_CHAIN_IND, ≈ 720 B of
AdvData, i.e. 3 frames). The controller may split AD structures across PDUs; a lost PDU truncates
the rest of the chain, so the scheduler places the frames of one pamphlet in a sliding cyclic
window `[manifest, c_0, …, c_{n−1}]` starting at a random offset each event (see
`synchronization.md`).

*Company identifier.* `0xFFFF` is reserved by the Bluetooth SIG for internal/interop testing
and may be used for prototypes only. A deployed product needs an assigned company identifier or
a 128-bit-UUID Service Data AD (type 0x21, 16 extra bytes per AD structure, i.e. frame ≤ 220 B).
This is an administrative dependency, not an operational one.

**ESP-NOW (prototype alternative, ESP32 only):** the same frames concatenated in one vendor action
frame (v1 limit 250 B ⇒ 1 frame; ESP-NOW v2 limit 1 470 B ⇒ up to 6 frames) [spec: ESP-IDF
esp_now docs]. Broadcast ESP-NOW frames cannot be encrypted and carry the sender's MAC address,
which must be randomised by the application.

## 5. Worked example 1 — single-chunk pamphlet (self-certifying)

Body `"Truth survives without permission."` (34 B), no metadata.

CPO (46 B):
```
01 00 22 00 00 00 00 00 00 00 00 00 54 72 75 74
68 20 73 75 72 76 69 76 65 73 20 77 69 74 68 6f
75 74 20 70 65 72 6d 69 73 73 69 6f 6e 2e
```
`leaf_0 = ea31a0de1f5c847a`
`id = 562ab3b8fef3e63ec79fa5e3f1ae1d6c3fda315a7beaffb74ef8644f862a3141`, bucket 21.

On-air FRAG (62 B):
```
5a 12 00 00 01 00 2e 00 56 2a b3 b8 fe f3 e6 3e      header: v1 FRAG, rsv, idx 0/1, len 46, sid64
01 00 22 00 00 00 00 00 00 00 00 00 54 72 75 74      CPO …
68 20 73 75 72 76 69 76 65 73 20 77 69 74 68 6f
75 74 20 70 65 72 6d 69 73 73 69 6f 6e 2e
```

Receiver (Bob): (1) magic/version/type ok; (2) `total = 1`, `chunk_len = 46 = frame_len − 16`;
(3) `sid64` not in index, not tombstoned; (4) compute `leaf_0` over the chunk, then
`id = SHA-256(01 ‖ 2e 00 ‖ leaf_0)`; (5) `id[0:8] = 562ab3b8fef3e63e` equals the header's `sid64`
→ accept; (6) validate CPO (header, TLVs, UTF-8); (7) admission; (8) two-phase commit
(`storage.md`); (9) insert `(sid64, address)` into the sorted RAM index.

(Gemini's worked example printed `9f86d081…0a08` as the digest; that is SHA-256 of the ASCII
string `test`, not of its own preimage, whose real SHA-256 is `b9fdb3e2…71dad6` [executed].)

## 6. Worked example 2 — multi-chunk pamphlet with metadata

Body = the sentence `"Question: what would you say if nobody could delete it? "` × 6 (336 B), TLV
`02 02 65 6e` (language "en"). CPO = 352 B → 2 chunks → 3 frames: MANIFEST 22 B, FRAG 236 B,
FRAG 148 B. `id = 054b47cbf4d12101baf774246d08ba0f0d01e38cc3e304323a40b67caa67bedb`.

```
MANIFEST  5a 13 02 00 60 01 | 59 59 1b 68 96 e0 c5 d6 | 16 85 83 bc b1 e3 e8 03
          magic vt total rsv len=352 | leaf_0             | leaf_1
FRAG 0    5a 12 00 00 02 00 dc 00 05 4b 47 cb f4 d1 21 01 | 01 00 50 01 04 00 00 00 00 00 00 00 02 02 65 6e 51 75 …
FRAG 1    5a 12 00 01 02 00 84 00 05 4b 47 cb f4 d1 21 01 | (132 B: CPO[220:352])
```

A receiver that has the manifest verifies each FRAG independently (`leaf_k` match) and may
collect FRAG 0 and FRAG 1 from different senders, minutes apart.

## 7. Parser rules (normative)

1. Check total length against `FRAME_MAX` before reading any field.
2. Check magic, then version nibble, then type; unknown → drop silently.
3. Every length field is checked against both its constant bound and the actual frame length.
4. Non-final chunks must be exactly 220 B (prevents ambiguous reassembly).
5. No field is used before it is validated; no allocation depends on a received length.
6. A completed object is re-validated as a CPO before admission.
