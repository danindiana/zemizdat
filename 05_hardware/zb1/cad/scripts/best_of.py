"""Run the route+finish stages for several pre-route configurations and keep the best result.

Freerouting is deterministic for a given input but chaotic across inputs: a small change in what is
pre-routed reshuffles everything. So try a few and keep the one with the fewest unconnected items
(ties: fewer DRC violations). Artifacts of each attempt go to build/attempts/<name>/.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAD = os.path.dirname(HERE)
BUILD = os.path.join(CAD, "build")

BASE = [["VBUS", ["U5", "5"], ["J1", "A9"]], "USB_DP", "USB_DN", "XTAL32_P", "XTAL32_N"]
CONFIGS = {
    "A_usb_xtal": BASE,
    "B_plus_protvcc_hop": BASE + [["PROT_VCC", ["R23", "2"], ["U6", "5"]]],
    "C_plus_protvcc_net": BASE + ["PROT_VCC"],
}


def score(rpt):
    txt = open(rpt).read()
    import re
    unc = int(re.search(r"Found (\d+) unconnected", txt).group(1))
    viol = int(re.search(r"Found (\d+) DRC violations", txt).group(1))
    return unc, viol


def main(names):
    env = dict(os.environ, KICAD7_FOOTPRINT_DIR="/usr/share/kicad/footprints",
               KICAD7_SYMBOL_DIR="/usr/share/kicad/symbols")
    results = {}
    for name in names:
        cfg = CONFIGS[name]
        out = os.path.join(BUILD, "attempts", name)
        os.makedirs(out, exist_ok=True)
        for f in os.listdir(BUILD):
            if f.endswith((".kicad_pro", ".kicad_prl")) or f == "zb1.ses":
                os.remove(os.path.join(BUILD, f))
        env["ZB1_PREROUTE"] = json.dumps(cfg)
        r1 = subprocess.run([sys.executable, os.path.join(HERE, "route.py")], env=env, capture_output=True, text=True)
        r2 = subprocess.run([sys.executable, os.path.join(HERE, "finish.py")], env=env, capture_output=True, text=True)
        open(os.path.join(out, "log.txt"), "w").write(r1.stdout + r1.stderr + r2.stdout + r2.stderr)
        for f in ("zb1.ses", "zb1_fanout.kicad_pcb"):
            shutil.copy(os.path.join(BUILD, f), out)
        shutil.copy(os.path.join(CAD, "zb1.kicad_pcb"), out)
        shutil.copy(os.path.join(CAD, "reports", "drc.rpt"), out)
        results[name] = score(os.path.join(out, "drc.rpt"))
        print(name, "unconnected=%d violations=%d" % results[name], flush=True)
    best = min(results, key=lambda n: results[n])
    out = os.path.join(BUILD, "attempts", best)
    shutil.copy(os.path.join(out, "zb1.kicad_pcb"), os.path.join(CAD, "zb1.kicad_pcb"))
    shutil.copy(os.path.join(out, "drc.rpt"), os.path.join(CAD, "reports", "drc.rpt"))
    shutil.copy(os.path.join(out, "zb1.ses"), os.path.join(BUILD, "zb1.ses"))
    shutil.copy(os.path.join(out, "zb1_fanout.kicad_pcb"), os.path.join(BUILD, "zb1_fanout.kicad_pcb"))
    json.dump({"results": results, "best": best}, open(os.path.join(BUILD, "attempts", "summary.json"), "w"), indent=1)
    print("best:", best, results[best])


if __name__ == "__main__":
    main(sys.argv[1:] or list(CONFIGS))
