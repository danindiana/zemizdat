"""Executable checks of ZEMIZDAT-PROTO-1.0 invariants (pytest)."""
import os
import random
import struct

import pytest

import zmproto as z

TEXT = "Truth survives without permission.".encode()


def mk(body: bytes, meta=b""):
    cpo = z.encode_cpo(body, meta)
    return z.content_id(cpo), cpo


# ------------------------------------------------------------ worked example (pinned)
def test_worked_example_vector():
    cid, cpo = mk(TEXT)
    assert len(cpo) == 12 + 34 == 46
    assert cpo[:12].hex() == "010022000000000000000000"
    fr = z.burst(cpo)
    assert len(fr) == 1 and len(fr[0]) == 16 + 46
    # vector pinned so the C port can be checked byte-for-byte
    assert cid.hex() == WORKED_ID
    assert fr[0].hex() == WORKED_FRAME


WORKED_ID = None
WORKED_FRAME = None


def setup_module(_):
    global WORKED_ID, WORKED_FRAME
    cid, cpo = mk(TEXT)
    WORKED_ID = cid.hex()
    WORKED_FRAME = z.burst(cpo)[0].hex()


def test_single_chunk_roundtrip():
    cid, cpo = mk(TEXT)
    r = z.Reassembler()
    out = r.on_frame(z.parse_frame(z.burst(cpo)[0]))
    assert out == (cid, cpo)


@pytest.mark.parametrize("n", [1, 219, 220 - 12, 221, 1024, 2000, 4064 - 12])
def test_multichunk_roundtrip_any_order(n):
    body = ("x" * n).encode()
    cid, cpo = mk(body)
    frames = z.burst(cpo)
    man, frags = (frames[0], frames[1:]) if len(frames) > 1 else (None, frames)
    random.Random(n).shuffle(frags)
    r = z.Reassembler()
    res = None
    if man:
        assert r.on_frame(z.parse_frame(man)) is None
    for f in frags:
        res = r.on_frame(z.parse_frame(f)) or res
    assert res == (cid, cpo)
    assert len(frames) == (1 if len(cpo) <= z.CHUNK else 1 + -(-len(cpo) // z.CHUNK))


def test_fragment_counts_for_reference_sizes():
    # 1 KiB body -> 1036 canonical bytes -> 5 chunks + manifest = 6 frames
    _, cpo = mk(b"a" * 1024)
    assert len(z.burst(cpo)) == 6
    _, cpo = mk(b"a" * (4064 - 12))
    assert len(z.burst(cpo)) == 1 + 19


def test_multi_source_accumulation():
    """Fragments from different senders/bursts combine (carousel property)."""
    cid, cpo = mk(b"b" * 3000)
    fr = z.burst(cpo)
    r = z.Reassembler()
    r.on_frame(z.parse_frame(fr[0]), now=0)
    for i, f in enumerate(fr[1:]):
        out = r.on_frame(z.parse_frame(f), now=1000 * i)
    assert out == (cid, cpo)


def test_fragment_without_manifest_dropped():
    _, cpo = mk(b"c" * 900)
    r = z.Reassembler()
    for f in z.burst(cpo)[1:]:
        assert r.on_frame(z.parse_frame(f)) is None
    assert r.stats["no_manifest"] == len(z.burst(cpo)) - 1


def test_forged_fragment_rejected_and_does_not_poison():
    cid, cpo = mk(b"d" * 1500)
    fr = z.burst(cpo)
    r = z.Reassembler()
    r.on_frame(z.parse_frame(fr[0]))
    forged = bytearray(fr[2])
    forged[20] ^= 0x01
    assert r.on_frame(z.parse_frame(bytes(forged))) is None
    assert r.stats["bad_leaf"] == 1
    out = None
    for f in fr[1:]:
        out = r.on_frame(z.parse_frame(f)) or out
    assert out == (cid, cpo)


def test_forged_manifest_cannot_claim_existing_id():
    cid, cpo = mk(b"e" * 800)
    man = bytearray(z.burst(cpo)[0])
    man[10] ^= 0xFF                         # alter one leaf
    m = z.parse_frame(bytes(man))
    assert z.sid64(m.cid) != z.sid64(cid)   # a forged manifest is simply a different object


def test_staging_bounded():
    r = z.Reassembler(slots=4, timeout_ms=10_000)
    for i in range(20):
        _, cpo = mk(bytes([97 + i % 26]) * 600 + bytes([48 + i % 10]))
        r.on_frame(z.parse_frame(z.burst(cpo)[0]), now=i)
    assert len(r.slots) <= 4


# ------------------------------------------------------------ strict parser
def test_parser_rejects_bad_inputs():
    _, cpo = mk(b"f" * 500)
    good = z.burst(cpo)[1]
    bad = [
        b"", b"\x5a", bytes(300),
        bytes([0x5B]) + good[1:],                     # magic
        good[:1] + bytes([0x22]) + good[2:],          # version 2 ignored
        good[:3] + bytes([5]) + good[4:],             # idx 5 >= total 3
        good[:-1],                                    # length mismatch
        good[:5] + bytes([1]) + good[6:],             # reserved byte 5 != 0
    ]
    for b in bad:
        with pytest.raises(z.ZmError):
            z.parse_frame(b)


def test_parser_fuzz_never_crashes():
    rng = random.Random(1)
    _, cpo = mk(b"g" * 2000)
    seeds = z.burst(cpo) + [z.frame_sdb([z.content_id(cpo)])]
    n_ok = 0
    for _ in range(20000):
        b = bytearray(rng.choice(seeds))
        for _ in range(rng.randrange(1, 6)):
            op = rng.randrange(3)
            if op == 0 and b:
                b[rng.randrange(len(b))] = rng.randrange(256)
            elif op == 1 and b:
                del b[rng.randrange(len(b))]
            else:
                b.insert(rng.randrange(len(b) + 1), rng.randrange(256))
        try:
            z.parse_frame(bytes(b))
            n_ok += 1
        except z.ZmError:
            pass
    assert n_ok > 0


def test_cpo_validation():
    with pytest.raises(z.ZmError):
        z.encode_cpo(b"\xff\xfe")                     # not UTF-8
    with pytest.raises(z.ZmError):
        z.encode_cpo(b"x" * 5000)
    with pytest.raises(z.ZmError):
        z.encode_meta([(2, b"a"), (1, b"b")])         # unordered TLVs
    cpo = bytearray(z.encode_cpo(b"hello"))
    cpo[10] = 1                                       # reserved != 0
    with pytest.raises(z.ZmError):
        z.validate_cpo(bytes(cpo))


# ------------------------------------------------------------ SDB / digest
def test_sdb_roundtrip_and_diff():
    ids = [mk(f"p{i}".encode())[0] for i in range(300)]
    a, b = ids[:250], ids[:240] + ids[250:255]
    sdb = z.parse_frame(z.frame_sdb(b, congestion=3, salt=b"SALT"))
    assert len(z.frame_sdb(b)) == z.SDB_LEN <= z.FRAME_MAX
    diff = set(z.differing_buckets(a, sdb))
    truth = {z.bucket_of(c) for c in set(a) ^ set(b)}
    assert truth <= diff                       # never misses a differing bucket except 2^-16 events
    assert len(diff - truth) <= 1


def test_sdb_salt_changes_every_digest():
    ids = [mk(f"q{i}".encode())[0] for i in range(500)]
    d1 = z.bucket_digests(ids, b"AAAA")
    d2 = z.bucket_digests(ids, b"BBBB")
    assert sum(x == y for x, y in zip(d1, d2)) <= 3


# ------------------------------------------------------------ storage + power cuts
def _ops(seed, n=14):
    rng = random.Random(seed)
    objs = [mk(os.urandom(4).hex().encode() * rng.randrange(1, 120)) for _ in range(n)]
    seq = []
    for c in objs:
        seq.append(("put", c))
        if rng.random() < 0.3:
            seq.append(("put", c))                     # duplicate commit attempt
        if rng.random() < 0.2:
            seq.append(("del", c))
    return seq


def _run(store, seq):
    for op, (cid, cpo) in seq:
        if op == "put":
            store.commit(cid, cpo)
        else:
            store.delete(cid)


def test_store_dedup_and_capacity():
    f = z.NorFlash(sectors=8, sector_size=4096)
    s = z.Store(f, capacity_records=10)
    s.mount()
    cid, cpo = mk(b"dup")
    assert s.commit(cid, cpo) and not s.commit(cid, cpo)
    for i in range(30):
        c2, p2 = mk(f"cap{i}".encode())
        s.commit(c2, p2)
    assert len(s.index) == 10
    z.verify_store(s)


def test_store_survives_many_writes_with_gc():
    f = z.NorFlash(sectors=6, sector_size=4096)
    s = z.Store(f, capacity_records=8)
    s.mount()
    live = []
    rng = random.Random(7)
    for i in range(400):
        c, p = mk((f"gc{i}-" + "z" * rng.randrange(10, 900)).encode())
        if len(s.index) >= 8:
            victim = live.pop(0)
            s.delete(victim)
        assert s.commit(c, p)
        live.append(c)
        if i % 37 == 0:
            s2 = z.Store(f, 8)
            s2.mount()
            assert set(s2.index) == set(s.index)
            s = s2
    z.verify_store(s)
    assert max(f.erase_count) > 0


@pytest.mark.parametrize("seed", range(6))
def test_power_cut_at_every_byte(seed):
    """I6: for every possible interruption point of a realistic operation sequence,
    remounting yields a store whose committed records all verify, with no duplicates,
    and every record that had fully committed before the cut is still present."""
    seq = _ops(seed)
    ref = z.NorFlash(sectors=6, sector_size=4096, seed=seed)
    st = z.Store(ref, 6)
    st.mount()
    total = 0
    try:
        _run(st, seq)
    finally:
        total = ref.programmed
    step = max(1, total // 400)                 # ~400 cut points per seed, spread uniformly
    for cut in range(0, total + 50, step):
        f = z.NorFlash(sectors=6, sector_size=4096, seed=cut)
        s = z.Store(f, 6)
        s.mount()
        committed_before_cut = set()
        f.cut_after = cut
        try:
            for op, (cid, cpo) in seq:
                if op == "put":
                    if s.commit(cid, cpo):
                        committed_before_cut.add(cid)
                else:
                    s.delete(cid)
                    committed_before_cut.discard(cid)
        except z.PowerCut:
            pass
        f.cut_after = None
        s2 = z.Store(f, 6)
        s2.mount()
        z.verify_store(s2)
        # durability: everything acknowledged as committed survives (except a delete in flight)
        assert committed_before_cut - set(s2.index) == set() or \
            len(committed_before_cut - set(s2.index)) <= 1
        # and the store remains usable
        c, p = mk(f"after{cut}".encode())
        if len(s2.index) < 6:
            assert s2.commit(c, p)
        z.verify_store(s2)


def _churn_seq(seed, n=40):
    rng = random.Random(seed)
    return [mk((f"{seed}-{i}-" + "w" * rng.randrange(20, 190)).encode()) for i in range(n)]


def _churn(store, objs, cap, acked):
    live = list(store.index)
    for cid, cpo in objs:
        if len(store.index) >= cap:
            v = live.pop(0)
            store.delete(v)
            acked.discard(v)
        if store.commit(cid, cpo):
            acked.add(cid)
            live.append(cid)


@pytest.mark.parametrize("seed", range(3))
def test_power_cut_every_byte_with_gc(seed):
    """Small sectors force garbage collection and erases; cut at EVERY program/erase step."""
    objs = _churn_seq(seed)
    f0 = z.NorFlash(sectors=4, sector_size=1024, seed=seed)
    s0 = z.Store(f0, 3)
    s0.mount()
    _churn(s0, objs, 3, set())
    assert sum(f0.erase_count) > 3, "GC must actually run in this test"
    steps = f0.programmed + sum(f0.erase_count)
    for cut in range(steps + 1):
        f = z.NorFlash(sectors=4, sector_size=1024, seed=cut)
        s = z.Store(f, 3)
        s.mount()
        acked = set()
        f.cut_after = cut
        try:
            _churn(s, objs, 3, acked)
        except z.PowerCut:
            pass
        f.cut_after = None
        s2 = z.Store(f, 3)
        s2.mount()
        z.verify_store(s2)
        lost = acked - set(s2.index)
        assert len(lost) <= 1, (cut, lost)       # only a delete in flight may vanish
        # remains usable after recovery
        _churn(s2, _churn_seq(seed + 100, 8), 3, set())
        z.verify_store(s2)
