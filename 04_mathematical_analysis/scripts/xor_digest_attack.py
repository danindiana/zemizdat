#!/usr/bin/env python3
"""Demonstration: Gemini's proposed SDB (64 buckets x 32-bit XOR folds of sid64) is LINEAR over
GF(2), so an eavesdropper who knows the pamphlet universe U recovers a courier's library from a
single beacon whenever buckets hold <= 32 items, and learns 32 bits per bucket otherwise.

EXECUTED RESULT (simulation of the attack on synthetic data, not on hardware).
"""
import hashlib
import json
import os
import random

import numpy as np


def sid(i):
    return hashlib.sha256(b"pamphlet-%d" % i).digest()


def fold32(d):        # Gemini: bucket_xor[b] ^= low 32 bits of sid64
    return int.from_bytes(d[:8], "little") & 0xFFFFFFFF


def bucket(d):        # Gemini: top 6 bits of byte 0
    return d[0] >> 2


def gf2_solve(A, b):
    """Return (particular solution or None, number of free variables)."""
    A = A.copy() % 2
    b = b.copy() % 2
    m, n = A.shape
    row = 0
    piv = []
    for col in range(n):
        r = next((i for i in range(row, m) if A[i, col]), None)
        if r is None:
            continue
        A[[row, r]] = A[[r, row]]
        b[[row, r]] = b[[r, row]]
        for i in range(m):
            if i != row and A[i, col]:
                A[i] ^= A[row]
                b[i] ^= b[row]
        piv.append(col)
        row += 1
        if row == m:
            break
    if any(b[i] and not A[i].any() for i in range(m)):
        return None, None
    x = np.zeros(n, np.uint8)
    for i, c in enumerate(piv):
        x[c] = b[i]
    return x, n - len(piv)


def attack(M, frac, seed):
    rng = random.Random(seed)
    U = [sid(i) for i in range(M)]
    S = set(i for i in range(M) if rng.random() < frac)
    folds = [0] * 64
    for i in S:
        folds[bucket(U[i])] ^= fold32(U[i])
    recovered = 0
    free_total = 0
    exact_buckets = 0
    for b in range(64):
        items = [i for i in range(M) if bucket(U[i]) == b]
        A = np.array([[(fold32(U[i]) >> k) & 1 for i in items] for k in range(32)], np.uint8)
        y = np.array([(folds[b] >> k) & 1 for k in range(32)], np.uint8)
        x, free = gf2_solve(A, y)
        free_total += free
        if free == 0:
            exact_buckets += 1
            recovered += sum(1 for j, i in enumerate(items) if x[j] == (i in S))
    return dict(M=M, items_per_bucket=round(M / 64, 1), library_size=len(S),
                buckets_fully_recovered=exact_buckets, free_bits_total=free_total,
                items_recovered_exactly=recovered)


def main():
    res = [attack(M, 0.6, s) for M in (300, 1000, 2000, 3000, 10000) for s in (1,)]
    for r in res:
        print(r)
    out = os.path.join(os.path.dirname(__file__), "..", "results", "xor_digest_attack.json")
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
