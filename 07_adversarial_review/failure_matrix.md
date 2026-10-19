# 07 · Failure matrix

Rows: conditions. Columns: the properties of `01_formal_model`. Cell = what happens.
**S** = safety holds; **D** = degraded performance; **X** = property lost while the condition lasts;
**—** = not applicable. Evidence tags as elsewhere.

| Condition | I1–I4 safety | I6 crash | I5 consent | Liveness / spread | Listener service | Library privacy | Recovers when condition ends? |
|---|---|---|---|---|---|---|---|
| dense crowd, rate control works | S | S | S | D (tens of minutes per hall) [sim A] | D | as designed | — |
| dense crowd, rate control blind to interference (κ wrong) | S | S | S | **X → D** collapse at high density [sim G] | X | — | yes |
| unregulated advertising, N ≥ 500 per domain | S | S | S | **X** [sim A, BCAST] | X | — | yes |
| sparse city contacts, no burst mode | S | S | S | D (≈ half) [sim C] | D | — | — |
| sparse city contacts, burst mode | S | S | S | ok [sim C] | ok | — | — |
| flooder occupying channel | S | S | S | **X** locally [sim B] | X | — | yes, immediately |
| flooder + finite storage | S | S | S | D, bounded by admission policy [sim E] | D | — | partially (junk persists until evicted/deleted) |
| forged suppression | S | S | S | no measurable effect at N = 500 for either variant [sim B]; verified variant immune by construction | same | — | yes |
| black-hole devices (receive, never forward) | S | S | S | no measurable effect at N = 500, h ≥ 0.8 [sim B] | none | — | — |
| bridge couriers removed | S | S | S | **X** across the cut [sim D] | X across cut | — | yes when bridges return |
| power cut at any byte | S | S [exec] | S | — | — | — | yes (mount) |
| malformed / fuzzed frames | S [exec] | S | S | — | — | — | — |
| storage full, honest only | S | S | S | D for new items | D | — | as items are deleted/evicted |
| compromised device | S for others | S | its own only | as flooder/liar | — | — | — |
| ≥ t release keys + owner consent | **X** on that device | X | X | X | X | X | re-flash |
| passive observer with DF | S | S | S | — | — | COURIER/EXCHANGE: X (contents), LISTEN: S | — |
