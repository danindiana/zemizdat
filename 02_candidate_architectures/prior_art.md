# 02 · Prior art: open-source projects with similar goals or claims (checked 2026-10-19)

Star counts are from each repo page on the check date. "Overlap" is with ZEMIZDAT's
defining combination: (a) no accounts, servers or stable identities; (b) store-carry-forward
between strangers; (c) receive-only participation; (d) content-addressed, immutable objects;
(e) cheap MCU hardware.

## Summary

**No project found matches the combination.** Each existing system covers some of the
properties and gives up others:

* **Phone apps** get mobility but rely on connections and persistent device identities.
* **LoRa firmware** gets cheap MCUs and range but routes chat messages; it does not distribute an
  immutable collection.
* **DTN stacks** get store-carry-forward but run on IP hosts.
* **Wi-Fi boxes** get anonymous offline sharing but are fixed infrastructure.

The pattern closest to ZEMIZDAT's radio behaviour is Apple Find My / OpenHaystack: bystanders
passively pick up connectionless BLE advertisements. It serves a different purpose.

## Projects

| Project | What it claims | Overlap | Key differences / lessons for us |
|---|---|---|---|
| **bitchat** — [permissionlesstech/bitchat](https://github.com/permissionlesstech/bitchat) (36.6k★, Unlicense) | Offline BLE mesh chat, no accounts; up to 7 hops; store-and-forward queue; Nostr fallback | a, b (partly) | iOS/macOS/Android app. Its own README says its persistent per-device identifier is "observable by nearby radios". Its first release had broken identity authentication: MITM demonstrated by Alex Radocea (Supernetworks), July 2025, and confirmed as fundamental by Trail of Bits. **Lesson:** keep identities out of the data plane, as ZEMIZDAT does. |
| **Bridgefy** (proprietary; cautionary) | Offline mesh messenger promoted for protests | — | Academic analysis ([IACR ePrint 2021/214](https://eprint.iacr.org/2021/214); follow-up at [USENIX Security 2022](https://www.usenix.org/conference/usenixsecurity22/presentation/albrecht)): users could be tracked and social graphs built, anyone could impersonate anyone, and one crafted message could shut down the network. **Lesson:** defensive parsing and no identities. ZEMIZDAT's fuzzed parser and missing sender field address exactly these failure classes. |
| **Rumble** — [Marlinski/Rumble](https://github.com/Marlinski/Rumble) (317★, GPL-3.0) | Delay-tolerant, Twitter-like Android app; store-carry-forward; messages pushed to every device met; prioritised by hashtag, replication density and age; "naturally resistant against censorship" | a, b | **The closest in intent.** It uses pairwise channels (Bluetooth/Wi-Fi), so there is no receive-only mode; it is phone-only; activity is unclear. Its "replication density" priority is the same idea as our least-recently-heard weighting. |
| **Serval Rhizome / LBARD** — [servalproject/lbard](https://github.com/servalproject/lbard) (1★, ~2016–18) | Synchronises Rhizome content-addressed bundles between nodes over low-bandwidth radios; "tree synchronisation" using the XOR of content hashes; priority ranking of missing bundles | b, d | **The closest technically:** content-addressed bundles plus prioritised sync over constrained radios. It is pairwise and peer-to-peer over UHF/HF. Its XOR-of-hashes summary has the same linearity that let our attack recover libraries; it is fine between cooperating peers, but leaks when broadcast. Appears inactive. |
| **Meshtastic firmware** — [meshtastic/firmware](https://github.com/meshtastic/firmware) (8.3k★, GPL-3.0) | Off-grid LoRa mesh messaging, location, telemetry; ESP32, nRF52, RP2040 | e | Same MCU families as our boards. Uses LoRa flooding with channel keys and persistent node IDs, aimed at messaging rather than a pamphlet collection. Useful as a reference for nRF52/ESP32 power management and an active hardware ecosystem (T-Echo, T114). |
| **MeshCore** — [meshcore-dev/MeshCore](https://github.com/meshcore-dev/MeshCore) (3.8k★, MIT) | Lightweight C++ multi-hop routing library for LoRa; companion, repeater and "room server" (a simple BBS for shared posts) roles | e, b (room server) | Its room server resembles a fixed pamphlet board; ZEMIZDAT's equivalent is a stationary COURIER. Fixed roles and LoRa; not anonymous broadcast. MIT licence: portable code to study. |
| **Reticulum LXMF** — [markqvist/lxmf](https://github.com/markqvist/lxmf) (728★) | Message format over Reticulum; message ID = SHA-256 of contents (derivable, not transmitted); **propagation nodes** form a distributed store-and-forward message store | b, d (partly) | Content-derived IDs and a peer-synchronised store, but messages are addressed, signed (Ed25519) and end-to-end encrypted, and it runs on Python hosts. Self-described as not externally audited. |
| **dtn7-rs** — [dtn7/dtn7-rs](https://github.com/dtn7/dtn7-rs) (fork checked: [gh0st42/dtn7-rs](https://github.com/gh0st42/dtn7-rs)) | Bundle Protocol v7 daemon; flooding, epidemic and sink routing | b | The standards-track version of store-carry-forward (BPv7). Its convergence layers are TCP/HTTP over IP, not raw BLE. A possible interoperability target for a v2 gateway. |
| **Berty / Wesh** — [berty/weshnet](https://github.com/berty/weshnet) (251★, Apache-2.0/MIT) | Privacy-first off-grid peer-to-peer toolkit (libp2p, OrbitDB); topics include delay-tolerant networks | a (partly), b | Account-free but key-based group sync between members. Phones, not MCUs. |
| **Briar** — [Bramble spec](https://code.briarproject.org/briar/briar-spec) | Secure messaging over Tor, Wi-Fi or Bluetooth; Bramble Synchronisation Protocol | b (between contacts) | Syncs only between contacts who have exchanged keys, so it does not serve strangers. A strong reference for a well-specified sync protocol. |
| **OpenHaystack** — [seemoo-lab/openhaystack](https://github.com/seemoo-lab/openhaystack) (13.3k★, AGPL-3.0) | ESP32/nRF51 tags broadcast BLE advertisements that bystander iPhones pick up passively | radio pattern only | **Proof that connectionless advertisements reach passive bystanders at scale.** Its README warns that the fixed public key makes tags trackable — the same lesson as our address and salt rotation. |
| **Shareboxx** — [dividebysandwich/shareboxx](https://github.com/dividebysandwich/shareboxx) (163★, GPL-2.0); PirateBox / LibraryBox lineage | Offline Wi-Fi hotspot for anonymous file upload and download; no accounts | a, c-ish | Fixed box, not peer-to-peer; no carry-forward unless people copy files by hand. A good model for the stationary-courier role and its UI. |

## Takeaways for ZEMIZDAT

1. **The gaps:** receive-only participation, no identity on air, and content-addressed MCU
   firmware are not offered together by any project found. That is ZEMIZDAT's distinctive
   contribution, and also why there is no field data to borrow.
2. **The documented failures of comparable projects** (Bridgefy tracking, impersonation and DoS;
   bitchat identity flaws) all come from identities or parser robustness. Both are areas where
   ZEMIZDAT already chose the conservative design.
3. **Worth reading closely:**
   * LBARD's prioritised bundle sync;
   * Rumble's replication-density priority;
   * LXMF propagation-node peering, for a stationary-courier v2;
   * Meshtastic and MeshCore power management on the same nRF52840 boards.
4. **None of these projects publishes crowd-scale airtime measurements** of the kind experiment
   E5 needs. The congestion question has to be answered by our own rig.

*Search limits:* web search on 2026-10-19 plus the repo pages linked above. Closed or
discontinued products (FireChat, goTenna) were excluded because they have no open repository;
academic DTN prototypes without maintained repositories (e.g. Haggle) were not reviewed.
