#!/usr/bin/env python3
"""Aggregate results/runs.jsonl into tables (results/summary.md, results/summary.json) and figures.
All outputs are SIMULATION results; see simulator.py for every assumption."""
import collections
import json
import math
import os
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
COL = {"HYBRID": "#2a78d6", "AE_INV": "#eb6834", "PAIRWISE": "#1baf7a", "BCAST_RC": "#eda100",
       "BCAST": "#e87ba4", "ORACLE": "#008300"}
ORDER = ["HYBRID", "AE_INV", "PAIRWISE", "BCAST_RC", "BCAST", "ORACLE"]


def load():
    rows = []
    for line in open(os.path.join(RES, "runs.jsonl")):
        r = json.loads(line)
        if "error" not in r:
            rows.append(r)
    return rows


def ms(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if not xs:
        return "–"
    if len(xs) == 1:
        return f"{xs[0]:.3f}"
    return f"{st.mean(xs):.3f} ± {st.stdev(xs):.3f}"


def mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return st.mean(xs) if xs else float("nan")


def group(rows, g, keyf):
    d = collections.defaultdict(list)
    for r in rows:
        if r["group"] == g:
            d[keyf(r)].append(r)
    return d


def style(ax, title, xl, yl):
    ax.set_title(title, fontsize=11, loc="left")
    ax.set_xlabel(xl, fontsize=9)
    ax.set_ylabel(yl, fontsize=9)
    ax.grid(alpha=0.25, linewidth=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8)


def main():
    rows = load()
    out = []
    summ = {}
    P = lambda r, k, d=None: r["params"].get(k, d)  # noqa: E731

    # ---------------- A
    A = group(rows, "A", lambda r: (P(r, "N"), P(r, "strategy")))
    out.append("## Group A — population sweep, one auditorium (1 person/m², 60 min)\n")
    out.append("Mean completeness of honest receivers (± s.d. over seeds) / worst-decile (p10) / "
               "listener mean / median time for a pamphlet to reach 80 % of receivers (s) / "
               "fraction of pamphlets that reached 80 % / mean G.\n")
    out.append("| N | strategy | seeds | mean | p10 | LISTEN | t80 (s) | reach80 | tx events | G |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    Ns = sorted({k[0] for k in A})
    for N in Ns:
        for s in ORDER:
            rs = A.get((N, s))
            if not rs:
                continue
            out.append(f"| {N} | {s} | {len(rs)} | {ms([r['completeness_mean'] for r in rs])} | "
                       f"{ms([r['completeness_p10'] for r in rs])} | {ms([r['listen_mean'] for r in rs])} | "
                       f"{mean([r['t80_median'] for r in rs]):.0f} | {ms([r['frac_reach80'] for r in rs])} | "
                       f"{mean([r['tx_events'] for r in rs]):.3g} | {mean([r['G_mean'] for r in rs]):.2f} |")
            summ[f"A|{N}|{s}"] = dict(mean=mean([r['completeness_mean'] for r in rs]),
                                      p10=mean([r['completeness_p10'] for r in rs]),
                                      listen=mean([r['listen_mean'] for r in rs]),
                                      reach80=mean([r['frac_reach80'] for r in rs]))
    out.append("")
    # figure A1: final mean & p10 vs N
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for s in ORDER:
        xs = [N for N in Ns if (N, s) in A]
        if not xs:
            continue
        axs[0].plot(xs, [mean([r['completeness_mean'] for r in A[(N, s)]]) for N in xs], "-o", ms=4,
                    lw=2, color=COL[s], label=s)
        axs[1].plot(xs, [mean([r['completeness_p10'] for r in A[(N, s)]]) for N in xs], "-o", ms=4,
                    lw=2, color=COL[s], label=s)
    Hr = group(rows, "H", lambda r: (P(r, "env"), P(r, "N")))
    hx = sorted(N for (e, N) in Hr if e == "auditorium")
    if hx:
        for ax, key_ in zip(axs, ("completeness_mean", "completeness_p10")):
            ax.plot(hx, [mean([r[key_] for r in Hr[("auditorium", N)]]) for N in hx], "--s", ms=4, lw=2,
                    color=COL["HYBRID"], label="HYBRID v1 (beacons off)")
    for ax, t in zip(axs, ("Mean completeness after 60 min", "Worst-decile (p10) completeness")):
        ax.set_xscale("log")
        style(ax, t, "devices in one hall (log)", "fraction of honest pamphlets held")
    axs[0].legend(fontsize=8, frameon=False)
    fig.text(0.5, 0.015, "SIMULATION — auditorium, 1 person/m², 20 % LISTEN / 30 % EXCHANGE / 50 % COURIER",
             ha="center", fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(os.path.join(RES, "fig_A_population.png"), dpi=150)
    plt.close(fig)
    # figure A2: time series at N=1000 and 3000
    for Nsel in (1000, 3000):
        fig, ax = plt.subplots(figsize=(6, 3.6))
        any_ = False
        for s in ORDER:
            rs = A.get((Nsel, s))
            if not rs:
                continue
            ser = rs[0]["series"]
            ax.plot([x["t"] / 60 for x in ser], [x["mean"] for x in ser], lw=2, color=COL[s], label=s,
                    ls="--" if s == "ORACLE" else "-")
            any_ = True
        if any_:
            style(ax, f"Mean completeness over time, N = {Nsel} (seed 1)", "minutes", "fraction held")
            ax.legend(fontsize=8, frameon=False)
            fig.tight_layout()
            fig.savefig(os.path.join(RES, f"fig_A_timeseries_N{Nsel}.png"), dpi=150)
        plt.close(fig)

    # ---------------- B
    B = group(rows, "B", lambda r: (P(r, "adversary"), P(r, "h"), P(r, "strategy"),
                                    P(r, "verified_suppression", True)))
    out.append("## Group B — cooperative fraction h × adversary (N = 500, 30 min)\n")
    out.append("| adversary | h | strategy | verified suppr. | mean | p10 | G |")
    out.append("|---|---|---|---|---|---|---|")
    for k in sorted(B, key=lambda k: (k[0], -k[1], ORDER.index(k[2]), not k[3])):
        rs = B[k]
        out.append(f"| {k[0]} | {k[1]} | {k[2]} | {'yes' if k[3] else 'NO'} | "
                   f"{ms([r['completeness_mean'] for r in rs])} | {ms([r['completeness_p10'] for r in rs])} | "
                   f"{mean([r['G_mean'] for r in rs]):.2f} |")
        summ["B|" + "|".join(map(str, k))] = mean([r['completeness_mean'] for r in rs])
    out.append("")
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4), sharey=True)
    for ax, adv in zip(axs, ("flood", "blackhole", "suppress")):
        for s in ("HYBRID", "AE_INV", "BCAST_RC"):
            hs = sorted({k[1] for k in B if k[0] == adv and k[2] == s and k[3]}, reverse=True)
            if adv != "flood":
                hs = [1.0] + hs if ("flood", 1.0, s, True) in B else hs
            ys = [mean([r['completeness_mean'] for r in (B.get((adv, h, s, True)) or B.get(("flood", 1.0, s, True)))])
                  for h in hs]
            ax.plot(hs, ys, "-o", ms=4, lw=2, color=COL[s], label=s)
        if adv == "suppress":
            hs = sorted({k[1] for k in B if k[0] == adv and not k[3]}, reverse=True)
            ax.plot(hs, [mean([r['completeness_mean'] for r in B[(adv, h, "HYBRID", False)]]) for h in hs],
                    ":o", ms=4, lw=2, color=COL["HYBRID"], label="HYBRID, naive suppression")
        ax.invert_xaxis()
        style(ax, f"adversary: {adv}", "cooperative fraction h", "mean completeness")
        ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(RES, "fig_B_adversary.png"), dpi=150)
    plt.close(fig)

    # ---------------- C
    def cvar(r):
        if P(r, "burst_n", 8) == 0:
            return "no burst mode"
        if P(r, "sdb", True) is False:
            return "beacons off (v1)"
        if P(r, "digest_weight", True) is False:
            return "beacons sent, weight off"
        return "default" if P(r, "strategy") != "HYBRID" else "beacons on"
    C = group(rows, "C", lambda r: (P(r, "env"), P(r, "strategy"), cvar(r)))
    out.append("## Group C — environments (N = 3 000)\n")
    out.append("rooms: 6 rooms × 500, people change room every ~20 min on average, 1 h. "
               "city: encounter process, 1.5 encounters/h, 20 communities, 24 h.\n")
    out.append("| env | strategy | variant | seeds | mean | p10 | LISTEN | COURIER | t50 (min) | reach50 | "
               "energy mAh (radio, nRF52840 currents) |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for k in sorted(C, key=lambda k: (k[0], ORDER.index(k[1]), k[2])):
        rs = C[k]
        out.append(f"| {k[0]} | {k[1]} | {k[2]} | {len(rs)} | "
                   f"{ms([r['completeness_mean'] for r in rs])} | {ms([r['completeness_p10'] for r in rs])} | "
                   f"{ms([r['listen_mean'] for r in rs])} | {ms([r['courier_mean'] for r in rs])} | "
                   f"{mean([r['t50_median'] for r in rs]) / 60:.0f} | {ms([r['frac_reach50'] for r in rs])} | "
                   f"{mean([r['energy_mAh_mean'] for r in rs]):.1f} |")
        summ["C|" + "|".join(map(str, k))] = mean([r['completeness_mean'] for r in rs])
    out.append("")
    for env in ("rooms", "city"):
        fig, ax = plt.subplots(figsize=(6, 3.6))
        for s in ORDER:
            rs = C.get((env, s, "beacons on" if s == "HYBRID" else "default"))
            if not rs:
                continue
            ser = rs[0]["series"]
            ax.plot([x["t"] / 3600 for x in ser], [x["mean"] for x in ser], lw=2, color=COL[s], label=s)
        for var, ls in (("beacons off (v1)", ":"), ("no burst mode", "-.")):
            rs = C.get((env, "HYBRID", var))
            if rs:
                ser = rs[0]["series"]
                ax.plot([x["t"] / 3600 for x in ser], [x["mean"] for x in ser], lw=2, ls=ls,
                        color=COL["HYBRID"], label=f"HYBRID, {var}")
        style(ax, f"Mean completeness over time — {env}, N = 3 000 (seed 1)", "hours", "fraction held")
        ax.legend(fontsize=8, frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(RES, f"fig_C_{env}.png"), dpi=150)
        plt.close(fig)

    # ---------------- D
    D = group(rows, "D", lambda r: (P(r, "bridges"), P(r, "cut_bridges")))
    out.append("## Group D — interdiction: two rooms joined only by bridge couriers (N = 400, 2 h)\n")
    out.append("| bridges | bridges silenced | mean | p10 |")
    out.append("|---|---|---|---|")
    for k in sorted(D):
        rs = D[k]
        out.append(f"| {k[0]} | {'yes' if k[1] else 'no'} | {ms([r['completeness_mean'] for r in rs])} | "
                   f"{ms([r['completeness_p10'] for r in rs])} |")
        summ[f"D|{k[0]}|{k[1]}"] = mean([r['completeness_mean'] for r in rs])
    out.append("")

    # ---------------- E
    E = group(rows, "E", lambda r: (P(r, "admission"), P(r, "quota_per_min", 60.0), P(r, "h")))
    out.append("## Group E — storage exhaustion: capacity 600 slots, flooders at 5 events/s (N = 500, 60 min)\n")
    out.append("| admission | quota/min | h | mean | p10 | mean junk stored | honest refused (full) | honest refused (quota) | honest evicted |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for k in sorted(E, key=lambda k: (k[0], k[1], -k[2])):
        rs = E[k]
        q = k[1] if "quota" in k[0] else "–"
        out.append(f"| {k[0]} | {q} | {k[2]} | {ms([r['completeness_mean'] for r in rs])} | "
                   f"{ms([r['completeness_p10'] for r in rs])} | {mean([r['mean_junk'] for r in rs]):.0f} | "
                   f"{mean([r['honest_drops_full'] for r in rs]):.0f} | {mean([r['honest_drops_quota'] for r in rs]):.0f} | "
                   f"{mean([r.get('honest_evicted', 0) for r in rs]):.0f} |")
        summ[f"E|{k[0]}|{k[1]}|{k[2]}"] = mean([r['completeness_mean'] for r in rs])
    out.append("")

    # ---------------- F
    F = collections.defaultdict(list)
    for r in rows:
        if r["group"] != "F":
            continue
        base = {"N", "strategy", "T", "sample_s", "seed"}
        extra = {k: v for k, v in r["params"].items() if k not in base}
        lab = ", ".join(f"{k}={v}" for k, v in extra.items()) or "baseline"
        F[(P(r, "strategy"), lab)].append(r)
    out.append("## Group F — sensitivity (N = 1 000 auditorium, 30 min, 2 seeds)\n")
    out.append("| strategy | change from baseline | mean | p10 | LISTEN | reach80 | energy mAh |")
    out.append("|---|---|---|---|---|---|---|")
    for k in sorted(F, key=lambda k: (ORDER.index(k[0]), k[1] != "baseline", k[1])):
        rs = F[k]
        out.append(f"| {k[0]} | {k[1]} | {ms([r['completeness_mean'] for r in rs])} | "
                   f"{ms([r['completeness_p10'] for r in rs])} | {ms([r['listen_mean'] for r in rs])} | "
                   f"{ms([r['frac_reach80'] for r in rs])} | {mean([r['energy_mAh_mean'] for r in rs]):.2f} |")
        summ["F|" + "|".join(k)] = mean([r['completeness_mean'] for r in rs])
    out.append("")
    # any G (extra) groups
    for g in sorted({r["group"] for r in rows} - set("ABCDEF")):
        G = collections.defaultdict(list)
        for r in rows:
            if r["group"] == g:
                lab = ", ".join(f"{k}={v}" for k, v in r["params"].items() if k not in ("seed", "sample_s"))
                G[lab].append(r)
        out.append(f"## Group {g}\n")
        out.append("| configuration | seeds | mean | p10 | reach80 | G |")
        out.append("|---|---|---|---|---|---|")
        for lab, rs in sorted(G.items()):
            out.append(f"| {lab} | {len(rs)} | {ms([r['completeness_mean'] for r in rs])} | "
                       f"{ms([r['completeness_p10'] for r in rs])} | {ms([r['frac_reach80'] for r in rs])} | "
                       f"{mean([r['G_mean'] for r in rs]):.2f} |")
            summ[f"{g}|{lab}"] = mean([r['completeness_mean'] for r in rs])
        out.append("")

    with open(os.path.join(RES, "summary.md"), "w") as fh:
        fh.write("# Simulation results (generated by analyze.py — SIMULATION, not measurement)\n\n")
        fh.write(f"{len(rows)} runs.\n\n" + "\n".join(out))
    json.dump(summ, open(os.path.join(RES, "summary.json"), "w"), indent=1)
    print("\n".join(out))


if __name__ == "__main__":
    main()
