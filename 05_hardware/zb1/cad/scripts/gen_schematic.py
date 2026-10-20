"""Generate zb1.kicad_sch (KiCad 7) from zb1_design.PARTS.

Style: every connected pin gets a short wire stub ending in a net label (a common "label per
pin" style); unconnected pins get no-connect flags. Parts are grouped into titled blocks.
The generated schematic is checked by exporting its netlist with kicad-cli (see verify_netlist.py).
"""
from __future__ import annotations
import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CAD = os.path.dirname(HERE)

import symlib  # noqa: E402
from sexp import dumps, Q  # noqa: E402
from zb1_design import PARTS, BLOCKS  # noqa: E402

LOCAL = {"zb1": os.path.join(CAD, "lib", "zb1.kicad_sym")}
G = 2.54
STUB = 2.54
NS = uuid.UUID("6f1b8a52-7c3e-4d2a-9b1e-zb1000000000".replace("zb1", "0b1"))


def uid(*key):
    return str(uuid.uuid5(NS, "/".join(map(str, key))))


ROOT = uid("root")


def snap(v):
    return round(round(v / 1.27) * 1.27, 4)


def text_w(s, size=1.27):
    return len(s) * size * 0.75 + 1.0


# Pre-load symbols and compute geometry
SYMS = {}
for p in PARTS:
    if p["sym"] not in SYMS:
        SYMS[p["sym"]] = symlib.load_symbol(p["sym"], LOCAL)


def part_extent(p):
    pins = symlib.pins(SYMS[p["sym"]])
    xs = [x for _, _, x, _, _, _, _ in pins]
    ys = [y for _, _, _, y, _, _, _ in pins]
    lab = max([text_w(n) for n in p["pins"].values()] + [4])
    minx, maxx = min(xs + [-2.54]), max(xs + [2.54])
    miny, maxy = min(ys + [-2.54]), max(ys + [2.54])
    # room for stub + label on each side, and for reference/value text
    return (minx - STUB - lab, maxx + STUB + lab, miny - STUB - lab * 0.6 - 3, maxy + STUB + lab * 0.6 + 3)


def place_blocks():
    """Simple shelf packing of parts inside blocks, blocks laid out in two columns on A2."""
    order = ["usb", "charger", "protect", "ldo", "mcu", "sd", "io"]
    cols = {"usb": 0, "charger": 0, "protect": 0, "ldo": 0, "mcu": 1, "sd": 1, "io": 1}
    widths = {0: 250.0, 1: 300.0}
    xstart = {0: 20.0, 1: 280.0}
    ycur = {0: 25.0, 1: 25.0}
    placed, rects = {}, []
    for b in order:
        col = cols[b]
        bw = widths[col]
        x0, y0 = xstart[col], ycur[col]
        x, y, shelf_h = x0 + 5, y0 + 12, 0
        for p in [p for p in PARTS if p["block"] == b]:
            l, r, bot, top = part_extent(p)
            w, h = r - l, top - bot
            if x + w > x0 + bw - 5:
                x, y, shelf_h = x0 + 5, y + shelf_h + 4, 0
            placed[p["ref"]] = (snap(x - l), snap(y + top))   # symbol origin (schematic y down)
            x += w + 4
            shelf_h = max(shelf_h, h)
        bh = (y + shelf_h + 6) - y0
        rects.append((b, x0, y0, bw, bh))
        ycur[col] = y0 + bh + 8
    return placed, rects


def build():
    placed, rects = place_blocks()
    items = []
    lib_syms = [SYMS[k] for k in sorted(SYMS)]
    for b, x0, y0, bw, bh in rects:
        items.append(["rectangle", ["start", round(x0, 2), round(y0, 2)], ["end", round(x0 + bw, 2), round(y0 + bh, 2)],
                      ["stroke", ["width", 0.3], ["type", "dash"]], ["fill", ["type", "none"]],
                      ["uuid", uid("rect", b)]])
        items.append(["text", Q(BLOCKS[b]), ["at", round(x0 + 3, 2), round(y0 + 7, 2), 0],
                      ["effects", ["font", ["size", 2.5, 2.5], ["thickness", 0.5], "bold"], ["justify", "left", "bottom"]],
                      ["uuid", uid("btext", b)]])

    used_points = set()
    for p in PARTS:
        X, Y = placed[p["ref"]]
        sym = SYMS[p["sym"]]
        pins = symlib.pins(sym)
        props = []
        _, _, bot, top = part_extent(p)
        pin_ys = [y for _, _, _, y, _, _, _ in pins]
        vertical2 = len(pins) in (1, 2) and all(abs(x) < 1e-6 for _, _, x, _, _, _, _ in pins)
        if vertical2:   # R, C, test points: text to the right so it never hits the labels
            props.append(["property", Q("Reference"), Q(p["ref"]), ["at", round(X + 2.54, 2), round(Y - 0.8, 2), 0],
                          ["effects", ["font", ["size", 1.27, 1.27]], ["justify", "left"]]])
            props.append(["property", Q("Value"), Q(p["value"]), ["at", round(X + 2.54, 2), round(Y + 1.2, 2), 0],
                          ["effects", ["font", ["size", 1.27, 1.27]], ["justify", "left"]]])
        else:
            ref_y = Y - max(pin_ys + [2.54]) - 3.0
            val_y = Y - min(pin_ys + [-2.54]) + 3.0
            props.append(["property", Q("Reference"), Q(p["ref"]), ["at", X, round(ref_y, 2), 0],
                          ["effects", ["font", ["size", 1.27, 1.27]]]])
            props.append(["property", Q("Value"), Q(p["value"]), ["at", X, round(val_y, 2), 0],
                          ["effects", ["font", ["size", 1.27, 1.27]]]])
        props.append(["property", Q("Footprint"), Q(p["fp"]), ["at", X, Y, 0],
                      ["effects", ["font", ["size", 1.27, 1.27]], "hide"]])
        props.append(["property", Q("Datasheet"), Q(""), ["at", X, Y, 0],
                      ["effects", ["font", ["size", 1.27, 1.27]], "hide"]])
        props.append(["property", Q("MPN"), Q(p["mpn"]), ["at", X, Y, 0],
                      ["effects", ["font", ["size", 1.27, 1.27]], "hide"]])
        pin_entries = [["pin", Q(n), ["uuid", uid(p["ref"], "pin", n)]] for n in sorted({x[0] for x in pins})]
        items.append(["symbol", ["lib_id", Q(p["sym"])], ["at", X, Y, 0], ["unit", 1],
                      ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "yes" if p.get("dnp") else "no"],
                      ["uuid", uid(p["ref"])], *props, *pin_entries,
                      ["instances", ["project", Q("zb1"), ["path", Q("/" + ROOT), ["reference", Q(p["ref"])], ["unit", 1]]]]])

        done_here = set()
        for num, name, px, py, ang, ln, et in pins:
            ex, ey = round(X + px, 4), round(Y - py, 4)
            if (ex, ey) in done_here:
                continue                         # stacked pins share one connection
            done_here.add((ex, ey))
            stacked = [n for n, _, qx, qy, _, _, _ in pins if abs(qx - px) < 1e-6 and abs(qy - py) < 1e-6]
            nets = {p["pins"][n] for n in stacked if n in p["pins"]}
            if not nets:
                items.append(["no_connect", ["at", ex, ey], ["uuid", uid(p["ref"], "nc", num)]])
                continue
            assert len(nets) == 1, (p["ref"], stacked, nets)
            net = nets.pop()
            # stub goes away from the body: opposite to the pin direction
            d = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[int(ang) % 360]
            sx, sy = round(ex + d[0] * STUB, 4), round(ey + d[1] * STUB, 4)
            assert (sx, sy) not in used_points, (p["ref"], num)
            used_points.add((sx, sy))
            items.append(["wire", ["pts", ["xy", ex, ey], ["xy", sx, sy]],
                          ["stroke", ["width", 0], ["type", "default"]], ["uuid", uid(p["ref"], "w", num)]])
            lang, just = {(-1, 0): (180, "right"), (1, 0): (0, "left"),
                          (0, -1): (90, "left"), (0, 1): (270, "right")}[d]
            items.append(["label", Q(net), ["at", sx, sy, lang],
                          ["effects", ["font", ["size", 1.27, 1.27]], ["justify", just, "bottom"]],
                          ["uuid", uid(p["ref"], "l", num)]])

    notes = [
        "ZB-1 rev 0.1 - generated from scripts/zb1_design.py (single source of truth). Edit the script, not this file.",
        "DNP by default: U6 + Q2 + R23/R24/C13 (cell protection; SJ2 bridges BATN-GND), U7 + C16 (fuel gauge).",
        "J3 polarity: pin 1 = BAT- (black), pin 2 = BAT+ (red). CHECK YOUR CELL - there is no polarity standard.",
        "SJ1: cut to insert an ammeter in the 3V3 rail (E6). TP1 / Feather EN pulls LDO_EN low to cut power (E7).",
    ]
    for i, t in enumerate(notes):
        items.append(["text", Q(t), ["at", 20, 375 + i * 4.5, 0],
                      ["effects", ["font", ["size", 2, 2]], ["justify", "left", "bottom"]], ["uuid", uid("note", i)]])

    sch = ["kicad_sch", ["version", 20230121], ["generator", "eeschema"], ["uuid", ROOT], ["paper", Q("A2")],
           ["title_block", ["title", Q("ZEMIZDAT ZB-1 development board")], ["date", Q("2026-10-19")],
            ["rev", Q("0.1")], ["company", Q("ZEMIZDAT project (github.com/danindiana/zemizdat)")],
            ["comment", 1, Q("ESP32-S3-MINI-1-N8 | BQ21040 LiPo charger | RT9080 LDO | 4-bit microSD")],
            ["comment", 2, Q("Design only - not fabricated or tested. See ../README.md")]],
           ["lib_symbols", *lib_syms], *items,
           ["sheet_instances", ["path", Q("/"), ["page", Q("1")]]]]
    return dumps(sch) + "\n"


if __name__ == "__main__":
    out = os.path.join(CAD, "zb1.kicad_sch")
    open(out, "w").write(build())
    print("wrote", out)
