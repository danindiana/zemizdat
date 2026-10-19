# ZEMIZDAT_ARGON — engineering investigation of the ZEMIZDAT communications problem

Mission brief: `MISSION.md` (ZEMIZDAT-ARGON-1.0). Start with **`09_final/EXECUTIVE_VERDICT.md`**.

## What is in here

| Dir | Contents | Kind of evidence |
|---|---|---|
| `01_formal_model/` | system definition, invariants I1–I10, conditional liveness, impossibility results A–J | proofs/arguments; links to executed tests |
| `02_candidate_architectures/` | broadcast, pairwise anti-entropy, hybrid, store-carry-forward, comparison + verdicts | analysis + simulation |
| `03_protocol/` | ZEMIZDAT-PROTO-1.0 spec, wire format, state machine, sync, storage, security/governance; **executable references** in Python and C | spec + executed code |
| `04_mathematical_analysis/` | storage/communication bounds, temporal graphs, convergence, uncertainty; `scripts/` + `results/` | calculations (executed scripts) |
| `05_hardware/` | UNO R4 WiFi, ESP32-S3, nRF52840, battery budget, BOM | datasheet facts + labelled estimates |
| `06_simulation/` | simulator, 377-run campaign, tests, results, figures | simulation |
| `07_adversarial_review/` | threat model, 15 counterexamples, failure matrix, mitigations | analysis + simulation |
| `08_verification/` | hardware test plan E1–E7, properties, acceptance tests, evidence gaps | plan (nothing run on hardware) |
| `09_final/` | verdict, architecture decision, spec index, research questions, prototype plan, next action, audit of the earlier Gemini run | synthesis |

## Labels used everywhere

**[spec]** manufacturer/standard document · **[executed]** checked by code in this tree ·
**[simulated]** simulator output · **[estimate]** calculation with stated assumptions ·
**[assumption]** to be replaced by experiment. **No hardware measurement exists yet.**

## Re-run everything

```bash
cd 03_protocol/reference_py && python3 -m pytest -q            # 31 tests (codec, reassembly, every-byte power cuts)
cd ../reference_c && make test                                 # C vs Python vectors + 2M-frame fuzz (ASan/UBSan)
cd ../../04_mathematical_analysis/scripts && python3 airtime_model.py && python3 sync_costs.py && python3 xor_digest_attack.py
cd ../../06_simulation && python3 -m pytest -q tests && python3 run_experiments.py --jobs 2 && python3 analyze.py
```

Requirements: Python ≥ 3.11, numpy ≥ 2, matplotlib, pytest; gcc/clang with sanitizers.
