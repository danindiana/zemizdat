# 07 · Threat model

## Assets

1. Integrity of stored pamphlets (bytes match their id).
2. Availability of dissemination (honest pamphlets keep spreading).
3. Device resources (storage, battery, airtime share).
4. Participant privacy: presence, identity, location history, library contents, authorship.
5. Firmware integrity (governance plane).

## Adversary capabilities considered

| Capability | Examples | In scope |
|---|---|---|
| A1 listen anywhere in range, indefinitely, with better antennas | passive surveillance, direction finding | yes |
| A2 transmit arbitrary frames, valid or malformed | modified firmware, SDR | yes |
| A3 generate unlimited valid objects | scripts on a laptop | yes |
| A4 unlimited identities | address rotation (free in BLE) | yes |
| A5 occupy the channel | ignore rate control, continuous transmission, jamming | yes, as a model (packet loss / channel unavailability). No jamming equipment is designed or used here. |
| A6 seize or buy devices, read their flash | physical access | yes |
| A7 compromise < t firmware signing keys | insider, theft | yes |
| A8 compromise ≥ t signing keys | coordinated insider / coercion | yes, residual risk |
| A9 break SHA-256 / Ed25519, 64-bit second preimages | — | no |
| A10 control the physical movement of participants | checkpoints, closing exits | yes (graph interdiction, `04_mathematical_analysis/temporal_graphs.md`) |

## Honest participants

Run unmodified firmware, may be any of LISTEN / EXCHANGE / COURIER, may have small or large
libraries, may stop participating at any time. Cooperation is a **parameter** `h` (fraction of
devices that are honest), not a claim about any real population.

## Security properties claimed (and their limits)

| Property | Claim | Against |
|---|---|---|
| integrity | unconditional (I2, I9) | A2–A4 |
| memory safety of the receive path | tested, not proven (ASan/UBSan fuzzing) | A2 |
| bounded resource consumption per device | unconditional (I3, I4, budgets) | A2–A5 |
| availability | **conditional** (liveness.md); fails under A5 and A10 by Theorems C, H | — |
| retention of honest pamphlets | **bounded damage only** (Theorem D) | A3+A4 |
| LISTEN presence privacy | passive scanning emits no RF (to verify, E-L) | A1 |
| library privacy | **only for LISTEN**; COURIER/EXCHANGE disclose what they send; beacons disclose bucket equality | A1 |
| unlinkability across time | address/salt rotation defeats address-based linking; **content-based linking of couriers remains** | A1 |
| authorship anonymity | no author field and no hop count in v1; but the *first sighting* of a new id reveals where it first appeared, and an A1 observer with direction finding can locate the first transmitter. Mitigation (spec §5 option): "release in crowd" — an author's device starts sending a new pamphlet only when the observed event rate indicates many transmitters nearby. Bounded, not solved. | A1 |
| firmware integrity | threshold + owner consent; fails if ≥ t keys and owner consent are both obtained | A7, A8 |

## Explicitly out of scope

Truth of content; legality of content in any jurisdiction; protection of a device owner from
coercion; side channels on the MCU; supply-chain implants in the radio silicon.
