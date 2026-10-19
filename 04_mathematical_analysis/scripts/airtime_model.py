#!/usr/bin/env python3
"""Analytical airtime model for ZEMIZDAT over BLE 5 extended advertising (and comparators).

THEORETICAL ESTIMATE. Constants marked [spec] follow from the Bluetooth Core Specification
PDU formats; everything marked [assume] is a parameter to be replaced by experiment E5.

Outputs: results/airtime_model.json and a printed table used by communication_bounds.md.
"""
import json
import math
import os

US = 1e-6
# ---- PDU airtimes ---------------------------------------------------------------------
# 1M PHY: 1 B preamble + 4 B access address + 2 B header + payload + 3 B CRC, 8 us/byte
# 2M PHY: 2 B preamble, 4 us/byte
def t1m(payload):
    return (1 + 4 + 2 + payload + 3) * 8 * US


def t2m(payload):
    return (2 + 4 + 2 + payload + 3) * 4 * US


TAU_P = t1m(7)          # ADV_EXT_IND: ext-hdr len/flags(2) + ADI(2) + AuxPtr(3) = 7 B  [spec]
TAU_A = t2m(255)        # full AUX_ADV_IND / AUX_CHAIN_IND on 2M PHY                    [spec]
TAU_A_1M = t1m(255)
N_SEC = 37
P_LOSS = 0.10           # [assume]
FRAME = 236             # ZEMIZDAT frame bytes per AUX PDU (220 B chunk + 16 B header)


def per_event_frames(R, L, int_frac=1.0, tau_a=TAU_A, p_loss=P_LOSS):
    """Expected frames decoded per (event x receiver that is scanning), chain of L PDUs."""
    Gp = R * TAU_P * int_frac
    Ga = R * L * tau_a * int_frac / N_SEC
    a = math.exp(-2 * Ga) * (1 - p_loss)
    sp = math.exp(-2 * Gp)
    return sp * sum(a ** k for k in range(1, L + 1)), Gp, Ga, a, sp


def domain_goodput(R, L, **kw):
    """Frames/s decodable by an always-scanning receiver that hears the WHOLE domain."""
    f, *_ = per_event_frames(R, L, **kw)
    return R * f


def optimise(L, **kw):
    best = (0, 0)
    for R in range(50, 20001, 10):
        g = domain_goodput(R, L, **kw)
        if g > best[0]:
            best = (g, R)
    g, R = best
    f, Gp, Ga, a, sp = per_event_frames(R, L, **kw)
    return dict(L=L, R_opt=R, frames_per_s=round(g, 1), Gp=round(Gp, 3), Ga=round(Ga, 3),
                aux_success=round(a, 3), primary_success=round(sp, 3),
                kB_per_s=round(g * 220 / 1000, 1))


def main():
    out = {"constants": dict(TAU_P_us=round(TAU_P / US, 1), TAU_A_us=round(TAU_A / US, 1),
                             TAU_A_1M_us=round(TAU_A_1M / US, 1), N_SEC=N_SEC, P_LOSS=P_LOSS)}
    print("PDU airtime: ADV_EXT_IND %.0f us (1M), AUX 255B %.0f us (2M) / %.0f us (1M)"
          % (TAU_P / US, TAU_A / US, TAU_A_1M / US))

    # 1. chain length optimisation (always-on receiver, whole domain audible)
    rows = [optimise(L) for L in (1, 2, 3, 4, 6, 7)]
    out["chain_optimisation"] = rows
    print("\nChain length vs optimal domain goodput (receiver hears whole domain, 100% scan):")
    for r in rows:
        print("  L=%d  R*=%5d ev/s  %7.1f frames/s (%6.1f kB/s)  Gp=%.2f Ga=%.2f a=%.2f" %
              (r["L"], r["R_opt"], r["frames_per_s"], r["kB_per_s"], r["Gp"], r["Ga"], r["aux_success"]))

    # 2. what the simulator's rate-control target implies
    for L in (1, 6):
        for G in (0.1, 0.2, 0.3):
            R = min(G / TAU_P, G * N_SEC / (L * TAU_A))
            f, Gp, Ga, a, sp = per_event_frames(R, L)
            out.setdefault("targets", []).append(dict(L=L, G_target=G, R=round(R), frames_per_event=round(f, 3),
                                                      goodput_frames_s=round(R * f)))

    # 3. unregulated advertising collapse: N transmitters at 10 events/s
    coll = []
    for N in (10, 50, 100, 200, 500, 1000, 3000, 5000):
        f, Gp, Ga, a, sp = per_event_frames(10 * N, 6)
        coll.append(dict(N_tx=N, Gp=round(Gp, 3), Ga=round(Ga, 3), frames_per_event=round(f, 4),
                         domain_frames_s=round(10 * N * f, 1)))
    out["unregulated_10Hz_L6"] = coll
    print("\nUnregulated 10 Hz chained advertising, one interference domain:")
    for c in coll:
        print("  N_tx=%5d  Gp=%.2f Ga=%.2f  frames/event=%.4f  domain frames/s=%.0f" %
              (c["N_tx"], c["Gp"], c["Ga"], c["frames_per_event"], c["domain_frames_s"]))
    # critical N where unregulated goodput peaks
    best = max(coll, key=lambda c: c["domain_frames_s"])
    out["unregulated_peak_N"] = best["N_tx"]

    # 4. Auditorium completion lower bound (broadcast), M pamphlets of 6 frames, tiles
    M, F = 3000, 6
    hall_side = math.sqrt(3000 / 1.0)
    tile = 10.0
    tiles = (hall_side / tile) ** 2
    opt6 = optimise(6)
    per_tile_frames = opt6["frames_per_s"] / tiles
    scan = 0.3
    t_ideal = M * F / (per_tile_frames * scan)
    out["auditorium_bound"] = dict(M=M, frames_per_pamphlet=F, tiles=round(tiles, 1),
                                   domain_frames_s=opt6["frames_per_s"],
                                   per_receiver_frames_s_at_scan30=round(per_tile_frames * scan, 1),
                                   ideal_seconds_no_redundancy=round(t_ideal),
                                   note="every frame new to every receiver; real carousels add a coupon-collector factor")
    print("\nAuditorium 3000 devices, 1 person/m^2, %0.f reception tiles of %0.f m, one interference domain:"
          % (tiles, tile))
    print("  optimal domain goodput %.0f frames/s -> %.1f frames/s per tile -> %.1f/s per receiver at 30%% scan"
          % (opt6["frames_per_s"], per_tile_frames, per_tile_frames * scan))
    print("  lower bound to receive 3000 x 6 frames: %.0f s (%.1f min)" % (t_ideal, t_ideal / 60))

    # 5. Unicast comparison and the Gemini '102 hours' figure
    bits = 3000 * 2999 * 1068 * 8
    gemini = bits / 200e3 / 3600
    raw = N_SEC * 2e6
    eff = raw * 0.5 * math.exp(-1)  # link-layer efficiency 0.5, ALOHA at G=0.5 across channels [assume]
    out["unicast"] = dict(total_bits=bits, gemini_single_200kbps_hours=round(gemini, 1),
                          data_channels_raw_Mbps=raw / 1e6, effective_Mbps_assumed=round(eff / 1e6, 1),
                          hours_at_effective=round(bits / eff / 3600, 2),
                          broadcast_frames_needed=3000 * F * tiles, )
    print("\nUnicast: N(M-1)L = %.2e bits. Gemini's single 200 kbps channel: %.0f h. With 37 data channels"
          " at an assumed %.1f Mb/s effective: %.1f h." % (bits, gemini, eff / 1e6, bits / eff / 3600))
    bc_bits = 3000 * 1068 * 8 * tiles * 1.0
    out["unicast"]["broadcast_bits_one_copy_per_tile"] = bc_bits
    out["unicast"]["broadcast_gain_factor"] = round(bits / bc_bits, 1)
    print("Broadcast needs ~one copy per reception tile: %.2e bits -> intrinsic gain %.0fx over unicast,"
          " before scan duty and loss." % (bc_bits, bits / bc_bits))

    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "results"), exist_ok=True)
    with open(os.path.join(os.path.dirname(__file__), "..", "results", "airtime_model.json"), "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
