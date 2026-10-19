"""ZEMIZDAT-PROTO-1.0 executable reference (Python).

This module is the normative executable companion to 03_protocol/ZEMIZDAT_PROTO_1.0.md.
Where prose and code disagree, the disagreement is a bug to be filed; the test
suite (test_zmproto.py) pins the behaviour.

Contents
  * canonical pamphlet object (CPO) encode / validate
  * content identity: hash-list id over fixed 220-byte chunks
  * over-the-air frames: SDB (0x11), FRAG (0x12), MANIFEST (0x13)
  * salted, non-linear bucket digest used by the SDB
  * receiver reassembly with per-fragment verification
  * NOR-flash model with power-cut injection + log-structured record store

Everything here is deliberately allocation-bounded in the sense that the
firmware port can use fixed arrays: every length is checked against a
compile-time constant before it is used.
"""
from __future__ import annotations

import hashlib
import os
import random
import struct
from dataclasses import dataclass, field

# ---------------------------------------------------------------- constants
MAGIC = 0x5A
PROTO_VER = 1
T_SDB, T_FRAG, T_MANIFEST = 0x1, 0x2, 0x3

FRAME_MAX = 236            # bytes of ZEMIZDAT frame inside one BLE AUX_ADV_IND / ESP-NOW v1 frame
FRAG_HDR = 16
CHUNK = FRAME_MAX - FRAG_HDR   # 220 payload bytes per fragment
CPO_HDR = 12
META_MAX = 256
CPO_MAX = 4064             # canonical bytes; ceil(4064/220) = 19 chunks
MAX_CHUNKS = 19
LEAF = 8                   # truncated per-chunk hash length
MANIFEST_HDR = 6
N_BUCKETS = 64
N_WANTS = 4
SDB_LEN = 8 + 2 * N_BUCKETS + 8 * N_WANTS   # 168

ENC_UTF8 = 0x00            # only encoding defined in v1


class ZmError(ValueError):
    """Any validation failure. Callers drop the input; nothing is partially applied."""


# ---------------------------------------------------------------- canonical object
def utf8_valid(b: bytes) -> bool:
    try:
        b.decode("utf-8", errors="strict")
        return True
    except UnicodeDecodeError:
        return False


def encode_meta(tlvs: list[tuple[int, bytes]]) -> bytes:
    """Meta TLVs: type u8, len u8, value. Must be strictly ascending by type."""
    out = bytearray()
    last = -1
    for t, v in tlvs:
        if not (0 < t < 256) or t <= last or len(v) > 255:
            raise ZmError("bad TLV ordering/size")
        out += bytes([t, len(v)]) + v
        last = t
    if len(out) > META_MAX:
        raise ZmError("meta too long")
    return bytes(out)


def encode_cpo(body: bytes, meta: bytes = b"", pow_nonce: int = 0) -> bytes:
    """Build canonical bytes. The author is responsible for any Unicode normalisation;
    receivers only enforce well-formed UTF-8 (NFC tables are too large for the MCU)."""
    if not utf8_valid(body):
        raise ZmError("body not UTF-8")
    total = CPO_HDR + len(meta) + len(body)
    if len(body) < 1 or total > CPO_MAX:
        raise ZmError("size out of range")
    hdr = struct.pack("<BBHHIH", PROTO_VER, ENC_UTF8, len(body), len(meta), pow_nonce, 0)
    cpo = hdr + meta + body
    validate_cpo(cpo)
    return cpo


def validate_cpo(cpo: bytes) -> tuple[bytes, bytes]:
    """Strict validation. Returns (meta, body)."""
    if len(cpo) < CPO_HDR + 1 or len(cpo) > CPO_MAX:
        raise ZmError("cpo length")
    ver, enc, blen, mlen, _nonce, rsv = struct.unpack_from("<BBHHIH", cpo, 0)
    if ver != PROTO_VER or enc != ENC_UTF8 or rsv != 0:
        raise ZmError("cpo header")
    if mlen > META_MAX or CPO_HDR + mlen + blen != len(cpo) or blen < 1:
        raise ZmError("cpo lengths")
    meta = cpo[CPO_HDR:CPO_HDR + mlen]
    body = cpo[CPO_HDR + mlen:]
    # TLV walk: bounded by mlen, strictly ascending types
    i, last = 0, -1
    while i < mlen:
        if i + 2 > mlen:
            raise ZmError("tlv truncated")
        t, ln = meta[i], meta[i + 1]
        if t == 0 or t <= last or i + 2 + ln > mlen:
            raise ZmError("tlv invalid")
        last = t
        i += 2 + ln
    if not utf8_valid(body):
        raise ZmError("body not UTF-8")
    return meta, body


# ---------------------------------------------------------------- identity
def chunks_of(cpo: bytes) -> list[bytes]:
    return [cpo[i:i + CHUNK] for i in range(0, len(cpo), CHUNK)]


def leaf_hash(idx: int, chunk: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + bytes([idx]) + chunk).digest()[:LEAF]


def id_from_leaves(total_len: int, leaves: list[bytes]) -> bytes:
    return hashlib.sha256(b"\x01" + struct.pack("<H", total_len) + b"".join(leaves)).digest()


def content_id(cpo: bytes) -> bytes:
    """id(p) = SHA256(0x01 || u16le(len) || leaf_0 || ... || leaf_{n-1}),
    leaf_k = SHA256(0x00 || u8 k || chunk_k)[:8]. A depth-1 hash list: content-derived,
    deterministic, and lets every fragment be verified on arrival."""
    cs = chunks_of(cpo)
    return id_from_leaves(len(cpo), [leaf_hash(i, c) for i, c in enumerate(cs)])


def sid64(cid: bytes) -> bytes:
    return cid[:8]


# ---------------------------------------------------------------- frames
def _vt(t: int) -> int:
    return (PROTO_VER << 4) | t


def frame_manifest(cpo: bytes) -> bytes:
    cs = chunks_of(cpo)
    leaves = b"".join(leaf_hash(i, c) for i, c in enumerate(cs))
    return struct.pack("<BBBBH", MAGIC, _vt(T_MANIFEST), len(cs), 0, len(cpo)) + leaves


def frames_frag(cpo: bytes) -> list[bytes]:
    """Byte 2 is reserved (sent as 0, ignored on receipt). An earlier draft carried a hop count
    there; a hop count of 0 identifies the transmitter as the author, so it was removed."""
    cid = content_id(cpo)
    cs = chunks_of(cpo)
    out = []
    for i, c in enumerate(cs):
        hdr = struct.pack("<BBBBBBH", MAGIC, _vt(T_FRAG), 0, i, len(cs), 0, len(c)) + sid64(cid)
        out.append(hdr + c)
    return out


def burst(cpo: bytes) -> list[bytes]:
    """All frames of one pamphlet: manifest first (omitted for 1-chunk objects)."""
    fr = frames_frag(cpo)
    return fr if len(fr) == 1 else [frame_manifest(cpo)] + fr


@dataclass
class Frag:
    rsv: int
    idx: int
    total: int
    sid: bytes
    chunk: bytes


@dataclass
class Manifest:
    total: int
    length: int
    leaves: list[bytes]

    @property
    def cid(self) -> bytes:
        return id_from_leaves(self.length, self.leaves)


def parse_frame(b: bytes):
    """Strict parse. Raises ZmError on anything unexpected (unknown version included)."""
    if len(b) < 4 or len(b) > FRAME_MAX or b[0] != MAGIC:
        raise ZmError("frame envelope")
    ver, t = b[1] >> 4, b[1] & 0xF
    if ver != PROTO_VER:
        raise ZmError("version")          # higher versions are ignored, never half-parsed
    if t == T_FRAG:
        if len(b) < FRAG_HDR + 1:
            raise ZmError("frag short")
        _, _, rsv0, idx, total, rsv, clen = struct.unpack_from("<BBBBBBH", b, 0)
        if rsv or not (1 <= total <= MAX_CHUNKS) or idx >= total:
            raise ZmError("frag header")
        if not (1 <= clen <= CHUNK) or FRAG_HDR + clen != len(b):
            raise ZmError("frag length")
        if idx < total - 1 and clen != CHUNK:
            raise ZmError("non-final chunk must be full")
        return Frag(rsv0, idx, total, bytes(b[8:16]), bytes(b[16:]))
    if t == T_MANIFEST:
        if len(b) < MANIFEST_HDR:
            raise ZmError("manifest short")
        _, _, total, rsv, length = struct.unpack_from("<BBBBH", b, 0)
        if rsv or not (2 <= total <= MAX_CHUNKS) or len(b) != MANIFEST_HDR + LEAF * total:
            raise ZmError("manifest header")
        if not (CHUNK * (total - 1) < length <= min(CHUNK * total, CPO_MAX)):
            raise ZmError("manifest length")
        lv = [bytes(b[MANIFEST_HDR + LEAF * i:MANIFEST_HDR + LEAF * (i + 1)]) for i in range(total)]
        return Manifest(total, length, lv)
    if t == T_SDB:
        return parse_sdb(b)
    raise ZmError("type")


# ---------------------------------------------------------------- SDB / digest
def bucket_of(cid: bytes) -> int:
    """Fixed bucketing (top 6 bits of id byte 0) so a bucket is a contiguous range of a
    sid64-sorted index on flash."""
    return cid[0] >> 2


def bucket_digests(ids: list[bytes], salt: bytes) -> list[int]:
    """Non-linear salted digest: d_b = trunc16(SHA256(salt || sorted ids in bucket b)).
    An empty bucket hashes the salt alone. Replaces the linear XOR fold, which lets an
    observer who knows the pamphlet universe solve for the library by GF(2) elimination."""
    per = [[] for _ in range(N_BUCKETS)]
    for c in ids:
        per[bucket_of(c)].append(sid64(c))
    out = []
    for b in range(N_BUCKETS):
        h = hashlib.sha256(salt)
        for s in sorted(per[b]):
            h.update(s)
        out.append(int.from_bytes(h.digest()[:2], "little"))
    return out


@dataclass
class Sdb:
    congestion: int
    salt: bytes
    digests: list[int]
    wants: list[bytes] = field(default_factory=list)


def frame_sdb(ids: list[bytes], congestion: int = 0, salt: bytes | None = None,
              wants: list[bytes] = ()) -> bytes:
    salt = salt if salt is not None else os.urandom(4)
    if len(salt) != 4 or not (0 <= congestion <= 7) or len(wants) > N_WANTS:
        raise ZmError("sdb args")
    d = bucket_digests(ids, salt)
    w = list(wants) + [b"\x00" * 8] * (N_WANTS - len(wants))
    return (bytes([MAGIC, _vt(T_SDB), congestion << 1, 0]) + salt
            + struct.pack("<%dH" % N_BUCKETS, *d) + b"".join(w))


def parse_sdb(b: bytes) -> Sdb:
    if len(b) != SDB_LEN or b[3] != 0 or b[2] & 0xF1:
        raise ZmError("sdb")
    d = list(struct.unpack_from("<%dH" % N_BUCKETS, b, 8))
    w = [bytes(b[8 + 2 * N_BUCKETS + 8 * i: 8 + 2 * N_BUCKETS + 8 * (i + 1)]) for i in range(N_WANTS)]
    return Sdb((b[2] >> 1) & 7, bytes(b[4:8]), d, [x for x in w if x != b"\x00" * 8])


def differing_buckets(my_ids: list[bytes], peer: Sdb) -> list[int]:
    mine = bucket_digests(my_ids, peer.salt)
    return [i for i in range(N_BUCKETS) if mine[i] != peer.digests[i]]


# ---------------------------------------------------------------- reassembly
@dataclass
class Slot:
    sid: bytes
    man: Manifest | None = None
    chunks: dict = field(default_factory=dict)
    last_ms: int = 0


class Reassembler:
    """Bounded staging. A fragment is accepted only if it matches its manifest leaf, so a
    forged fragment can neither poison a slot nor force a whole-object hash failure."""

    def __init__(self, slots: int = 8, timeout_ms: int = 120_000):
        self.max_slots = slots
        self.timeout = timeout_ms
        self.slots: dict[bytes, Slot] = {}
        self.stats = {"bad_leaf": 0, "no_manifest": 0, "evicted": 0, "complete": 0}

    def _slot(self, sid: bytes, now: int) -> Slot | None:
        if sid in self.slots:
            return self.slots[sid]
        if len(self.slots) >= self.max_slots:
            old = min(self.slots.values(), key=lambda s: s.last_ms)
            if now - old.last_ms < self.timeout:
                return None                     # refuse rather than thrash
            del self.slots[old.sid]
            self.stats["evicted"] += 1
        s = Slot(sid, last_ms=now)
        self.slots[sid] = s
        return s

    def on_frame(self, fr, now: int = 0, have=lambda sid: False):
        """Returns (cid, cpo) on completion, else None."""
        if isinstance(fr, Manifest):
            cid = fr.cid
            sid = sid64(cid)
            if have(sid):
                return None
            s = self._slot(sid, now)
            if s is not None and s.man is None:
                s.man = fr
                s.last_ms = now
            return None
        if not isinstance(fr, Frag) or have(fr.sid):
            return None
        if fr.total == 1:                       # self-certifying single-chunk object
            cid = id_from_leaves(len(fr.chunk), [leaf_hash(0, fr.chunk)])
            if sid64(cid) != fr.sid:
                self.stats["bad_leaf"] += 1
                return None
            try:
                validate_cpo(fr.chunk)
            except ZmError:
                return None
            self.stats["complete"] += 1
            return cid, fr.chunk
        s = self.slots.get(fr.sid)
        if s is None or s.man is None:
            self.stats["no_manifest"] += 1
            return None
        if fr.total != s.man.total or leaf_hash(fr.idx, fr.chunk) != s.man.leaves[fr.idx]:
            self.stats["bad_leaf"] += 1
            return None
        s.chunks[fr.idx] = fr.chunk
        s.last_ms = now
        if len(s.chunks) == s.man.total:
            cpo = b"".join(s.chunks[i] for i in range(s.man.total))
            del self.slots[fr.sid]
            if len(cpo) != s.man.length:
                return None
            try:
                validate_cpo(cpo)
            except ZmError:
                return None
            cid = s.man.cid
            assert content_id(cpo) == cid      # implied by leaf checks; kept as a self-test
            self.stats["complete"] += 1
            return cid, cpo
        return None


# ---------------------------------------------------------------- NOR flash model
class PowerCut(Exception):
    pass


class NorFlash:
    """Bits only go 1->0 when programming; erase sets a whole sector to 0xFF.
    `cut_after` bytes of programming are allowed before a PowerCut; the interrupted byte
    gets a random subset of its intended 1->0 transitions (torn write)."""

    def __init__(self, sectors: int = 16, sector_size: int = 4096, seed: int = 0):
        self.ss = sector_size
        self.n = sectors
        self.mem = bytearray(b"\xff" * (sectors * sector_size))
        self.cut_after: int | None = None
        self.rng = random.Random(seed)
        self.erase_count = [0] * sectors
        self.programmed = 0

    def program(self, addr: int, data: bytes):
        for i, v in enumerate(data):
            cur = self.mem[addr + i]
            if self.cut_after is not None:
                if self.cut_after == 0:
                    torn = cur & ~(~v & cur & self.rng.randrange(256))
                    self.mem[addr + i] = torn & 0xFF
                    raise PowerCut()
                self.cut_after -= 1
            self.mem[addr + i] = cur & v
            self.programmed += 1

    def erase(self, sector: int):
        if self.cut_after is not None:
            if self.cut_after == 0:
                # torn erase: some bytes back to FF, others not
                base = sector * self.ss
                k = self.rng.randrange(self.ss)
                self.mem[base:base + k] = b"\xff" * k
                raise PowerCut()
            self.cut_after -= 1
        self.mem[sector * self.ss:(sector + 1) * self.ss] = b"\xff" * self.ss
        self.erase_count[sector] += 1

    def read(self, addr: int, n: int) -> bytes:
        return bytes(self.mem[addr:addr + n])


# Record state machine (monotone 1->0 transitions only)
ST_EMPTY, ST_WRITING, ST_WRITTEN, ST_COMMITTED, ST_DEAD = 0xFFFF, 0xFFFE, 0xFFFC, 0xFFF8, 0x0000
SEC_MAGIC = 0x5A4D5331      # "ZMS1"
SEC_HDR = 12                # magic u32, seq u32, state u16 (FFFF open/FFFE closed), rsv u16
REC_HDR = 48                # state u16, len u16, cid[32], rsv u8, flags u8, rsv[8], dead u16
DEAD_OFF = 46               # separate deletion flag: FFFF alive, anything else deleted


class Store:
    """Log-structured pamphlet store over NorFlash.

    Invariants (tested):
      I1  after mount(), at most one committed record per cid
      I2  every committed record re-hashes to its cid
      I4  committed payload bytes never exceed the configured capacity
      I6  a power cut at any byte leaves no committed-but-incomplete record
    """

    def __init__(self, flash: NorFlash, capacity_records: int):
        self.f = flash
        self.cap = capacity_records
        self.index: dict[bytes, int] = {}     # cid -> record address
        self.cur = -1
        self.wp = 0
        self.seq = 0

    # ---- helpers
    def _sec_hdr(self, s):
        m, seq, st, _ = struct.unpack("<IIHH", self.f.read(s * self.f.ss, SEC_HDR))
        return (m, seq, st)

    def _free_sectors(self):
        return [s for s in range(self.f.n) if self._sec_hdr(s)[0] != SEC_MAGIC]

    def _open_sector(self):
        """Open a fresh sector. One erased spare is always kept: when only the spare is
        left, it becomes the head and the oldest closed sector is compacted into it."""
        free = self._free_sectors()
        if not free:
            raise ZmError("no spare sector (invariant broken)")
        s = free[0]
        if self.f.read(s * self.f.ss, self.f.ss) != b"\xff" * self.f.ss:
            self.f.erase(s)
        self.seq += 1
        self.f.program(s * self.f.ss, struct.pack("<IIHH", SEC_MAGIC, self.seq, 0xFFFF, 0xFFFF))
        self.cur, self.wp = s, s * self.f.ss + SEC_HDR
        if len(free) == 1:
            self._gc()

    def _close_sector(self):
        if self.cur >= 0:
            self.f.program(self.cur * self.f.ss + 8, struct.pack("<H", 0xFFFE))
        self.cur = -1

    # ---- mount / recovery
    def mount(self):
        self.index.clear()
        secs = []
        for s in range(self.f.n):
            m, seq, st = self._sec_hdr(s)
            if m == SEC_MAGIC:
                secs.append((seq, s, st))
        secs.sort()
        self.seq = secs[-1][0] if secs else 0
        self.cur = -1
        copies: dict[bytes, list[int]] = {}
        for seq, s, st in secs:
            base = s * self.f.ss
            a = base + SEC_HDR
            end = base + self.f.ss
            clean_end = True
            while a + REC_HDR <= end:
                hdr = self.f.read(a, REC_HDR)
                state, ln = struct.unpack_from("<HH", hdr, 0)
                if hdr == b"\xff" * REC_HDR:
                    break                                     # free space
                if state == ST_COMMITTED and 0 < ln <= CPO_MAX and a + REC_HDR + ln <= end:
                    # only a fully verified record ever reaches ST_COMMITTED, so ln is trusted
                    dead = struct.unpack_from("<H", hdr, DEAD_OFF)[0]
                    if dead != 0xFFFF:
                        if dead != 0x0000:                    # torn delete: finish it (stabilise)
                            self.f.program(a + DEAD_OFF, struct.pack("<H", 0))
                        a += REC_HDR + ln
                        continue
                    cid = hdr[4:36]
                    payload = self.f.read(a + REC_HDR, ln)
                    if content_id(payload) == cid:
                        # a duplicate can only come from an interrupted GC copy; the newest
                        # copy wins in the index, older physical copies are left for GC
                        copies.setdefault(cid, []).append(a)
                        self.index[cid] = a
                        a += REC_HDR + ln
                        continue
                # torn or unverifiable record: it is necessarily the last write in this
                # sector (append-only, sector closed afterwards). Kill it, stop parsing.
                if state != ST_DEAD:
                    self.f.program(a, struct.pack("<H", ST_DEAD))
                clean_end = False
                break
            if s == secs[-1][1] and st == 0xFFFF and clean_end:
                self.cur, self.wp = s, a
            elif st == 0xFFFF:
                self.f.program(base + 8, struct.pack("<H", 0xFFFE))
        if len(self.index) > self.cap:
            raise AssertionError("capacity exceeded on mount")
        if not self._free_sectors() and secs:
            self._recover_interrupted_gc(secs, copies)

    def _recover_interrupted_gc(self, secs, copies):
        """No erased spare means power failed inside _gc() (spare already claimed as head,
        victim not yet erased)."""
        head = secs[-1][1]
        if self.cur == head:
            self._gc()                               # head intact: just finish compaction
            return
        # head holds a torn copy: every committed record in it is a copy of a record that is
        # still committed in the victim. Point the index back at the older copies, erase head.
        for cid, addrs in copies.items():
            if self.index.get(cid, -1) // self.f.ss == head:
                older = [a for a in addrs if a // self.f.ss != head]
                assert older, "record only in GC head: impossible by construction"
                self.index[cid] = older[-1]
        self.f.erase(head)

    # ---- operations
    def has(self, cid: bytes) -> bool:
        return cid in self.index

    def commit(self, cid: bytes, cpo: bytes, flags: int = 0) -> bool:
        if cid in self.index:
            return False                                      # I1
        if len(self.index) >= self.cap:
            return False                                      # I4 (admission policy runs before)
        if content_id(cpo) != cid:
            raise ZmError("hash mismatch")                    # I2
        need = REC_HDR + len(cpo)
        if self.cur < 0 or self.wp + need > (self.cur + 1) * self.f.ss:
            self._close_sector()
            self._open_sector()
        a = self.wp
        self.f.program(a, struct.pack("<HH", ST_WRITING, len(cpo)) + cid + bytes([0, flags & 0xFF]))
        self.f.program(a + REC_HDR, cpo)
        self.f.program(a, struct.pack("<H", ST_WRITTEN))
        if content_id(self.f.read(a + REC_HDR, len(cpo))) != cid:   # read-back verify
            self.f.program(a, struct.pack("<H", ST_DEAD))
            self._close_sector()                              # a killed record is always last
            return False
        self.f.program(a, struct.pack("<H", ST_COMMITTED))
        self.index[cid] = a
        self.wp = a + need
        return True

    def delete(self, cid: bytes):
        a = self.index.pop(cid, None)
        if a is not None:
            self.f.program(a + DEAD_OFF, struct.pack("<H", 0))

    def get(self, cid: bytes) -> bytes:
        a = self.index[cid]
        ln = struct.unpack("<H", self.f.read(a + 2, 2))[0]
        return self.f.read(a + REC_HDR, ln)

    def _gc(self):
        """Compact the oldest closed sector into the (fresh) head sector, then erase it.
        Crash between copy and erase leaves two committed copies; mount() keeps the
        newest and kills the older (I1 holds on the logical view after mount)."""
        secs = sorted((self._sec_hdr(s)[1], s) for s in range(self.f.n)
                      if self._sec_hdr(s)[0] == SEC_MAGIC and s != self.cur)
        if not secs:
            return
        victim = secs[0][1]
        live = [c for c, a in self.index.items() if a // self.f.ss == victim]
        for c in live:
            data = self.get(c)
            a = self.wp
            need = REC_HDR + len(data)
            assert a + need <= (self.cur + 1) * self.f.ss, "victim live data exceeds a sector"
            self.f.program(a, struct.pack("<HH", ST_WRITING, len(data)) + c + bytes([0, 0]))
            self.f.program(a + REC_HDR, data)
            self.f.program(a, struct.pack("<H", ST_WRITTEN))
            self.f.program(a, struct.pack("<H", ST_COMMITTED))
            self.index[c] = a
            self.wp = a + need
        self.f.erase(victim)


def verify_store(store: Store) -> None:
    """Assert I1, I2, I4 on the logical view."""
    assert len(store.index) <= store.cap
    seen = set()
    for cid, a in store.index.items():
        assert cid not in seen
        seen.add(cid)
        st, ln = struct.unpack("<HH", store.f.read(a, 4))
        assert st == ST_COMMITTED
        assert store.f.read(a + DEAD_OFF, 2) == b"\xff\xff"
        assert content_id(store.f.read(a + REC_HDR, ln)) == cid
