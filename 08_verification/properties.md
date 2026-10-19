# 08 · Properties and how each is checked

| ID | Property | Kind | Checked by | Status |
|---|---|---|---|---|
| I1 | ≤ 1 copy per id (logical) | safety | `test_store_*`, power-cut tests; C re-delivery 46/46 rejected | **executed** |
| I2 | committed ⇒ hashes to id | safety | fuzz 2 M frames (0 invalid completions); mount re-hash | **executed** |
| I3 | static memory bound | safety | `sizeof(zm_rx)` = 17 428 B; ASan/UBSan fuzz | **executed (host)**; on-target stack measurement pending |
| I4 | capacity respected | safety | store capacity test; simulator capacity test | **executed** |
| I5 | no TX without ORIG/FWD | safety | simulator test; code structure; **E-L** on silicon | sim executed; silicon pending |
| I6 | crash consistency | safety | every-byte power cuts incl. GC (Python NOR model); **E7** | model executed; silicon pending |
| I7 | dedup survives budget reset | safety | by construction | argued |
| I8 | offline operation | safety | inspection (no network I/O in data plane) | argued |
| I9 | per-chunk authenticity | safety | forged-fragment tests; C fuzz | **executed** |
| I10 | suppression requires verified bytes | safety | by construction; simulator showed no effect of the attack at N = 500 | argued |
| L1 | eventual dissemination under (C1)(C2) | liveness | proof; simulator groups A, C | proved (conditional) + simulated |
| L2 | impossible without recurrent cut contact | liveness | proof; simulator group D | proved + simulated |
| P1 | listener receives without transmitting | functional | simulator (LISTEN mean); **E2** | simulated |
| P2 | rate control holds load near target with unknown population | performance | simulator (idealised); **E5** | **open** — controller observability unresolved |
| P3 | parser rejects malformed frames | robustness | `test_parser_*`, C fuzz | **executed** |
| P4 | Python and C agree byte-for-byte | conformance | `make test` vectors | **executed** |

How to re-run everything that is executable:

```bash
cd 03_protocol/reference_py && python3 -m pytest -q          # 31 tests
cd ../reference_c && make test                               # vectors + 2M-frame fuzz, ASan/UBSan
cd ../../06_simulation && python3 -m pytest -q tests         # 14 tests
python3 run_experiments.py --jobs 2 && python3 analyze.py    # full campaign (hours)
cd ../04_mathematical_analysis/scripts && python3 airtime_model.py && python3 sync_costs.py \
   && python3 xor_digest_attack.py
```
