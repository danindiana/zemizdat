# 09 · Technical specification (index)

The normative specification is split by concern; this page is the reading order for a firmware
engineer.

| Read | File | Normative content |
|---|---|---|
| 1 | `03_protocol/ZEMIZDAT_PROTO_1.0.md` | constants, modes, discovery/privacy rules, rate control, burst mode, carousel scheduling, receive path, budgets, admission, versioning, failure handling, radio-API dependencies |
| 2 | `03_protocol/wire_format.md` | CPO, identifier, FRAG/MANIFEST/SDB layouts, BLE/ESP-NOW encapsulation, worked byte-exact examples, parser rules |
| 3 | `03_protocol/storage.md` | sector/record layout, commit protocol, mount/recovery, GC, index, endurance |
| 4 | `03_protocol/state_machine.md` | device states, per-mode behaviour, transmit-permission check |
| 5 | `03_protocol/synchronization.md` | why no reconciliation in v1; optional beacons |
| 6 | `03_protocol/security.md` | data-plane mechanisms; governance plane (keys, thresholds, rollback, updates) |
| 7 | `03_protocol/reference_py/zmproto.py` | executable reference: codec, reassembly, store |
| 8 | `03_protocol/reference_c/zm_core.[ch]` | portable C99 receive path; `make test` |

Conformance: an implementation is conformant to the wire format if it reassembles every vector in
`reference_c/vectors.txt` to the listed ids and rejects every malformed frame class in
`reference_py/test_zmproto.py::test_parser_rejects_bad_inputs`.

Parts that are **not** yet specified to implementation level, by design or for lack of evidence:
the rate controller's interference observable (`κ_INT`, Q1), UI, and the v2 extensions (author
signatures, rateless-IBLT courier sync, event manifests).
