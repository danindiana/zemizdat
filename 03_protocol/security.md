# 03 · Security: data plane and governance plane

Threat model: `07_adversarial_review/threat_model.md`. This file specifies mechanisms.

## Part A — Data plane

### A1. Minimal cryptography (v1)

| Operation | Primitive | Where |
|---|---|---|
| content id, chunk leaves | SHA-256 (SoC engine on ESP32-S3 / nRF52840 CC310) | every chunk received, every commit, every mount |
| beacon digests (optional) | SHA-256 over salt ‖ sids | per beacon sent/received |
| randomness (addresses, salts, offsets, jitter) | hardware TRNG | scheduler |

No signatures, no keys, no encryption in the v1 data plane. Rationale: the data plane's
security goals are integrity (met by content addressing), availability under bounded abuse
(met by local limits), and privacy (met by not having identities). Encryption would protect
nothing — every pamphlet is meant for everyone in range — and keys would create identities.

### A2. Input validation

Normative parser rules in `wire_format.md` §7. Evidence: 2 M mutated frames, ASan + UBSan,
no memory error, no invalid completion [executed]. The reference C has no dynamic allocation
and no recursion.

### A3. Abuse limits (all local, all content-neutral)

`CPO_MAX`, `K_SLOT`, slot timeout, admission token bucket, old-item eviction, transmit
budget, battery thresholds, user tombstones. None depends on knowing who sent what.

### A4. What the data plane explicitly does NOT do

* No reputation, no blocklists by sender (no stable senders exist; Sybil makes them moot).
* No content filtering by the firmware (content-neutral by design). The owner can delete and
  tombstone; that decision is local and never propagated.
* No remote command of any kind is accepted over the data plane.

## Part B — Governance plane (firmware maintenance authority)

### B1. Goals and non-goals

* Goals: authentic, independently verifiable updates; vulnerability fixes; provenance; recovery
  from key compromise; no forced network-wide shutdown.
* Non-goals (MUST NOT exist): remote kill switch, remote content takedown, admission control
  of devices or users, automatic installation without the owner's physical action.
* **Authenticity ≠ trustworthiness.** A correctly signed update proves who released it, not that
  it is benign. Independent verification of *what* was released is provided by reproducible
  builds plus public, append-only release logs that third parties can audit before users accept.

### B2. Two layers of signature

```
Layer 1 (boot):  ROM/bootloader verifies the image against keys fused at manufacture
                 ESP32-S3: Secure Boot V2, RSA-3072-PSS, up to 3 key digests in eFuse,
                           each individually revocable (KEY_REVOKE eFuses)   [spec, ESP-IDF docs]
                 nRF52840: MCUboot with Ed25519 or ECDSA-P256, hardware security counter
                           for downgrade prevention                          [MCUboot docs]
Layer 2 (policy): the RUNNING (already trusted) firmware accepts a candidate image only if
                 a TUF-style targets record for it is signed by ≥ t of n maintainer keys
                 (proposed t = 3, n = 5, Ed25519), the image hash matches, its version is
                 greater than the installed one, and the owner presses the physical button.
                 Only then is it written to the secondary slot for Layer 1 to verify.
```

Why both: Layer 1 alone is a single point of failure (one key, or any one of three, signs
everything). Layer 2 alone does not stop a physical attacker from flashing an image through a
debug or serial-recovery path. Disable JTAG/serial recovery in production (eFuse) so Layer 1
plus Layer 2 is the only path.

### B3. Keys, rotation, compromise

| Event | Response |
|---|---|
| one maintainer key compromised (`< t`) | publish a new root record signed by `t` remaining keys rotating it out; devices learn the new root with the next update they accept; no harm meanwhile (attacker lacks `t`) |
| `≥ t` maintainer keys compromised | a malicious update can be signed. Mitigations: owner-consent gate; public log + reproducible build lets anyone see the bad release before many owners accept it; devices never auto-install. Residual risk: owners who accept quickly. |
| Layer-1 key compromised | revoke that eFuse slot in the next legitimate update (ESP32-S3); remaining slots continue. On nRF52840 with a single MCUboot key: re-provisioning needed → prefer a bootloader with ≥ 2 keys. |
| maintainer authority disappears | devices keep working forever on the installed version (I8); the data-plane protocol is versioned so forks can coexist. |

### B4. Rollback protection

Monotone security counter (ESP-IDF app anti-rollback `secure_version` eFuse; MCUboot hardware
security counter). Only *security* releases bump it, so an owner can still downgrade across
feature releases with the same counter.

### B5. Distributing updates without a network

v1: USB only (owner connects to a computer or phone and transfers a signed bundle). Not over
the BLE carousel: images are ~1 MB (≈ 4 800 chunks) against 4 KiB pamphlets, and an update
channel inside the data plane would make the governance plane a dependency of the data plane
and a target for flooding. v2 option: separate object type with a signed manifest, carried
only by devices whose owners opt in.

### B6. Compatibility

Frame and CPO version fields (`ZEMIZDAT_PROTO_1.0.md` §11) mean an update can add features
without forcing others to update. Devices that never update remain functional participants.

### B7. Compared approaches

| Approach | Used for | Why / why not |
|---|---|---|
| TUF (threshold roles, key rotation via root metadata) | Layer 2 policy | designed for compromise-resilient distribution; only the targets/root subset is needed |
| MCUboot | Layer 1 on nRF52840 | mature; image slots, swap, downgrade prevention |
| Espressif Secure Boot V2 | Layer 1 on ESP32-S3 | ROM-anchored; 3 revocable keys |
| IETF SUIT (RFC 9019/9124 manifests) | possible encoding for the Layer-2 record | standard, but the CBOR/COSE parser is a new attack surface on the MCU; v1 uses a fixed binary record instead |
| Reproducible builds + public log | trust in *content* of releases | the only mechanism here that addresses authenticity ≠ trustworthiness |
