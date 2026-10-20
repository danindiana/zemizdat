"""Stage 2 of the PCB flow: GND fan-out, autoroute with Freerouting, pour planes, DRC.

1. Load build/zb1_placed.kicad_pcb (with the project's net classes).
2. Give every SMD GND pad a short stub + via to the In1 GND plane (module centre pads: via-in-pad).
3. Export a routing copy with GND removed (Freerouting does not know about planes), run Freerouting
   (built locally from freerouting v1.4.4 source) headless, import the session.
4. Re-add the GND fan-out, add GND pours on all four layers, fill, run DRC, save zb1.kicad_pcb.
"""
from __future__ import annotations
import math
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CAD = os.path.dirname(HERE)
BUILD = os.path.join(CAD, "build")

import pcbnew  # noqa: E402
from shapely.geometry import box, Point, LineString  # noqa: E402
from gen_pcb import OX, OY, W, H, ANT_X  # noqa: E402

MM = pcbnew.FromMM

def load_with_project(pcb_path):
    """LoadBoard with the current zb1.kicad_pro rules (KiCad reads <name>.kicad_pro next to the board)."""
    import shutil as _sh
    pro = os.path.splitext(pcb_path)[0] + ".kicad_pro"
    src = os.path.join(CAD, "zb1.kicad_pro")
    if os.path.abspath(pro) != os.path.abspath(src):
        _sh.copy(src, pro)
    for ext in (".kicad_prl",):
        try:
            os.remove(os.path.splitext(pcb_path)[0] + ext)
        except FileNotFoundError:
            pass
    b = pcbnew.LoadBoard(pcb_path)
    b.SynchronizeNetsAndNetClasses(True)
    return b

T = pcbnew.ToMM
FREEROUTING = os.environ.get("FREEROUTING_JAR", "/home/claude/freerouting/fr144/freerouting-1.4.4-zb1.jar")
JAVA_CP = f"{FREEROUTING}:/usr/share/java/log4j-api.jar:/usr/share/java/log4j-core.jar:/usr/share/java/jh.jar"

VIA_D, VIA_DRILL, CLR = 0.5, 0.25, 0.15
OPT_SECONDS = int(os.environ.get("ZB1_OPT_SECONDS", "600"))   # cap on Freerouting post-route optimisation


def pad_box(pad):
    b = pad.GetBoundingBox()
    return box(T(b.GetLeft()) - OX, T(b.GetTop()) - OY, T(b.GetRight()) - OX, T(b.GetBottom()) - OY)


def load():
    src = os.path.join(BUILD, "zb1_placed.kicad_pcb")
    dst = os.path.join(CAD, "zb1.kicad_pcb")
    shutil.copy(src, dst)
    return load_with_project(dst)


def fanout(board):
    gnd = board.FindNet("GND")
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    obstacles = [(pad_box(p), p) for p in pads if p.GetNetname() != "GND"]
    holes = [Point(T(p.GetPosition().x) - OX, T(p.GetPosition().y) - OY).buffer(T(p.GetDrillSize().x) / 2)
             for p in pads if p.GetAttribute() in (pcbnew.PAD_ATTRIB_NPTH, pcbnew.PAD_ATTRIB_PTH)]
    for fp in board.GetFootprints():
        if fp.GetReference().startswith("H"):
            holes.append(Point(T(fp.GetPosition().x) - OX, T(fp.GetPosition().y) - OY).buffer(1.1))
    inner = box(0, 0, W, H).buffer(-0.5)
    keep = box(ANT_X - 0.2, -1, W + 1, H + 1)
    # rule areas embedded in footprints (e.g. under the USB-C receptacle) are no-go for vias too
    from shapely.geometry import Polygon
    for fp in board.GetFootprints():
        for z in fp.Zones():
            if z.GetIsRuleArea() and z.GetDoNotAllowVias():
                o = z.Outline()
                pts = [(T(o.CVertex(i).x) - OX, T(o.CVertex(i).y) - OY) for i in range(o.TotalVertices())]
                if len(pts) >= 3:
                    keep = keep.union(Polygon(pts))
    vias = []
    items = []

    def via_ok(c):
        circ = c.buffer(VIA_D / 2 + CLR)
        if not inner.contains(c.buffer(VIA_D / 2)) or keep.intersects(circ):
            return False
        if any(o.intersects(circ) for o, _ in obstacles):
            return False
        if any(h.distance(c) < VIA_D / 2 + 0.25 for h in holes):
            return False
        if any(v.distance(c) < VIA_D + 0.1 for v in vias):
            return False
        return True

    def add_via(c, track_from=None, layer=None):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(MM(OX + c.x), MM(OY + c.y)))
        v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DRILL)); v.SetNet(gnd)
        board.Add(v); items.append(v); vias.append(c)
        if track_from is not None:
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(MM(OX + track_from.x), MM(OY + track_from.y)))
            t.SetEnd(pcbnew.VECTOR2I(MM(OX + c.x), MM(OY + c.y)))
            t.SetWidth(MM(0.3)); t.SetLayer(layer); t.SetNet(gnd)
            board.Add(t); items.append(t)

    done, failed = 0, []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != "GND" or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            pc = Point(T(p.GetPosition().x) - OX, T(p.GetPosition().y) - OY)
            pb = pad_box(p)
            w = pb.bounds[2] - pb.bounds[0]
            h = pb.bounds[3] - pb.bounds[1]
            layer = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu   # (GetLayer() lies for flipped pads)
            if fp.GetReference() == "U1":
                if min(w, h) >= 1.0:                                      # module centre: via-in-pad
                    add_via(pc); done += 1
                continue                       # perimeter GND pads join the F.Cu pour + centre pad
            placed = False
            for d in [0.6, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5]:
                for k in range(16):
                    a = 2 * math.pi * k / 16
                    c = Point(pc.x + (w / 2 + d) * math.cos(a), pc.y + (h / 2 + d) * math.sin(a))
                    if not via_ok(c):
                        continue
                    seg = LineString([pc, c]).buffer(0.15 + CLR)
                    if any(o.intersects(seg) for o, q in obstacles):
                        continue
                    add_via(c, pc, layer); placed = True; done += 1
                    break
                if placed:
                    break
            if not placed:
                failed.append(f"{fp.GetReference()}.{p.GetNumber()}")
    print(f"GND fan-out: {done} vias; no spot (left to the copper pour): {len(failed)} {failed[:12]}")
    return items


def routing_copy(board, path):
    """Save a copy with a GND plane on In1 and export a Specctra DSN. Freerouting treats the plane as
    a conduction area, so GND pads that already have a fan-out via count as connected and the fan-out
    tracks/vias are respected as fixed GND copper."""
    tmp = os.path.join(BUILD, "zb1_route_in.kicad_pcb")
    board.Save(tmp)
    b2 = load_with_project(tmp)
    z = pcbnew.ZONE(b2)
    z.SetLayer(pcbnew.In1_Cu)
    z.SetNet(b2.FindNet("GND"))
    o = z.Outline(); o.NewOutline()
    for x, y in [(0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)]:
        o.Append(MM(OX + x), MM(OY + y))
    b2.Add(z)
    pcbnew.ZONE_FILLER(b2).Fill(b2.Zones())
    for t in b2.GetTracks():                 # fan-out is fixed: the router must not move it
        if t.GetNetname() == "GND":
            t.SetLocked(True)
    ok = pcbnew.ExportSpecctraDSN(b2, path)
    print("DSN export:", ok, path)


def freeroute(dsn, ses, passes=100):
    cmd = ["xvfb-run", "-a", "java", f"-Dzb1.opt.seconds={OPT_SECONDS}", "-cp", JAVA_CP, "eu.mihosoft.freerouting.gui.MainApplication",
           "-de", dsn, "-do", ses, "-mp", str(passes)]
    print("running:", " ".join(cmd[3:]))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    log = (r.stdout + r.stderr)
    open(os.path.join(BUILD, "freerouting.log"), "w").write(log)
    print("freerouting exit", r.returncode, "ses exists:", os.path.exists(ses))


def second_pass(passes=100):
    """Seed Freerouting with the first-pass session (as movable wiring) so it can rip up and
    finish the connections it left open. Result replaces build/zb1.ses if it routed more."""
    from finish import import_ses
    ses1 = os.path.join(BUILD, "zb1.ses")
    b = load_with_project(os.path.join(BUILD, "zb1_fanout.kicad_pcb"))
    import_ses(b, ses1)
    tmp = os.path.join(BUILD, "zb1_pass2_in.kicad_pcb")
    b.Save(tmp)
    dsn = os.path.join(BUILD, "zb1_pass2.dsn")
    ses2 = os.path.join(BUILD, "zb1_pass2.ses")
    b2 = load_with_project(tmp)
    z = pcbnew.ZONE(b2)
    z.SetLayer(pcbnew.In1_Cu); z.SetNet(b2.FindNet("GND"))
    o = z.Outline(); o.NewOutline()
    for x, y in [(0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)]:
        o.Append(MM(OX + x), MM(OY + y))
    b2.Add(z)
    pcbnew.ZONE_FILLER(b2).Fill(b2.Zones())
    print("pass-2 DSN:", pcbnew.ExportSpecctraDSN(b2, dsn))
    if os.path.exists(ses2):
        os.remove(ses2)
    freeroute(dsn, ses2, passes)
    return ses2


def unrouted(ses):
    """Unconnected-item count after importing `ses` (uses the finish stage without saving)."""
    from finish import import_ses
    b = load_with_project(os.path.join(BUILD, "zb1_fanout.kicad_pcb"))
    import_ses(b, ses)
    for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b); z.SetLayer(l); z.SetNet(b.FindNet("GND"))
        o = z.Outline(); o.NewOutline()
        for x, y in [(0, 0), (W, 0), (W, H), (0, H)]:
            o.Append(MM(OX + x), MM(OY + y))
        b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.BuildConnectivity()
    return b.GetConnectivity().GetUnconnectedCount(True)


if __name__ == "__main__" and "--pass2" in sys.argv:
    ses1 = os.path.join(BUILD, "zb1.ses")
    n1 = unrouted(ses1)
    ses2 = second_pass()
    n2 = unrouted(ses2)
    print(f"unconnected after pass 1: {n1}; after pass 2: {n2}")
    if n2 < n1:
        shutil.copy(ses2, ses1)
        print("pass 2 adopted")
    sys.exit(0)

if __name__ == "__main__":
    board = load()
    fan = fanout(board)
    from complete import preroute
    import json as _json
    cfg = _json.loads(os.environ.get("ZB1_PREROUTE", "null")) or \
        [["VBUS", ["U5", "5"], ["J1", "A9"]], "USB_DP", "USB_DN", "XTAL32_P", "XTAL32_N"]
    cfg = [tuple([c[0], tuple(c[1]), tuple(c[2])]) if isinstance(c, list) else c for c in cfg]
    pre = preroute(board, OX, OY, W, H, cfg)
    print("pre-routed (locked):", pre)
    dsn = os.path.join(BUILD, "zb1.dsn")
    ses = os.path.join(BUILD, "zb1.ses")
    routing_copy(board, dsn)
    if "--no-route" not in sys.argv:
        if os.path.exists(ses):
            os.remove(ses)
        freeroute(dsn, ses)
    board.Save(os.path.join(BUILD, "zb1_fanout.kicad_pcb"))
