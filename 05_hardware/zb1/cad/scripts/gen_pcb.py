"""Stage 1 of the PCB flow: create zb1.kicad_pcb from zb1_design.PARTS.

Board: Feather 50.8 x 22.86 mm, 4 layers (F.Cu signal / In1 GND plane / In2 signal+GND /
B.Cu signal). Fixed placements for connectors, module and headers; every other part is placed
by a small greedy search from a target position until its courtyard clears everything on the
same side (0.2 mm margin). Then GND pads get fan-out vias to the In1 plane.
Output: zb1_placed.kicad_pcb (unrouted). route.py does the rest.
"""
from __future__ import annotations
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CAD = os.path.dirname(HERE)

import pcbnew  # noqa: E402
from shapely.geometry import box, Point, LineString, Polygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402
from zb1_design import PARTS, MECH  # noqa: E402

MM = pcbnew.FromMM
OX, OY = 100.0, 100.0          # board origin on the KiCad page
W, H = 50.8, 22.86
ANT_X = 45.4                   # antenna keep-out starts here (board x)


def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


# ------------------------------------------------------------------ placement plan (board mm)
# ref: (x, y, rotation_deg, side)   side F = top, B = bottom. Fixed = exact.
FIXED = {
    "U1": (38.0, 11.43, 270, "F"),       # antenna (local -y) -> +x, flush with right edge
    "J1": (3.87, 11.43, 270, "F"),       # USB-C mouth -> -x
    "J2": (8.13, 11.43, 270, "B"),        # microSD on bottom, slot at the USB end
    "J5": (6.35, 21.59, 90, "F"),        # Feather 16-pin row (pins along +x)
    "J6": (16.51, 1.27, 90, "F"),        # Feather 12-pin row
}
MECH_POS = {"H3": (48.26, 2.54), "H4": (48.26, 20.32)}   # USB-end holes dropped (microSD slot)

# auto-placed: ref -> (target x, y, rotation, side)
TARGET = {
    # ---- top: USB, ESD, battery jack, charger, power path, buttons, crystal, LED
    # (everything left of x = 28.4 so the module's left pad row keeps a 2.2 mm escape channel)
    "U5": (12.4, 11.4, 90, "F"), "R1": (10.4, 7.8, 90, "F"), "R2": (10.4, 15.0, 90, "F"),
    "LED2": (4.0, 3.6, 0, "F"), "R21": (4.0, 5.0, 0, "F"),
    "U2": (12.7, 4.6, 0, "F"), "R3": (9.6, 2.4, 0, "F"), "R4": (9.6, 3.7, 0, "F"),
    "C1": (13.0, 8.0, 0, "F"),
    "J3": (19.6, 8.0, 0, "F"),
    "C2": (16.3, 13.0, 0, "F"),
    "D1": (12.6, 16.6, 90, "F"), "Q1": (16.0, 16.2, 0, "F"), "R7": (16.0, 18.9, 0, "F"),
    "C3": (19.0, 16.0, 90, "F"),
    "SW1": (22.1, 16.5, 90, "F"), "SW2": (26.0, 16.5, 90, "F"),
    "Y1": (27.2, 9.0, 90, "F"), "C8": (27.2, 5.9, 0, "F"), "C9": (27.2, 12.1, 0, "F"),
    "LED1": (26.5, 4.2, 0, "F"), "R20": (25.2, 6.6, 90, "F"),
    # ---- bottom: microSD support
    "U4": (19.5, 7.0, 0, "B"), "R17": (19.5, 4.4, 0, "B"), "C10": (22.0, 5.0, 90, "B"),
    "C11": (19.5, 10.0, 0, "B"), "R15": (18.3, 13.0, 90, "B"),
    "R10": (18.0, 16.4, 90, "B"), "R11": (19.2, 16.4, 90, "B"), "R12": (20.4, 16.4, 90, "B"),
    "R13": (21.6, 16.4, 90, "B"), "R14": (22.8, 16.4, 90, "B"), "R16": (24.0, 16.4, 90, "B"),
    # ---- bottom: regulator + current jumper, battery sense
    "U3": (25.5, 9.0, 0, "B"), "R8": (25.5, 6.2, 0, "B"), "C4": (23.0, 9.0, 90, "B"),
    "C5": (28.0, 9.0, 90, "B"), "SJ1": (25.5, 12.5, 0, "B"),
    "R5": (29.6, 5.0, 90, "B"), "R6": (30.8, 5.0, 90, "B"), "C14": (32.0, 5.0, 90, "B"),
    # ---- bottom: protection (DNP), fuel gauge (DNP), STEMMA-QT, module support, test pads
    "U6": (25.6, 15.0, 0, "B"), "Q2": (31.0, 16.0, 90, "B"), "R23": (28.6, 12.6, 0, "B"),
    "C13": (28.6, 13.8, 0, "B"), "R24": (30.4, 14.6, 90, "B"), "SJ2": (32.6, 14.6, 90, "B"),
    "U7": (35.0, 5.0, 0, "B"), "C16": (37.4, 5.0, 0, "B"),
    "J4": (38.0, 15.6, 0, "B"), "R18": (34.2, 15.0, 90, "B"), "R19": (35.4, 15.0, 90, "B"),
    "C6": (41.0, 6.6, 90, "B"), "C7": (42.6, 6.6, 90, "B"),
    "R9": (40.4, 18.6, 0, "B"), "C15": (42.8, 18.6, 0, "B"), "R25": (39.6, 7.4, 90, "B"),
    "R22": (3.0, 20.4, 0, "B"), "C12": (3.0, 21.6, 0, "B"),
    "TP1": (32.0, 10.2, 0, "B"), "TP2": (34.2, 10.2, 0, "B"), "TP3": (22.4, 11.8, 0, "B"),
    "TP4": (43.6, 10.6, 0, "B"), "TP5": (41.6, 12.0, 0, "B"),
}


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = os.path.join(CAD, "lib", "zb1.pretty") if lib == "zb1" else f"/usr/share/kicad/footprints/{lib}.pretty"
    fp = pcbnew.FootprintLoad(path, name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    v3 = lambda v: (v.x, v.y, v.z)
    models = [(str(m.m_Filename), v3(m.m_Offset), v3(m.m_Rotation), v3(m.m_Scale), m.m_Show)
              for m in fp.Models()]
    fp.Models().clear()
    for fn, off, rot, sc, show in models:
        fn = fn.replace("KICAD6_3DMODEL_DIR", "KICAD7_3DMODEL_DIR")
        fn = MODEL_OVERRIDE.get(name, fn)
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = fn
        m.m_Offset = pcbnew.VECTOR3D(*off); m.m_Rotation = pcbnew.VECTOR3D(*rot); m.m_Scale = pcbnew.VECTOR3D(*sc)
        m.m_Show = show
        fp.Add3DModel(m)
    if not models and name in MODEL_OVERRIDE:
        m = pcbnew.FP_3DMODEL(); m.m_Filename = MODEL_OVERRIDE[name]; fp.Add3DModel(m)
    return fp


MODEL_OVERRIDE = {
    "SW_Push_1P1T_NO_CK_KMR2": "${KIPRJMOD}/lib/3dmodels/SW_KMR2_envelope.step",
    "JST_PH_B2B-PH-SM4-TB_1x02-1MP_P2.00mm_Vertical": "${KIPRJMOD}/lib/3dmodels/JST_PH_B2B-PH-SM4-TB_envelope.step",
    "Crystal_SMD_3215-2Pin_3.2x1.5mm": "${KIPRJMOD}/lib/3dmodels/Crystal_3215_envelope.step",
    "USB_C_Receptacle_HRO_TYPE-C-31-M-12": "${KIPRJMOD}/lib/3dmodels/USB_C_HRO_TYPE-C-31-M-12_envelope.step",
    "microSD_HC_Hirose_DM3AT-SF-PEJM5": "${KIPRJMOD}/lib/3dmodels/microSD_DM3AT_envelope.step",
    "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical": "${KIPRJMOD}/lib/3dmodels/JST_SH_BM04B-SRSS-TB_envelope.step",
}


def courtyard_poly(fp):
    """Union of courtyard graphics (front or back) as a shapely polygon in board mm."""
    layers = (pcbnew.F_CrtYd, pcbnew.B_CrtYd)
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() in layers:
            b = g.GetBoundingBox()
            xs += [b.GetLeft(), b.GetRight()]
            ys += [b.GetTop(), b.GetBottom()]
    if not xs:
        b = fp.GetBoundingBox(False, False)
        xs, ys = [b.GetLeft(), b.GetRight()], [b.GetTop(), b.GetBottom()]
    t = pcbnew.ToMM
    return box(t(min(xs)) - OX, t(min(ys)) - OY, t(max(xs)) - OX, t(max(ys)) - OY)


def place(fp, x, y, rot, side):
    fp.SetPosition(P(x, y))
    fp.SetOrientationDegrees(rot)
    if side == "B" and fp.GetLayer() == pcbnew.F_Cu:
        fp.Flip(P(x, y), False)


def build():
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    board.SetLayerName(pcbnew.In1_Cu, "In1.GND")
    board.SetLayerName(pcbnew.In2_Cu, "In2.Sig")
    ds = board.GetDesignSettings()
    ds.SetAuxOrigin(P(0, 0))
    ds.SetGridOrigin(P(0, 0))

    nets = {}
    for p in PARTS:
        for n in p["pins"].values():
            if n not in nets:
                ni = pcbnew.NETINFO_ITEM(board, n)
                board.Add(ni)
                nets[n] = ni

    # outline with 1.5 mm corner radius
    r = 1.5
    segs = [((r, 0), (W - r, 0)), ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))]
    for a, b in segs:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        board.Add(s)
    k = r * (1 - math.sqrt(0.5))
    for st, mid, en in [((0, r), (k, k), (r, 0)), ((W - r, 0), (W - k, k), (W, r)),
                        ((W, H - r), (W - k, H - k), (W - r, H)), ((r, H), (k, H - k), (0, H - r))]:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(P(*st), P(*mid), P(*en))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        board.Add(s)

    fps = {}
    occupied = {"F": [], "B": []}
    edge = box(0, 0, W, H)

    def add(p, x, y, rot, side, fixed):
        fp = load_fp(p["fp"])
        fp.SetReference(p["ref"])
        fp.SetValue(p.get("value", ""))
        board.Add(fp)
        place(fp, x, y, rot, side)
        for pad in fp.Pads():
            n = p.get("pins", {}).get(pad.GetNumber())
            if n:
                pad.SetNet(nets[n])
        if p.get("dnp"):
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
            fp.Models().clear()          # not fitted: no body in 3D views
        fps[p["ref"]] = fp
        return fp

    for p in PARTS:
        if p["ref"] in FIXED:
            x, y, rot, side = FIXED[p["ref"]]
            fp = add(p, x, y, rot, side, True)
            poly = courtyard_poly(fp)
            occupied[side].append(poly)
            if list(fp.Pads())[0].GetAttribute() == pcbnew.PAD_ATTRIB_PTH:   # headers block both sides
                occupied["B" if side == "F" else "F"].append(poly)
    for m in MECH:
        if m["ref"] in MECH_POS:
            fp = add(dict(m, pins={}), *MECH_POS[m["ref"]], 0, "F", True)
            poly = courtyard_poly(fp)
            occupied["F"].append(poly); occupied["B"].append(poly)
    keep = box(ANT_X, 0, W, H)
    occupied["F"].append(keep); occupied["B"].append(keep)
    # module centre GND pad gets via-in-pad (through all layers): keep the bottom clear under it
    occupied["B"].append(box(38.0 - 2.5, 11.43 - 2.5, 38.0 + 2.5, 11.43 + 2.5))

    unplaced = []
    first = ["Y1", "C8", "C9", "LED1", "R20", "U5", "U2", "U3", "U4", "C6", "C7", "J3", "SW1", "SW2", "J4", "Q2", "U6"]
    rest = [p for p in PARTS if p["ref"] not in FIXED and p["ref"] not in first]
    for p in [next(q for q in PARTS if q["ref"] == r) for r in first] + rest:
        tx, ty, rot, side = TARGET[p["ref"]]
        fp = add(p, tx, ty, rot, side, False)
        ok = False
        for rad in [0] + [0.25 * k for k in range(1, 40)]:
            steps = 1 if rad == 0 else max(8, int(2 * math.pi * rad / 0.25))
            for k in range(steps):
                a = 2 * math.pi * k / steps
                x, y = tx + rad * math.cos(a), ty + rad * math.sin(a)
                x, y = round(x / 0.05) * 0.05, round(y / 0.05) * 0.05
                place(fp, x, y, rot, side)
                poly = courtyard_poly(fp)
                if not edge.buffer(-0.3).contains(poly):
                    continue
                if any(poly.buffer(0.1).intersects(o) for o in occupied[side]):
                    continue
                occupied[side].append(poly)
                ok = True
                break
            if ok:
                break
        if not ok:
            unplaced.append(p["ref"])
        elif rad > 0:
            print(f"  {p['ref']}: moved {rad:.2f} mm from target")
    if unplaced:
        print("UNPLACED:", unplaced)
    return board, fps, nets


def keepout(board):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetZoneName("ANTENNA_KEEPOUT")
    o = z.Outline()
    o.NewOutline()
    for x, y in [(ANT_X, -0.5), (W + 0.5, -0.5), (W + 0.5, H + 0.5), (ANT_X, H + 0.5)]:
        o.Append(MM(OX + x), MM(OY + y))
    board.Add(z)


def module_track_keepout(board):
    """No tracks on F.Cu under the module body (Espressif layout guidance); vias and GND pour allowed."""
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowCopperPour(False)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(False)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetLayer(pcbnew.F_Cu)
    z.SetZoneName("MODULE_NO_TRACKS_F")
    o = z.Outline()
    o.NewOutline()
    for x, y in [(32.9, 6.3), (43.1, 6.3), (43.1, 16.55), (32.9, 16.55)]:   # centre only; pads may escape inward
        o.Append(MM(OX + x), MM(OY + y))
    board.Add(z)


if __name__ == "__main__":
    board, fps, nets = build()
    keepout(board)
    module_track_keepout(board)
    out = os.path.join(CAD, "build", "zb1_placed.kicad_pcb")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    board.Save(out)
    # report module pad positions we care about
    u1 = fps["U1"]
    for n in ("1", "3", "19", "20", "23", "24", "45", "46"):
        pad = [p for p in u1.Pads() if p.GetNumber() == n][0]
        pos = pad.GetPosition()
        print(f"U1 pad {n}: ({pcbnew.ToMM(pos.x) - OX:.2f}, {pcbnew.ToMM(pos.y) - OY:.2f})")
    for ref, n in (("J1", "A6"), ("J2", "1"), ("J2", "11"), ("J5", "1"), ("J5", "16"), ("J6", "12")):
        pad = [p for p in fps[ref].Pads() if p.GetNumber() == n][0]
        pos = pad.GetPosition()
        print(f"{ref} pad {n}: ({pcbnew.ToMM(pos.x) - OX:.2f}, {pcbnew.ToMM(pos.y) - OY:.2f})")
    print("saved", out)
