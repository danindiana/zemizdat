#!/usr/bin/env python3
"""ZEMIZDAT-SIM-1.0 — round-based dissemination simulator with an explicit airtime model.

SIMULATION, NOT MEASUREMENT. Every physical constant below is either taken from a cited
specification (marked [spec]) or is an ASSUMPTION (marked [assume]) that the hardware
experiments in 08_verification/test_plan.md are designed to replace.

Model in one paragraph
----------------------
Time advances in rounds of `dt` seconds. Each round the environment yields *cells*: groups
of devices close enough to decode each other (reception neighbourhoods), and for every
cell the size of its *interference domain* (devices whose transmissions collide with the
cell's). Broadcast strategies emit BLE-5 extended-advertising events; each event carries
one ZEMIZDAT frame. Primary-channel pointer collisions and secondary-channel collisions
follow unslotted ALOHA, e^{-2G}. A receiver decodes a frame with probability
q = scan_duty * ALOHA success * (1 - p_loss) * host_cap, where host_cap models the finite
rate at which a scanner can follow AUX pointers and hand reports to the host. A pamphlet of
1 KiB is 5 chunks + 1 manifest = 6 frames; fragments accumulate across bursts and senders
(per-fragment verification makes that safe); data fragments are useless before the
manifest. Pairwise strategies use reliable BLE connections whose setup costs time and whose
aggregate goodput is a shared per-domain budget.

Strategies
----------
  BCAST     simple repeated broadcasting, fixed advertising rate, random item choice
  BCAST_RC  BCAST + density-adaptive rate control (ablation of HYBRID)
  PAIRWISE  connection-based blind push (receiver aborts duplicates after the first chunk)
  AE_INV    connection-based anti-entropy with a full sorted sid64 inventory exchange
  HYBRID    proposed ZEMIZDAT-PROTO-1.0: rate control + SDB bucket digests + demand-weighted
            carousel + verified suppression + listener floor
  ORACLE    upper bound, not implementable: HYBRID's radio behaviour with perfect knowledge of
            what every receiver in the cell lacks

Run `python3 simulator.py --help`.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field

import numpy as np

np.seterr(over="ignore")   # bucket signatures are sums mod 2^64 by design
import warnings  # noqa: E402
warnings.filterwarnings("ignore", message="overflow encountered in scalar")

LISTEN, EXCHANGE, COURIER = 0, 1, 2
HONEST, FLOOD, BLACKHOLE, SUPPRESS = 0, 1, 2, 3
N_BUCKETS = 64


# ============================================================================ parameters
@dataclass
class Params:
    # population / content
    N: int = 500
    mode_mix: tuple = (0.2, 0.3, 0.5)        # LISTEN, EXCHANGE, COURIER   [assume]
    h: float = 1.0                           # cooperative fraction
    adversary: str = "flood"                 # flood | blackhole | suppress
    body_bytes: int = 1024                   # pamphlet body
    capacity: int = 0                        # storage slots per device (0 = unlimited)
    admission: str = "naive"                 # naive | quota | strata | quota_strata
    quota_per_min: float = 60.0
    strata_epoch_s: float = 300.0
    # environment
    env: str = "auditorium"                  # auditorium | rooms | city | barbell
    density: float = 1.0                     # people per m^2 (auditorium/rooms)
    rooms: int = 15
    room_move_per_min: float = 0.05
    move_prob: float = 0.02                  # per round probability a person walks
    walk_speed: float = 1.0                  # m/s
    r_rx: float = 10.0                       # reception tile edge, m              [assume]
    r_int: float = 35.0                      # interference radius, m               [assume]
    city_enc_per_h: float = 1.5              # encounters per node per hour         [assume]
    city_mean_contact_s: float = 90.0
    city_communities: int = 20
    city_p_in: float = 0.8
    city_group_p: float = 0.15               # chance an encounter is a group >2
    bridges: int = 6
    cut_bridges: bool = False
    # time
    T: float = 3600.0
    dt: float = 1.0
    sample_s: float = 60.0
    # PHY (BLE 5 extended advertising)
    tau_p: float = 136e-6                    # ADV_EXT_IND on 1M PHY: 17 B          [spec-derived]
    tau_a: float = 1.064e-3                  # AUX_ADV_IND 255 B on 2M PHY          [spec-derived]
    n_sec: int = 37                          # secondary channels                   [spec]
    p_loss: float = 0.10                     # residual fading/Wi-Fi loss            [assume]
    host_rate: float = 200.0                 # reports/s a scanner+host can process  [assume]
    scan_duty: tuple = (0.3, 0.3, 0.3)       # per mode, while neighbours are present   [assume]
    idle_duty: float = 0.05                  # background scan when nobody is around    [assume]
    adv_rate: float = 10.0                   # unregulated events/s/node (100 ms)   [assume]
    chain: int = 3                           # AUX PDUs per adv event (AUX_ADV_IND + chain) [spec <=1650 B]
    G_target: float = 0.25                   # rate-control target, primary channels
    Ga_target: float = 0.15                  # rate-control target, secondary channels
    lam_max: float = 25.0                    # per-node cap events/s
    # HYBRID
    sdb_period: float = 4.0
    sdb_cache: int = 32
    eps: float = 0.05
    listen_floor: float = 0.3
    verified_suppression: bool = True
    sdb: bool = True                         # send summary digest beacons at all (v1 default: off)
    digest_weight: bool = True               # bucket-digest demand weighting from SDBs
    age_weight: bool = True                  # least-recently-overheard-first (Trickle-style)
    age_cap_s: float = 600.0
    burst_n: int = 8                         # HYBRID: <= this many transmitters in the domain -> burst mode
    burst_duty: float = 1.0                  # scan duty in burst mode
    burst_lam: float = 100.0                 # events/s cap in burst mode
    rc_scope: str = "domain"                 # domain: controller knows its interference domain (ideal)
                                             # cell: it only counts transmitters it can decode
    rc_kappa: float = 1.0                    # correction factor applied to the decodable count
    rep_interval_s: float = 2.0              # a device re-sends the same item at most every 2 s
    # pairwise
    conn_setup_s: float = 0.4                # discovery->connect->MTU/DLE->GATT     [assume]
    link_Bps: float = 40_000.0               # per-connection app goodput             [assume]
    domain_Bps: float = 1_500_000.0          # aggregate data-channel goodput per domain [assume]
    conn_max_s: float = 60.0
    conn_cooldown_s: float = 30.0            # idle time after a connection ends     [assume]
    dup_cost: int = 260
    # adversary
    flood_rate: float = 50.0
    # bookkeeping
    strategy: str = "HYBRID"
    seed: int = 1
    trace: bool = False


# ============================================================================ environments
class Env:
    def __init__(self, p: Params, rng):
        self.p, self.rng = p, rng

    def cells(self, t):
        """Return list of (node_index_array, interference_domain_id)."""
        raise NotImplementedError


class Hall(Env):
    """One or more rectangular rooms; reception = randomly shifted r_rx tiles; interference
    = a disc of radius r_int, approximated per room as min(1, pi r_int^2 / area) of the room."""

    def __init__(self, p, rng, n_rooms):
        super().__init__(p, rng)
        self.n_rooms = n_rooms
        per = max(1, p.N // n_rooms)
        side = math.sqrt(per / p.density)
        self.side = max(side, 1.0)
        self.room = rng.integers(0, n_rooms, p.N)
        self.xy = rng.uniform(0, self.side, (p.N, 2))
        area = self.side ** 2
        self.int_frac = min(1.0, math.pi * p.r_int ** 2 / area)

    def step_mobility(self):
        p, rng = self.p, self.rng
        mv = rng.random(p.N) < p.move_prob
        if mv.any():
            ang = rng.uniform(0, 2 * math.pi, mv.sum())
            d = p.walk_speed * p.dt * 10
            self.xy[mv, 0] = np.clip(self.xy[mv, 0] + d * np.cos(ang), 0, self.side)
            self.xy[mv, 1] = np.clip(self.xy[mv, 1] + d * np.sin(ang), 0, self.side)
        if self.n_rooms > 1 and p.room_move_per_min > 0:
            ch = rng.random(p.N) < p.room_move_per_min * p.dt / 60
            if ch.any():
                self.room[ch] = rng.integers(0, self.n_rooms, ch.sum())
                self.xy[ch] = rng.uniform(0, self.side, (ch.sum(), 2))

    def cells(self, t):
        self.step_mobility()
        off = self.rng.uniform(0, self.p.r_rx, 2)
        tx = ((self.xy[:, 0] + off[0]) // self.p.r_rx).astype(np.int64)
        ty = ((self.xy[:, 1] + off[1]) // self.p.r_rx).astype(np.int64)
        key = (self.room * 100_000 + tx * 1000 + ty)
        order = np.argsort(key, kind="stable")
        ks = key[order]
        cut = np.flatnonzero(np.diff(ks)) + 1
        groups = np.split(order, cut)
        return [(g, int(self.room[g[0]])) for g in groups if len(g) > 1]


class Barbell(Hall):
    """Two rooms joined only by `bridges` couriers that alternate rooms every 5 minutes."""

    def __init__(self, p, rng):
        super().__init__(p, rng, 2)
        self.room[: p.N // 2] = 0
        self.room[p.N // 2:] = 1
        self.bridge_ids = rng.choice(p.N, p.bridges, replace=False)

    def step_mobility(self):
        p = self.p
        mv = self.rng.random(p.N) < p.move_prob
        if mv.any():
            ang = self.rng.uniform(0, 2 * math.pi, mv.sum())
            self.xy[mv, 0] = np.clip(self.xy[mv, 0] + 10 * np.cos(ang), 0, self.side)
            self.xy[mv, 1] = np.clip(self.xy[mv, 1] + 10 * np.sin(ang), 0, self.side)
        self.t = getattr(self, "t", 0) + p.dt
        if int(self.t) % 300 == 0:
            for b in self.bridge_ids:
                self.room[b] = 1 - self.room[b]

    def cells(self, t):
        cs = super().cells(t)
        if self.p.cut_bridges:   # interdiction: bridges silenced (seized / jammed)
            bset = set(self.bridge_ids.tolist())
            cs = [(np.array([i for i in g if i not in bset]), d) for g, d in cs]
            cs = [(g, d) for g, d in cs if len(g) > 1]
        return cs


class City(Env):
    """Encounter process: Poisson encounters, community structure, geometric durations."""

    def __init__(self, p, rng):
        super().__init__(p, rng)
        self.comm = rng.integers(0, p.city_communities, p.N)
        self.members = [np.flatnonzero(self.comm == c) for c in range(p.city_communities)]
        self.active: list[tuple[np.ndarray, float]] = []
        self.busy = np.zeros(p.N, bool)
        self.int_frac = 1.0
        self.n_rooms = 1

    def cells(self, t):
        p, rng = self.p, self.rng
        self.active = [(g, end) for g, end in self.active if end > t]
        self.busy[:] = False
        for g, _ in self.active:
            self.busy[g] = True
        lam = p.N * p.city_enc_per_h * p.dt / 3600 / 2
        for _ in range(rng.poisson(lam)):
            a = int(rng.integers(p.N))
            if self.busy[a]:
                continue
            size = 2 if rng.random() > p.city_group_p else int(rng.integers(3, 9))
            if rng.random() < p.city_p_in:
                pool = self.members[self.comm[a]]
            else:
                pool = None
            others = []
            for _ in range(size - 1):
                b = int(rng.choice(pool)) if pool is not None else int(rng.integers(p.N))
                if b != a and not self.busy[b] and b not in others:
                    others.append(b)
            if not others:
                continue
            g = np.array([a] + others)
            self.busy[g] = True
            dur = rng.exponential(p.city_mean_contact_s)
            self.active.append((g, t + max(p.dt, dur)))
        return [(g, k) for k, (g, _) in enumerate(self.active)]


def make_env(p, rng):
    if p.env == "auditorium":
        return Hall(p, rng, 1)
    if p.env == "rooms":
        return Hall(p, rng, p.rooms)
    if p.env == "barbell":
        return Barbell(p, rng)
    if p.env == "city":
        return City(p, rng)
    raise ValueError(p.env)


# ============================================================================ simulator
class Sim:
    def __init__(self, p: Params):
        self.p = p
        self.rng = rng = np.random.default_rng(p.seed)
        N = p.N
        self.mode = rng.choice(3, N, p=list(p.mode_mix))
        self.adv = np.zeros(N, np.int8)
        n_bad = int(round((1 - p.h) * N))
        if n_bad:
            bad = rng.choice(N, n_bad, replace=False)
            self.adv[bad] = {"flood": FLOOD, "blackhole": BLACKHOLE, "suppress": SUPPRESS}[p.adversary]
        self.honest = self.adv == HONEST
        # honest originators: EXCHANGE or COURIER, honest
        self.origin = np.flatnonzero(self.honest & (self.mode != LISTEN))
        self.M = M = len(self.origin)
        cpo_len = 12 + p.body_bytes
        self.K = -(-cpo_len // 220)
        self.F = self.K + 1 if self.K > 1 else 1           # frames per burst
        self.full = (1 << self.F) - 1
        self.obj_bytes = int(cpo_len * 1.10) + 32          # unicast incl. L2CAP/ATT overhead
        self.prog = np.zeros((N, M), np.uint32)
        self.have = np.zeros((N, M), bool)
        self.have[self.origin, np.arange(M)] = True
        self.prog[self.origin, np.arange(M)] = self.full
        self.own = np.full(N, -1)
        self.own[self.origin] = np.arange(M)
        self.bucket = rng.integers(0, N_BUCKETS, M)
        self.rkey = rng.integers(1, 2 ** 63, M, dtype=np.int64).astype(np.uint64)
        self.sig = np.zeros((N, N_BUCKETS), np.uint64)
        np.add.at(self.sig, (self.origin, self.bucket), self.rkey)
        self.libn = self.have.sum(1)
        self.heard = np.full((N, M), -1e9, np.float32) if p.strategy == "HYBRID" else None
        self.junk = np.zeros(N, np.int64)
        self.cap = p.capacity if p.capacity > 0 else 10 ** 9
        self.tokens = np.full(N, p.quota_per_min)
        self.n_ep = int(math.ceil(p.T / p.strata_epoch_s)) + 1
        if p.admission in ("strata", "quota_strata"):
            self.adm_ep = np.full((N, M), -1, np.int16)      # epoch of admission (-1: not held / pinned)
            self.hon_ep = np.zeros((N, self.n_ep), np.int64)
            self.junk_ep = np.zeros((N, self.n_ep), np.int64)
        self.duty = np.array(p.scan_duty)[self.mode].astype(float)
        self.duty[self.adv == BLACKHOLE] = 0.3
        self.can_tx = (self.mode != LISTEN) & (self.adv != BLACKHOLE)
        self.can_fwd = (self.mode == COURIER) & self.honest
        self.sdb_sender = self.can_tx & self.honest
        self.env = make_env(p, rng)
        self.chainlen = max(1, min(p.chain, self.F))
        self._busy = np.zeros(M, bool)
        self._last_R: dict = {}
        # pairwise state
        self.partner = np.full(N, -1)
        self.conn_left = np.zeros(N)
        self.setup_left = np.zeros(N)
        self.inv_left = np.zeros(N)
        self.cool_until = np.zeros(N)
        self.queue: dict[int, np.ndarray] = {}
        self.qpos: dict[int, int] = {}
        # metrics
        self.m = dict(tx_events=0, tx_frames_useful=0, new_bits=0, rx_frames_ok=0,
                      junk_events=0, sdb_events=0, bytes_unicast=0, bytes_wasted=0,
                      bytes_inventory=0, conns=0, G_sum=0.0, G_n=0, G_max=0.0,
                      honest_drops_full=0, honest_drops_quota=0, forged_events=0)
        self.tx_time = np.zeros(N)
        self.contact_time = np.zeros(N)
        self.rx_on = np.zeros(N)            # active-scan seconds, accumulated per cell-round
        self._dom_ntx = 10 ** 9
        self.first_cov = {a: np.full(M, np.nan) for a in (0.5, 0.8, 0.9)}
        self.series = []

    # ------------------------------------------------------------- helpers
    def _admit(self, r, now):
        """Admission for one honest object at receiver r. Returns True if it may be stored
        (any eviction needed to make room has already been applied)."""
        p = self.p
        if p.admission in ("quota", "quota_strata"):
            if self.tokens[r] < 1:
                self.m["honest_drops_quota"] += 1
                return False
            self.tokens[r] -= 1
        total = self.libn[r] + self.junk[r]
        if p.admission in ("strata", "quota_strata"):
            e = self._epoch(now)
            if total < self.cap or self._evict_for(r, e):
                self._pending_epoch = e
                return True
            self.m["honest_drops_full"] += 1
            return False
        if total < self.cap:
            return True
        self.m["honest_drops_full"] += 1
        return False

    # ---- time-stratified reservoir -------------------------------------------------
    def _epoch(self, now):
        return min(int(now // self.p.strata_epoch_s), self.n_ep - 1)

    def _strata_counts(self, r):
        return self.hon_ep[r] + self.junk_ep[r]

    def _evict_for(self, r, e):
        """Make room for one arrival in epoch e: evict one random unpinned item from the epoch
        holding the most items, if that epoch exceeds its fair share. Content-neutral."""
        c = self._strata_counts(r)
        rep = int((c > 0).sum() + (1 if c[e] == 0 else 0))
        pinned = 1 if self.own[r] >= 0 else 0
        share = (self.cap - pinned) / max(1, rep)
        j = int(np.argmax(c))
        if c[j] <= share:
            return False
        if self.rng.random() < self.junk_ep[r, j] / c[j]:
            self.junk_ep[r, j] -= 1
            self.junk[r] -= 1
        else:
            cand = np.flatnonzero(self.adm_ep[r] == j)
            it = int(self.rng.choice(cand))
            self._drop_item(r, it)
        return True

    def _drop_item(self, r, it):
        self.have[r, it] = False
        self.prog[r, it] = 0
        self.libn[r] -= 1
        self.sig[r, self.bucket[it]] -= self.rkey[it]
        self.hon_ep[r, self.adm_ep[r, it]] -= 1
        self.adm_ep[r, it] = -1
        self.m["honest_evicted"] = self.m.get("honest_evicted", 0) + 1

    def _note_admitted(self, r, it):
        if self.p.admission in ("strata", "quota_strata"):
            e = self._pending_epoch
            self.adm_ep[r, it] = e
            self.hon_ep[r, e] += 1

    def _admit_junk(self, r_idx, counts, now):
        p = self.p
        if p.admission in ("quota", "quota_strata"):
            take = np.minimum(counts, np.floor(self.tokens[r_idx]).astype(np.int64))
            self.tokens[r_idx] -= take
            counts = take
        room = np.maximum(0, self.cap - self.libn[r_idx] - self.junk[r_idx])
        first = np.minimum(counts, room)
        self.junk[r_idx] += first
        if p.admission not in ("strata", "quota_strata"):
            return
        e = self._epoch(now)
        self.junk_ep[r_idx, e] += first
        rest = counts - first
        for r, k in zip(r_idx[rest > 0], rest[rest > 0]):
            k = int(k)
            while k > 0:
                c = self._strata_counts(r)
                rep = int((c > 0).sum() + (1 if c[e] == 0 else 0))
                pinned = 1 if self.own[r] >= 0 else 0
                share = (self.cap - pinned) / max(1, rep)
                j = int(np.argmax(c))
                if c[j] <= share:
                    break
                n_ev = int(min(k, math.ceil(c[j] - share)))
                xj = int(self.rng.binomial(n_ev, self.junk_ep[r, j] / c[j]))
                xh = min(n_ev - xj, int(self.hon_ep[r, j]))
                xj = min(n_ev - xh, int(self.junk_ep[r, j]))   # never evict more than exists
                n_ev = xj + xh
                if n_ev == 0:
                    break
                self.junk_ep[r, j] -= xj
                self.junk[r] -= xj
                if xh:
                    cand = np.flatnonzero(self.adm_ep[r] == j)
                    for it in self.rng.choice(cand, xh, replace=False):
                        self._drop_item(r, int(it))
                self.junk_ep[r, e] += n_ev
                self.junk[r] += n_ev
                k -= n_ev

    def _chain_table(self):
        """mask[L, off]: frames obtained when the first L PDUs of an event were decoded and the
        event's window starts at position `off` of the cyclic sequence [manifest, c0..c_{K-1}].
        The controller hands the whole chain to the host as one report, so the host can apply
        the manifest before the chunks of the same event."""
        if hasattr(self, "_tab"):
            return self._tab
        F = self.F
        tab = np.zeros((self.chainlen + 1, F), np.uint32)
        for L in range(self.chainlen + 1):
            for off in range(F):
                m = 0
                for j in range(L):
                    m |= 1 << ((off + j) % F)
                tab[L, off] = m
        self._tab = tab
        return tab

    def _deliver(self, rcv, items, mult, P0, a, now):
        """Broadcast delivery. P0[r]: prob. receiver r catches the primary pointer of one event
        (scan duty x primary ALOHA x host cap). a: per-AUX-PDU success. A chain is decoded as a
        prefix of a cyclic window over [manifest, chunks]; up to 4 events of the same item in a
        round are drawn independently (more are truncated: a lower bound)."""
        if len(items) == 0 or len(rcv) == 0:
            return
        F, K = self.F, self.K
        need = ~self.have[np.ix_(rcv, items)]
        if not need.any():
            return
        Lc = self.chainlen
        ks = np.arange(1, Lc + 1)
        pk = P0[:, None] * (a ** ks)[None, :]                              # r x Lc : P(L >= k)
        tab = self._chain_table()
        mask = np.zeros((len(rcv), len(items)), np.uint32)
        for j in range(int(min(mult.max(), 4))):                          # independent events
            act = (mult > j)[None, :]
            u = self.rng.random((len(rcv), len(items), 1))
            L = (u < pk[:, None, :]).sum(2)                                # prefix length
            off = self.rng.integers(0, F, L.shape)
            mask |= np.where(act, tab[L, off], 0).astype(np.uint32)
            if self.heard is not None:
                caught = act & (L > 0)
                if caught.any():
                    ri, ui = np.nonzero(caught)
                    self.heard[rcv[ri], items[ui]] = now
        big = mult > 4
        if big.any():
            # many events of the same item (sparse contact, long round): per-frame coverage
            # 1-(1-pi)^m with pi = (1/F) sum_j P(prefix > j); frames treated as independent
            pi = pk.sum(1) / F                                             # r
            m_extra = (mult[big] - 4)[None, :]
            pf = 1.0 - (1.0 - pi[:, None]) ** m_extra                      # r x b
            draws = self.rng.random((len(rcv), int(big.sum()), F)) < pf[:, :, None]
            extra = (draws * (1 << np.arange(F, dtype=np.uint32))).sum(2).astype(np.uint32)
            mask[:, big] |= extra
        mask &= np.where(need, self.full, 0).astype(np.uint32)
        old = self.prog[np.ix_(rcv, items)]
        if F > 1:
            gate = ((old | mask) & 1).astype(bool)                         # manifest gates data
            mask = np.where(gate, mask, 0).astype(np.uint32)
        new = old | mask
        added = new & ~old
        nb = int(np.unpackbits(added.view(np.uint8)).sum())
        if nb == 0:
            return
        self.m["new_bits"] += nb
        done = (new == self.full) & need
        if done.any() and self.cap >= 10 ** 9 and self.p.admission not in ("quota", "quota_strata"):
            ri, ui = np.nonzero(done)
            rr, ii = rcv[ri], items[ui]
            self.have[rr, ii] = True
            np.add.at(self.libn, rr, 1)
            np.add.at(self.sig, (rr, self.bucket[ii]), self.rkey[ii])
        elif done.any():
            ri, ui = np.nonzero(done)
            for a_, b_ in zip(ri, ui):
                r, it = rcv[a_], items[b_]
                if not self._admit(r, now):
                    new[a_, b_] = 0
                    continue
                self._note_admitted(r, it)
                self.have[r, it] = True
                self.libn[r] += 1
                self.sig[r, self.bucket[it]] += self.rkey[it]
        self.prog[np.ix_(rcv, items)] = new

    def _record_cov(self, t):
        rec = self.honest
        cov = self.have[rec].mean(0)
        for a, arr in self.first_cov.items():
            hit = np.isnan(arr) & (cov >= a)
            arr[hit] = t

    # ------------------------------------------------------------- broadcast family
    def _R_target(self, int_frac):
        """Events/s per interference domain that keep both primary and secondary load at
        G_target (unslotted ALOHA optimum is G=0.5; 0.3 leaves margin)."""
        p = self.p
        L = self.chainlen
        return min(p.G_target / p.tau_p, p.Ga_target * p.n_sec / (L * p.tau_a)) / max(int_frac, 1e-9)

    def _broadcast_round(self, cells, t):
        p = self.p
        dom_of = {}
        for g, d in cells:
            dom_of.setdefault(d, []).append(g)
        int_frac = getattr(self.env, "int_frac", 1.0)
        for d, gs in dom_of.items():
            allg = np.concatenate(gs)
            txc = allg[self.can_tx[allg] & self.honest[allg]]
            n_tx = len(txc)
            n_fl = int((self.adv[allg] == FLOOD).sum())
            n_sup = int((self.adv[allg] == SUPPRESS).sum())
            if p.strategy == "BCAST":
                lam_each = p.adv_rate
            else:
                lam_each = min(p.lam_max, self._R_target(int_frac) / max(1, n_tx))
            # expected events in domain (honest at lam_each; HYBRID may send fewer)
            R_ev = (self._last_R.get(d, n_tx * lam_each)) + n_fl * p.flood_rate + n_sup * 5.0
            Gp = R_ev * p.tau_p * int_frac
            Ga = R_ev * self.chainlen * p.tau_a * int_frac / p.n_sec
            self.m["G_sum"] += Gp + Ga; self.m["G_n"] += 1
            self.m["G_max"] = max(self.m["G_max"], Gp + Ga)
            sp = math.exp(-2 * Gp)
            a = math.exp(-2 * Ga) * (1 - p.p_loss)
            ev_total = 0
            self._dom_ntx = n_tx
            for g in gs:
                ev_total += self._broadcast_cell(g, lam_each, sp, a, t)
            self._last_R[d] = ev_total / p.dt

    def _broadcast_cell(self, g, lam_each, sp, a, t):
        """Returns number of honest events emitted in this cell this round."""
        p, rng = self.p, self.rng
        dt, F = p.dt, self.F
        strat = p.strategy
        t_ev = 3 * p.tau_p + self.chainlen * p.tau_a
        tx = g[self.can_tx[g] & self.honest[g]]
        if p.rc_scope == "cell" and strat != "BCAST":
            lam_each = min(p.lam_max, self._R_target(1.0) / max(1.0, len(tx) * p.rc_kappa))
        burst = strat == "HYBRID" and p.burst_n > 0 and self._dom_ntx <= p.burst_n
        if burst:
            # sparse contact: airtime is not scarce, contact time is -> listen fully, send fast
            lam_each = min(p.burst_lam, self._R_target(1.0) / max(1, self._dom_ntx))
        ev = rng.poisson(lam_each * dt, len(tx)).astype(np.int64)
        sdb_ev = np.zeros(len(tx), np.int64)
        if strat == "HYBRID" and len(tx) and p.sdb:
            p_sdb = min(1.0, dt / p.sdb_period)
            sdb_ev = np.minimum(ev, (rng.random(len(tx)) < p_sdb).astype(np.int64))
            self.m["sdb_events"] += int(sdb_ev.sum())
        bursts = ev - sdb_ev                         # one chained event = one pamphlet burst
        self.m["tx_events"] += int(sdb_ev.sum())
        self.tx_time[tx] += sdb_ev * (3 * p.tau_p + p.tau_a)
        chosen = []
        forged = set()
        sup = g[self.adv[g] == SUPPRESS]
        if len(sup):
            present = np.flatnonzero(self.have[g].any(0))
            if len(present):
                k = min(len(present), int(5 * p.dt * len(sup)))
                forged = set(rng.choice(present, k, replace=False).tolist())
                self.m["forged_events"] += k
        nbr_pool = None
        if strat == "HYBRID":
            senders = g[self.sdb_sender[g]]
            if len(senders) > p.sdb_cache:
                senders = rng.choice(senders, p.sdb_cache, replace=False)
            nbr_pool = senders
        busy = self._busy
        touched = []
        sent_events = int(sdb_ev.sum())
        for k, i in enumerate(tx):
            nb = int(bursts[k])
            if nb == 0:
                continue
            if self.can_fwd[i]:
                cand = np.flatnonzero(self.have[i])
            else:
                cand = np.array([self.own[i]]) if self.own[i] >= 0 else np.array([], int)
            if len(cand) == 0:
                continue
            if strat == "ORACLE":
                # NOT IMPLEMENTABLE: exact knowledge of every receiver's library in the cell.
                need = (~self.have[np.ix_(g, cand)]).sum(0).astype(float)
                need[busy[cand]] = 0
                if need.sum() == 0:
                    continue
                order = np.argsort(-need)[:nb]
                picks = cand[order[need[order] > 0]]
            elif strat == "HYBRID":
                nbrs = nbr_pool[nbr_pool != i]
                diff = (self.sig[nbrs] != self.sig[i][None, :]).sum(0) if len(nbrs) else np.zeros(N_BUCKETS)
                w = diff[self.bucket[cand]].astype(float)
                if not (p.digest_weight and p.sdb):
                    w = np.ones(len(cand))
                if w.sum() == 0:
                    # every SDB-sending neighbour matches: only a listener floor remains
                    nb = int(rng.binomial(nb, p.listen_floor))
                    if nb == 0:
                        continue
                    w = np.ones(len(cand))
                w = w + p.eps * (w.sum() / len(w))
                if p.age_weight:
                    age = np.minimum(t - self.heard[i, cand], p.age_cap_s) + 1.0
                    w = w * age
                # carousel: no repeat within a cycle; long rounds (sparse contacts) run whole cycles.
                # Weighted sampling without replacement (Efraimidis-Spirakis exponential race).
                k1 = min(nb, len(cand))
                keys = rng.exponential(size=len(cand)) / w
                picks = cand[np.argpartition(keys, k1 - 1)[:k1]] if k1 < len(cand) else cand[np.argsort(keys)]
                reps = max(1, int(p.dt / p.rep_interval_s))
                if nb > len(cand) and reps > 1:
                    extra = min(nb - k1, (reps - 1) * len(cand))
                    picks = np.concatenate([picks, np.resize(rng.permutation(cand), extra)])
            else:
                picks = rng.choice(cand, size=nb)
            if strat in ("HYBRID", "ORACLE") and touched:
                # overheard another holder sending it (verified against own copy): suppress
                n0 = len(picks)
                picks = picks[~busy[picks]]
                if burst and len(picks) < n0:
                    # no contention: reuse the slot for something nobody is sending
                    free = cand[~busy[cand]]
                    free = free[~np.isin(free, picks)]
                    if len(free):
                        picks = np.concatenate([picks, rng.choice(free, min(n0 - len(picks), len(free)),
                                                                  replace=False)])
            if forged and strat == "HYBRID" and not p.verified_suppression:
                picks = picks[~np.isin(picks, np.fromiter(forged, int, len(forged)))]
            if len(picks) == 0:
                continue
            if strat in ("HYBRID", "ORACLE"):
                busy[picks] = True
                touched.append(picks)
            chosen.extend(picks.tolist())
            if self.heard is not None:
                self.heard[i, picks] = t
            sent_events += len(picks)
            self.m["tx_events"] += len(picks)
            self.tx_time[i] += len(picks) * t_ev
        for tp in touched:
            busy[tp] = False
        rcv = g[self.duty[g] > 0]
        if len(rcv) == 0:
            return sent_events
        n_fl = int((self.adv[g] == FLOOD).sum())
        R_cell = sent_events / dt + n_fl * p.flood_rate + len(sup) * 5.0
        duty = np.full(len(rcv), p.burst_duty) if burst else self.duty[rcv]
        self.rx_on[rcv] += duty * dt
        offered = R_cell * duty * sp
        host = np.minimum(1.0, p.host_rate / np.maximum(offered, 1e-9))
        P0 = duty * sp * host
        if chosen:
            items, mult = np.unique(np.array(chosen), return_counts=True)
            self._deliver(rcv, items, mult, P0, a, t)
        if n_fl:
            n_junk = rng.poisson(n_fl * p.flood_rate * dt) * self.chainlen
            self.m["junk_events"] += n_junk
            hon_mask = self.honest[rcv]
            if hon_mask.any() and n_junk:
                qj = P0[hon_mask] * a * (1 - a ** self.chainlen) / max(1e-12, (1 - a)) / self.chainlen
                got = rng.binomial(n_junk, np.clip(qj, 0, 1))
                self._admit_junk(rcv[hon_mask], got, t)
        return sent_events

    # ------------------------------------------------------------- pairwise family
    def _pair_round(self, cells, t):
        p, rng = self.p, self.rng
        dt = p.dt
        cell_of = np.full(p.N, -1)
        dom_of = np.full(p.N, -1)
        for ci, (g, d) in enumerate(cells):
            cell_of[g] = ci
            dom_of[g] = d
        # break connections whose peers left the cell or timed out
        for i in np.flatnonzero(self.partner >= 0):
            j = self.partner[i]
            if cell_of[i] < 0 or cell_of[i] != cell_of[j] or self.conn_left[i] <= 0:
                self._drop(i, t)
        # load per domain: connections share domain goodput; adverts share primaries
        doms = {}
        for g, d in cells:
            doms.setdefault(d, []).append(g)
        int_frac = getattr(self.env, "int_frac", 1.0)
        for d, gs in doms.items():
            allg = np.concatenate(gs)
            part = allg[self.can_tx[allg]]
            free = part[self.partner[part] < 0]
            # connectable advertising + CONNECT_IND, rate-controlled like HYBRID
            R_target = p.G_target / p.tau_p / max(int_frac, 1e-9)
            n_fl = int((self.adv[allg] == FLOOD).sum())
            R_ev = min(R_target, len(free) * p.adv_rate) + n_fl * p.flood_rate
            Gp = R_ev * p.tau_p * int_frac
            self.m["G_sum"] += Gp; self.m["G_n"] += 1; self.m["G_max"] = max(self.m["G_max"], Gp)
            p_conn = math.exp(-2 * Gp) * (1 - p.p_loss)
            # each new connection consumes ~1/scan_duty connectable advertising events
            attempts = min(len(free) // 2, int(R_target * dt * float(np.mean(p.scan_duty))) + 1)
            for g in gs:
                fr = g[self.can_tx[g] & (self.partner[g] < 0) & self.honest[g]
                       & (self.cool_until[g] <= t)]
                if len(fr) < 2:
                    continue
                rng.shuffle(fr)
                n_try = min(len(fr) // 2, max(1, attempts * len(fr) // max(1, len(free))))
                for k in range(n_try):
                    a, b = int(fr[2 * k]), int(fr[2 * k + 1])
                    if rng.random() < p_conn:
                        self._connect(a, b)
            active = [i for i in allg if self.partner[i] > i]
            if not active:
                continue
            # flooders' AUX PDUs occupy the same 37 channels as connection data
            Ga_fl = n_fl * p.flood_rate * self.chainlen * p.tau_a * int_frac / p.n_sec
            surv = math.exp(-2 * Ga_fl)
            per_pair = min(p.link_Bps * surv, p.domain_Bps * surv / len(active))
            for a in active:
                self._pair_transfer(int(a), int(self.partner[a]), per_pair, t)

    def _connect(self, a, b):
        p = self.p
        self.partner[a], self.partner[b] = b, a
        self.conn_left[[a, b]] = p.conn_max_s
        self.setup_left[[a, b]] = p.conn_setup_s
        self.m["conns"] += 1
        if p.strategy == "AE_INV":
            inv = 8 * (self.libn[a] + self.libn[b]) + 64
            self.inv_left[[a, b]] = inv
            self.m["bytes_inventory"] += inv
        for s, r in ((a, b), (b, a)):
            if self.can_fwd[s]:
                c = np.flatnonzero(self.have[s])
            else:
                c = np.array([self.own[s]]) if self.own[s] >= 0 else np.array([], int)
            if p.strategy == "AE_INV":
                c = c[~self.have[r, c]]
            self.queue[s] = self.rng.permutation(c)
            self.qpos[s] = 0

    def _drop(self, i, t=None):
        j = self.partner[i]
        for x in (i, j):
            if x >= 0:
                self.partner[x] = -1
                self.queue.pop(x, None)
                if t is not None:
                    self.cool_until[x] = t + self.p.conn_cooldown_s

    def _pair_transfer(self, a, b, Bps, t):
        p = self.p
        dt = p.dt
        su = min(dt, self.setup_left[a])
        self.setup_left[[a, b]] -= su
        budget = Bps * (dt - su)
        self.conn_left[[a, b]] -= dt
        self.tx_time[[a, b]] += (dt - su) * 0.5 * Bps / 250_000.0   # radio-on ~ bytes/2Mbps
        if p.strategy == "AE_INV" and self.inv_left[a] > 0:
            use = min(budget, self.inv_left[a])
            self.inv_left[[a, b]] -= use
            budget -= use
        if budget <= 0:
            return
        progressed = False
        for s, r in ((a, b), (b, a)):
            bud = budget / 2
            q = self.queue.get(s)
            if q is None:
                continue
            pos = self.qpos[s]
            while pos < len(q) and bud > 0:
                it = int(q[pos])
                if self.have[r, it]:
                    cost = p.dup_cost
                    self.m["bytes_wasted"] += cost
                else:
                    cost = self.obj_bytes
                    if bud < cost:
                        break
                    if self._store_unicast(r, it, t):
                        progressed = True
                bud -= cost
                self.m["bytes_unicast"] += cost
                pos += 1
            self.qpos[s] = pos
        done = all(self.qpos.get(x, 0) >= len(self.queue.get(x, [])) for x in (a, b))
        if done:
            self._drop(a, t)

    def _store_unicast(self, r, it, t):
        if (self.cap < 10 ** 9 or self.p.admission in ("quota", "quota_strata")):
            if not self._admit(r, t):
                return False
            self._note_admitted(r, it)
        self.have[r, it] = True
        self.prog[r, it] = self.full
        self.libn[r] += 1
        self.sig[r, self.bucket[it]] += self.rkey[it]
        return True

    # ------------------------------------------------------------- main loop
    def run(self):
        p = self.p
        t = 0.0
        next_sample = 0.0
        pairwise = p.strategy in ("PAIRWISE", "AE_INV")
        rounds = int(round(p.T / p.dt))
        self._record_cov(0.0)
        for _ in range(rounds):
            cells = self.env.cells(t)
            for g, _ in cells:
                self.contact_time[g] += p.dt
            self.tokens = np.minimum(self.p.quota_per_min, self.tokens + p.quota_per_min * p.dt / 60)
            if pairwise:
                self._pair_round(cells, t)
            else:
                self._broadcast_round(cells, t)
            t += p.dt
            if t >= next_sample:
                self._record_cov(t)
                self.series.append(self._snapshot(t))
                next_sample += p.sample_s
        return self.summary()

    def _completeness(self):
        rec = self.honest
        return self.have[rec].sum(1) / max(1, self.M)

    def _snapshot(self, t):
        c = self._completeness()
        return dict(t=t, mean=float(c.mean()), p10=float(np.percentile(c, 10)),
                    listen_mean=float(c[self.mode[self.honest] == LISTEN].mean())
                    if (self.mode[self.honest] == LISTEN).any() else float("nan"))

    def summary(self):
        p, m = self.p, self.m
        c = self._completeness()
        cov = self.have[self.honest].mean(0)
        jain = float(cov.sum() ** 2 / (len(cov) * (cov ** 2).sum())) if cov.sum() > 0 else 0.0
        hm = self.mode[self.honest]
        tx_ev = m["tx_events"]
        # energy (nRF52840 radio currents [spec]; CPU, regulator excluded)
        if p.strategy in ("PAIRWISE", "AE_INV"):
            active_rx = self.duty * self.contact_time
        else:
            active_rx = self.rx_on
        rx_on = active_rx + p.idle_duty * (p.T - self.contact_time)
        mAh_rx = rx_on * 6.26 / 3600
        mAh_tx = self.tx_time * 6.40 / 3600
        e = (mAh_rx + mAh_tx)[self.honest]
        def lat(a):
            arr = self.first_cov[a]
            return float(np.nanmedian(arr)) if np.isfinite(arr).any() else float("nan"), \
                float(np.mean(np.isfinite(arr)))
        out = dict(
            params=asdict(p), M=self.M, frames_per_pamphlet=self.F,
            completeness_mean=float(c.mean()), completeness_p10=float(np.percentile(c, 10)),
            completeness_min=float(c.min()),
            listen_mean=float(c[hm == LISTEN].mean()) if (hm == LISTEN).any() else None,
            exchange_mean=float(c[hm == EXCHANGE].mean()) if (hm == EXCHANGE).any() else None,
            courier_mean=float(c[hm == COURIER].mean()) if (hm == COURIER).any() else None,
            t50_median=lat(0.5)[0], frac_reach50=lat(0.5)[1],
            t80_median=lat(0.8)[0], frac_reach80=lat(0.8)[1],
            t90_median=lat(0.9)[0], frac_reach90=lat(0.9)[1],
            jain_coverage=jain,
            tx_events=tx_ev, sdb_events=m["sdb_events"], junk_events=m["junk_events"],
            new_fragment_receptions=m["new_bits"],
            receptions_per_tx_event=(m["new_bits"] / tx_ev) if tx_ev else None,
            bytes_unicast=m["bytes_unicast"], bytes_wasted=m["bytes_wasted"],
            bytes_inventory=m["bytes_inventory"], connections=m["conns"],
            G_mean=m["G_sum"] / max(1, m["G_n"]), G_max=m["G_max"],
            max_library=int(self.libn.max()), mean_junk=float(self.junk[self.honest].mean()),
            honest_drops_full=m["honest_drops_full"], honest_drops_quota=m["honest_drops_quota"],
            honest_evicted=m.get("honest_evicted", 0),
            energy_mAh_mean=float(e.mean()), energy_mAh_p90=float(np.percentile(e, 90)),
            tx_radio_s_mean=float(self.tx_time[self.honest].mean()),
            series=self.series,
        )
        return out


def run(**kw):
    p = Params(**kw)
    t0 = time.time()
    out = Sim(p).run()
    out["wall_s"] = time.time() - t0
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for f, v in asdict(Params()).items():
        if isinstance(v, bool):
            ap.add_argument("--" + f, type=lambda s: s.lower() in ("1", "true", "yes"), default=v)
        elif isinstance(v, tuple):
            ap.add_argument("--" + f, type=lambda s: tuple(float(x) for x in s.split(",")), default=v)
        else:
            ap.add_argument("--" + f, type=type(v), default=v)
    ap.add_argument("--out", default="-")
    a = vars(ap.parse_args(argv))
    out_path = a.pop("out")
    res = run(**a)
    js = json.dumps(res, indent=1, default=float)
    if out_path == "-":
        res.pop("series")
        res.pop("params")
        print(json.dumps(res, indent=1, default=float))
    else:
        open(out_path, "w").write(js)


if __name__ == "__main__":
    main()
