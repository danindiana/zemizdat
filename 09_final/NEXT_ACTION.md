# 09 · Next action (one, concrete, falsifiable)

**Build two ESP32-S3 boards and two nRF52840 boards running `03_protocol/reference_c/zm_core.c`
with a minimal radio glue, and run experiment E1 + E2:** one board advertises the eight
pamphlets in `reference_c/vectors.txt` as anonymous, non-connectable, 3-PDU chained extended
advertising at 2 events/s; the other passively scans at 30 % duty and commits what it completes.

**Hypothesis being tested:** both commodity BLE stacks can carry ZEMIZDAT's connectionless,
chained, identity-free frames to the host intact, and a passive receiver reconstructs and verifies
every pamphlet without ever transmitting.

**Falsified if** (any of):
* fewer than 90 % of caught events deliver all 3 chain PDUs at 1 m on either stack;
* a stable advertiser address appears on the sniffer;
* the receiver commits any id not in the vector list, or fails to commit any listed id within
  10 minutes;
* the sniffer or SDR sees any transmission from the LISTEN board.

**Why this first:** every other result in this tree — the carousel, the simulations, the
capacity numbers — assumes this link exists. It is the cheapest experiment (≈ $60, ≈ 1 week) that
can invalidate the whole architecture, and its failure modes have predefined fallbacks
(`L_CHAIN = 1`, address rotation, ESP-NOW).

Recording: JSONL per `08_verification/test_plan.md`, firmware git hash, sniffer pcap, photos of
the setup. Then E7 (power cuts on real flash) on the same boards.
