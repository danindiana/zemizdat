"""Compare a KiCad-exported netlist (kicadxml) with zb1_design.PARTS, pin by pin.

Usage: python verify_netlist.py <netlist.xml>   (exit 1 on any mismatch)
Checks: every designed connection is present under the same net name, no extra connections,
every component present with the designed footprint and value.
"""
import sys
import os
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zb1_design import PARTS  # noqa: E402


def main(path):
    root = ET.parse(path).getroot()
    errs = []
    comps = {c.get("ref"): c for c in root.iter("comp")}
    for p in PARTS:
        c = comps.get(p["ref"])
        if c is None:
            errs.append(f"missing component {p['ref']}")
            continue
        if c.findtext("footprint") != p["fp"]:
            errs.append(f"{p['ref']}: footprint {c.findtext('footprint')} != {p['fp']}")
        if c.findtext("value") != p["value"]:
            errs.append(f"{p['ref']}: value {c.findtext('value')} != {p['value']}")
    got = {}
    for n in root.iter("net"):
        name = n.get("name").lstrip("/")
        for node in n.iter("node"):
            got[(node.get("ref"), node.get("pin"))] = name
    want = {(p["ref"], pin): net for p in PARTS for pin, net in p["pins"].items()}
    for k, net in want.items():
        g = got.get(k)
        if g != net:
            errs.append(f"{k[0]}.{k[1]}: netlist {g!r} != design {net!r}")
    for k, g in got.items():
        if k not in want and not g.startswith("unconnected-"):
            errs.append(f"{k[0]}.{k[1]}: extra connection to {g!r}")
    n_conn = len(want)
    print(f"components: {len(comps)} (design {len(PARTS)}); designed pin connections: {n_conn}; "
          f"nets: {len({v for v in want.values()})}")
    if errs:
        print("MISMATCHES:")
        print("\n".join("  " + e for e in errs))
        return 1
    print("OK: schematic netlist matches the design database exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
