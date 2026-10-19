"""Emit test vectors (hex frames + expected completed ids) from the Python reference."""
import random, sys
sys.path.insert(0, "../reference_py")
import zmproto as z

rng = random.Random(42)
lines = []
for i, n in enumerate([5, 34, 207, 208, 300, 1024, 2500, 4052]):
    body = ("".join(rng.choice("abcdefghij αβγ€") for _ in range(n))).encode()[:n]
    while True:
        try:
            body.decode(); break
        except UnicodeDecodeError:
            body = body[:-1]
    cpo = z.encode_cpo(body)
    cid = z.content_id(cpo)
    fr = z.burst(cpo)
    if len(fr) > 1:
        man, frags = fr[0], fr[1:]
        rng.shuffle(frags)
        fr = [man] + frags
    for f in fr:
        lines.append("F " + f.hex())
    lines.append("E " + cid.hex())
ids = [z.content_id(z.encode_cpo(f"s{i}".encode())) for i in range(200)]
salt = b"\x01\x02\x03\x04"
sdb = z.frame_sdb(ids, congestion=2, salt=salt)
lines.append("S " + sdb.hex())
d = z.bucket_digests(ids, salt)
lines.append("D " + " ".join(str(x) for x in d))
per = {}
for c in ids:
    per.setdefault(z.bucket_of(c), []).append(z.sid64(c))
for b in range(z.N_BUCKETS):
    lines.append("B %d %s" % (b, "".join(s.hex() for s in sorted(per.get(b, [])))))
open("vectors.txt", "w").write("\n".join(lines) + "\n")
print(len(lines), "vector lines")
