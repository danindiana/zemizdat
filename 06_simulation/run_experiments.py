#!/usr/bin/env python3
"""Reproducible experiment campaign for ZEMIZDAT-SIM-1.0.

  python3 run_experiments.py --write-configs     # regenerate configs/experiments.json
  python3 run_experiments.py --jobs 2            # run everything not yet in results/runs.jsonl
  python3 run_experiments.py --only A,B          # subset of experiment groups

Each run is keyed by a hash of its parameters; reruns are skipped, so the campaign can be
interrupted and resumed. Seeds are explicit; results are deterministic for a given numpy.
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import simulator as S  # noqa: E402

RES = os.path.join(HERE, "results", "runs.jsonl")
CFG = os.path.join(HERE, "configs", "experiments.json")
STRATS = ["BCAST", "BCAST_RC", "PAIRWISE", "AE_INV", "HYBRID"]


def experiments():
    ex = []

    def add(group, seeds, **kw):
        for s in seeds:
            ex.append(dict(group=group, params=dict(kw, seed=s)))

    # A: population sweep, single auditorium, fixed density, all strategies
    for N in (10, 50, 100, 500, 1000, 3000, 5000):
        seeds = (1, 2, 3) if N <= 1000 else ((1, 2) if N == 3000 else (1,))
        for st in STRATS:
            add("A", seeds, N=N, strategy=st, env="auditorium", T=3600, sample_s=60)
        if N in (100, 1000):
            add("A", (1,), N=N, strategy="ORACLE", env="auditorium", T=3600, sample_s=60)
    # B: cooperative fraction x adversary type
    for adv in ("flood", "blackhole", "suppress"):
        for h in (1.0, 0.99, 0.95, 0.9, 0.8):
            if adv != "flood" and h == 1.0:
                continue
            for st in ("HYBRID", "AE_INV", "BCAST_RC"):
                add("B", (1, 2, 3), N=500, h=h, adversary=adv, strategy=st, T=1800, sample_s=60)
    for h in (0.95, 0.9, 0.8):
        add("B", (1, 2, 3), N=500, h=h, adversary="suppress", strategy="HYBRID",
            verified_suppression=False, T=1800, sample_s=60)
    # C: environments 2 and 3
    for st in ("HYBRID", "BCAST_RC", "AE_INV", "PAIRWISE"):
        add("C", (1, 2) if st == "HYBRID" else (1,), N=3000, env="rooms", rooms=6,
            room_move_per_min=0.05, strategy=st, T=3600, dt=1.0, sample_s=120)
        add("C", (1, 2), N=3000, env="city", strategy=st, T=86400, dt=30.0, sample_s=1800)
    for dw in (False,):
        add("C", (1, 2), N=3000, env="city", strategy="HYBRID", digest_weight=dw,
            T=86400, dt=30.0, sample_s=1800)
        add("C", (1,), N=3000, env="rooms", rooms=6, room_move_per_min=0.05, strategy="HYBRID",
            sdb=False, T=3600, sample_s=120)
    add("C", (1, 2), N=3000, env="city", strategy="HYBRID", burst_n=0, T=86400, dt=30.0, sample_s=1800)
    # D: interdiction (barbell); bridges present vs silenced
    for cut in (False, True):
        for b in (2, 8):
            add("D", (1, 2, 3), N=400, env="barbell", bridges=b, cut_bridges=cut,
                strategy="HYBRID", T=7200, sample_s=120)
    # E: storage exhaustion under flooding, finite capacity
    for adm, q in (("naive", 60.0), ("quota", 60.0), ("quota", 150.0), ("strata", 60.0),
                   ("quota_strata", 150.0)):
        for h in (1.0, 0.98, 0.95):
            add("E", (1, 2, 3), N=500, h=h, adversary="flood", capacity=600, admission=adm,
                quota_per_min=q, strategy="HYBRID", T=3600, sample_s=120, flood_rate=5.0)
    # F: sensitivity (N=1000 auditorium, 30 min), HYBRID vs AE_INV
    sens = [("scan_duty", (0.1, 0.1, 0.1)), ("scan_duty", (1.0, 1.0, 1.0)),
            ("p_loss", 0.0), ("p_loss", 0.3), ("chain", 1), ("r_rx", 5.0), ("r_rx", 20.0),
            ("host_rate", 50.0), ("host_rate", 1000.0), ("domain_Bps", 500_000.0),
            ("domain_Bps", 4_000_000.0), ("link_Bps", 10_000.0), ("conn_setup_s", 1.5),
            ("mode_mix", (0.6, 0.2, 0.2)), ("mode_mix", (0.0, 0.0, 1.0)), ("body_bytes", 4000),
            ("body_bytes", 200), ("age_weight", False), ("digest_weight", False)]
    for st in ("HYBRID", "AE_INV"):
        add("F", (1, 2), N=1000, strategy=st, T=1800, sample_s=60)        # baseline
        for k, v in sens:
            if st == "AE_INV" and k in ("chain", "host_rate", "age_weight", "digest_weight"):
                continue
            if st == "HYBRID" and k in ("domain_Bps", "link_Bps", "conn_setup_s"):
                continue
            add("F", (1, 2), N=1000, strategy=st, T=1800, sample_s=60, **{k: v})
    # G: can the rate controller see its interference domain? (spec §4 weakness)
    for scope, k in (("domain", 1.0), ("cell", 1.0), ("cell", 3.0), ("cell", 10.0)):
        add("G", (1, 2), N=1000, strategy="HYBRID", rc_scope=scope, rc_kappa=k, T=1800, sample_s=60)
    # H: the configuration actually specified for v1 (beacons off) — population sweep + city
    for N in (100, 500, 1000, 3000, 5000):
        seeds = (1, 2, 3) if N <= 1000 else ((1, 2) if N == 3000 else (1,))
        add("H", seeds, N=N, strategy="HYBRID", sdb=False, env="auditorium", T=3600, sample_s=60)
    add("H", (1, 2), N=3000, env="city", strategy="HYBRID", sdb=False, T=86400, dt=30.0, sample_s=1800)
    return ex


def key(e):
    return hashlib.sha1(json.dumps(e["params"], sort_keys=True, default=list).encode()).hexdigest()[:16]


def work(e):
    t0 = time.time()
    try:
        out = S.run(**e["params"])
    except Exception as exc:  # record failures instead of hiding them
        return dict(key=key(e), group=e["group"], params=e["params"], error=repr(exc))
    out.pop("params", None)
    out.update(key=key(e), group=e["group"], params=e["params"], wall_s=time.time() - t0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--only", default="")
    ap.add_argument("--write-configs", action="store_true")
    a = ap.parse_args()
    ex = experiments()
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    with open(CFG, "w") as fh:
        json.dump(ex, fh, indent=1, default=list)
    if a.write_configs:
        print(len(ex), "runs written to", CFG)
        return
    done = set()
    if os.path.exists(RES):
        for line in open(RES):
            try:
                r = json.loads(line)
                if "error" not in r:
                    done.add(r["key"])
            except json.JSONDecodeError:
                pass
    groups = set(a.only.split(",")) if a.only else None
    todo = [e for e in ex if key(e) not in done and (groups is None or e["group"] in groups)]
    # cheap first so partial campaigns are still informative
    todo.sort(key=lambda e: e["params"].get("N", 0) * e["params"].get("T", 3600) / e["params"].get("dt", 1.0))
    print(f"{len(ex)} runs defined, {len(done)} done, {len(todo)} to run", flush=True)
    os.makedirs(os.path.dirname(RES), exist_ok=True)
    with mp.Pool(a.jobs, maxtasksperchild=4) as pool, open(RES, "a") as fh:
        for i, r in enumerate(pool.imap_unordered(work, todo)):
            fh.write(json.dumps(r, default=float) + "\n")
            fh.flush()
            tag = "ERR " + r["error"] if "error" in r else "mean=%.3f" % r["completeness_mean"]
            print(f"[{i+1}/{len(todo)}] {r['group']} {r['params'].get('strategy')} N={r['params'].get('N')} "
                  f"{tag} {r.get('wall_s', 0):.0f}s", flush=True)


if __name__ == "__main__":
    main()
