#!/usr/bin/env python3
"""Closed-form cost model of set-reconciliation options for ZEMIZDAT (THEORETICAL ESTIMATE).

For library size M and difference |D| (items the sender has that the receiver lacks, assumed
one-sided for the formulas), estimate: control bytes on air, interactive round trips, working
RAM, persistent index, and what an eavesdropper learns. Content bytes (1068 B per 1 KiB
pamphlet) are reported alongside so overheads can be judged against payload.
"""
import json
import math
import os

FRAME_PAYLOAD = 220
SID = 8
OBJ = 1068


def frames(nbytes):
    return math.ceil(nbytes / FRAME_PAYLOAD)


def costs(M, D):
    out = {}
    # 1 sorted sid64 inventory (exact); both sides send
    b = 2 * SID * M
    out["sorted_inventory"] = dict(bytes=b, rtt=1, ram=256, index=12 * M, fp=0.0,
                                   leak="entire library, verbatim")
    # 2 fixed 64-bucket digests (salted, non-linear) + sid lists of differing buckets
    per_bucket = SID * M / 64
    nb = min(64, D)  # worst case: each differing item in a different bucket
    b = 2 * 168 + nb * per_bucket
    out["bucket_digest+lists"] = dict(bytes=round(b), rtt=2, ram=512, index=12 * M, fp=2 ** -16,
                                      leak="which buckets differ; sid lists of those buckets")
    # 3 16-ary Merkle prefix tree; per level, 16 child hashes of 8 B per differing node
    levels = max(1, math.ceil(math.log(max(M, 2), 16)))
    b = D * levels * 16 * SID
    out["merkle16"] = dict(bytes=b, rtt=levels, ram=16 * SID * 2, index=12 * M + 16 * M // 15 * SID,
                           fp=0.0, leak="hash tree of library (testable against known items)")
    # 4 Bloom filter of whole library, eps = 1%
    eps = 0.01
    bits = -M * math.log(eps) / (math.log(2) ** 2)
    out["bloom_1pct"] = dict(bytes=round(bits / 8), rtt=1, ram=round(bits / 8), index=12 * M, fp=eps,
                             leak="membership of ANY known item testable")
    # 5 Cuckoo filter, ~ (log2(1/eps)+3)/0.95 bits per item
    cb = M * (math.log2(1 / eps) + 3) / 0.95
    out["cuckoo_1pct"] = dict(bytes=round(cb / 8), rtt=1, ram=round(cb / 8), index=12 * M, fp=eps,
                              leak="membership of ANY known item testable")
    # 6 fixed-size IBLT sized from a difference estimator (strata estimator ~ 16 strata x 80 cells)
    cell = 1 + SID + 4
    est = 16 * 80 * cell
    b = est + math.ceil(1.5 * D + 10) * cell
    out["iblt+estimator"] = dict(bytes=b, rtt=2, ram=b, index=12 * M, fp=1e-6,
                                 leak="decodes U\\S for an observer holding U when |U\\S| small")
    # 7 rateless IBLT (Yang et al., SIGCOMM 2024): ~1.35 |D| coded symbols, streamed
    b = math.ceil(1.35 * D + 5) * cell
    out["rateless_iblt"] = dict(bytes=b, rtt=1, ram=max(1, D) * cell * 2, index=12 * M + 0, fp=1e-6,
                                leak="same as IBLT")
    # 8 no reconciliation: demand-agnostic carousel (broadcast). Control bytes 0; waste appears as
    # redundant content (see simulator).
    out["carousel_only"] = dict(bytes=0, rtt=0, ram=0, index=12 * M, fp=None,
                                leak="items you transmit (inherent to forwarding)")
    for v in out.values():
        v["frames"] = frames(v["bytes"])
        v["overhead_vs_content"] = round(v["bytes"] / max(1, D * OBJ), 3)
    return out


def main():
    table = {}
    for M in (50, 100, 1000, 3000, 10000, 100000):
        for D in (1, 10, 100, M // 2, M):
            if D > M:
                continue
            table[f"M={M},D={D}"] = costs(M, D)
    out = os.path.join(os.path.dirname(__file__), "..", "results", "sync_costs.json")
    json.dump(table, open(out, "w"), indent=1)
    # compact print
    meths = list(next(iter(table.values())).keys())
    print("bytes on air (both directions) | rtt  -- per (M, |D|)")
    print("%-16s" % "M,D" + "".join("%17s" % m[:16] for m in meths))
    for k, row in table.items():
        print("%-16s" % k + "".join("%11d|%-5s" % (row[m]["bytes"], row[m]["rtt"]) for m in meths))
    print("\nRAM needed for the structure (bytes) at |D|=10:")
    for M in (50, 1000, 3000, 100000):
        r = table[f"M={M},D=10"]
        print("  M=%6d " % M + "  ".join("%s=%d" % (m[:10], r[m]["ram"]) for m in meths))


if __name__ == "__main__":
    main()
