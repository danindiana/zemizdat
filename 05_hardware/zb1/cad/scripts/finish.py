"""Stage 3 of the PCB flow: import the Freerouting session, restore GND fan-out, pour GND on all
layers, add silkscreen labels, fill zones, run DRC, save zb1.kicad_pcb + reports/drc.rpt."""
from __future__ import annotations
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CAD = os.path.dirname(HERE)
BUILD = os.path.join(CAD, "build")

import pcbnew  # noqa: E402
from gen_pcb import OX, OY, W, H  # noqa: E402
from zb1_design import PARTS  # noqa: E402

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



def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def silk_text(board, txt, x, y, size=0.6, layer=pcbnew.F_SilkS, angle=0, bold=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetPosition(P(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(size * (0.2 if bold else 0.15)))
    t.SetTextAngleDegrees(angle)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


def gnd_zone(board, layer, prio=0):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet("GND"))
    z.SetLocalClearance(MM(0.2))
    z.SetMinThickness(MM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(MM(0.25))
    z.SetThermalReliefSpokeWidth(MM(0.3))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(prio)
    z.SetZoneName(f"GND_{board.GetLayerName(layer)}")
    o = z.Outline()
    o.NewOutline()
    for x, y in [(0, 0), (W, 0), (W, H), (0, H)]:
        o.Append(MM(OX + x), MM(OY + y))
    board.Add(z)
    return z


def import_ses(board, path):
    """Add the wires and vias of a Specctra session (Freerouting output) to the board.
    (pcbnew.ImportSpecctraSES needs the GUI editor in KiCad 7, so this does it directly.)"""
    from sexp import parse, find, find1
    root = parse(open(path).read())[0]
    routes = find1(root, "routes")
    res = find1(routes, "resolution")
    scale = 1000.0 / float(res[2]) if res[1] == "um" else None     # session units -> nm
    layers = {board.GetLayerName(l): l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)}
    vias_ds = {}
    for ps in find(find1(routes, "library_out") or [], "padstack"):
        vias_ds[str(ps[1])] = ps
    def pt(x, y):
        return pcbnew.VECTOR2I(int(round(float(x) * scale)), int(round(-float(y) * scale)))
    existing = set()
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            existing.add(("v", round(t.GetPosition().x / 10000), round(t.GetPosition().y / 10000)))
        else:
            a, b = sorted([(round(t.GetStart().x / 10000), round(t.GetStart().y / 10000)), (round(t.GetEnd().x / 10000), round(t.GetEnd().y / 10000))])
            existing.add(("t", t.GetLayer(), a, b))
    nw = nv = dup = 0
    for net in find(find1(routes, "network_out"), "net"):
        ni = board.FindNet(str(net[1]))
        for w in find(net, "wire"):
            path_ = find1(w, "path")
            layer = layers[str(path_[1])]
            width = int(round(float(path_[2]) * scale))
            coords = path_[3:]
            pts = [pt(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
            for a, b in zip(pts, pts[1:]):
                k = ("t", layer, *sorted([(round(a.x / 10000), round(a.y / 10000)), (round(b.x / 10000), round(b.y / 10000))]))
                if k in existing:
                    dup += 1
                    continue
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(a); t.SetEnd(b); t.SetWidth(width); t.SetLayer(layer); t.SetNet(ni)
                board.Add(t); nw += 1
        for v in find(net, "via"):
            pos = pt(v[2], v[3])
            if ("v", round(pos.x / 10000), round(pos.y / 10000)) in existing:
                dup += 1
                continue
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pos)
            name = str(v[1])                      # e.g. Via[0-3]_600:300_um
            dia, drill = name.split("_")[1].split(":")
            via.SetWidth(pcbnew.FromMM(float(dia) / 1000)); via.SetDrill(pcbnew.FromMM(float(drill) / 1000))
            via.SetNet(ni)
            board.Add(via); nv += 1
    print(f"SES import: {nw} track segments, {nv} vias added; {dup} already present (fixed fan-out)")


def relocate_testpoints(board, failed_nets):
    """A stranded test pad has no electrical role beyond being reachable: move it to the nearest
    clear bottom-side spot next to its own net's copper."""
    import math
    import complete as CMP
    from shapely.geometry import Point as _Pt
    moved = []
    for fp in board.GetFootprints():
        if not fp.GetReference().startswith("TP"):
            continue
        pad = list(fp.Pads())[0]
        net = pad.GetNetname()
        if net not in failed_nets:
            continue
        items = CMP.item_shapes(board)
        mine = [g for n, L, g, o, c in items if n == net and o is not pad and pcbnew.B_Cu in L]
        others = [g for n, L, g, o, c in items if n != net and pcbnew.B_Cu in L]
        from gen_pcb import courtyard_poly
        from shapely.affinity import translate
        court = [translate(courtyard_poly(f2), OX, OY) for f2 in board.GetFootprints()
                 if f2.IsFlipped() and f2 is not fp]
        inner = CMP.box(OX + 1.2, OY + 1.2, OX + W - 1.2, OY + H - 1.2)
        best = None
        for g in mine:
            c = g.centroid
            for r in (1.2, 1.5, 1.8, 2.2, 2.6, 3.0):
                for k in range(24):
                    a = 2 * math.pi * k / 24
                    pt = _Pt(c.x + r * math.cos(a), c.y + r * math.sin(a))
                    disk = pt.buffer(0.5 + 0.3)
                    if not inner.contains(pt) or pt.x > OX + 45.0:
                        continue
                    if any(o.intersects(disk) for o in others) or any(cb.intersects(pt.buffer(1.05)) for cb in court):
                        continue
                    d = pt.distance(g)
                    if best is None or d < best[0]:
                        best = (d, pt)
        if best:
            fp.SetPosition(pcbnew.VECTOR2I(MM(best[1].x), MM(best[1].y)))
            moved.append(f"{fp.GetReference()}->({best[1].x - OX:.2f},{best[1].y - OY:.2f})")
    return moved


def trim_dangling(board, max_len=1.0):
    """Delete short track stubs with a free end, as long as connectivity does not change."""
    removed = 0
    for _ in range(5):
        board.BuildConnectivity()
        conn = board.GetConnectivity()
        base = conn.GetUnconnectedCount(True)
        cand = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"
                and pcbnew.ToMM(t.GetLength()) <= max_len and conn.TestTrackEndpointDangling(t, False)]
        if not cand:
            break
        for t in cand:
            board.Remove(t)
            board.BuildConnectivity()
            if board.GetConnectivity().GetUnconnectedCount(True) > base:
                board.Add(t)                # it mattered after all
            else:
                removed += 1
    return removed


FEATHER_12 = ["BAT", "EN", "USB", "13", "12", "11", "10", "9", "6", "5", "SCL", "SDA"]
FEATHER_16 = ["RST", "3V", "NC", "GND", "A0", "A1", "A2", "A3", "A4", "NC", "SCK", "MO", "MI", "RX", "TX", "NC"]


def main():
    board = load_with_project(os.path.join(BUILD, "zb1_fanout.kicad_pcb"))
    gnd_items = [(t.GetClass(), t.GetStart() if t.GetClass() == "PCB_TRACK" else t.GetPosition(),
                  t.GetEnd() if t.GetClass() == "PCB_TRACK" else None, t.GetWidth(),
                  t.GetLayer() if t.GetClass() == "PCB_TRACK" else None,
                  t.GetDrill() if t.GetClass() == "PCB_VIA" else None)
                 for t in board.GetTracks() if t.GetNetname() == "GND"]
    ses = os.path.join(BUILD, "zb1.ses")
    import_ses(board, ses)
    if "--no-complete" not in sys.argv:
        import complete as CMP
        bad = CMP.keepout_offenders(board)
        if bad:
            names = sorted({t.GetNetname() for t in bad})
            for t in bad:
                board.Remove(t)
            print(f"removed {len(bad)} item(s) inside keep-outs on nets {names}")
        routed, failed = CMP.complete(board, OX, OY, W, H)
        print(f"maze router: completed {routed} connection(s); could not route: {failed}")
        moved = relocate_testpoints(board, failed)
        if moved:
            routed, failed = CMP.complete(board, OX, OY, W, H)
            print(f"after moving {moved}: completed {routed}; could not route: {failed}")
        print("removed dangling stubs:", trim_dangling(board))
    have_gnd = sum(1 for t in board.GetTracks() if t.GetNetname() == "GND")
    if have_gnd < len(gnd_items):               # importer cleared the board's tracks: restore fan-out
        gnd = board.FindNet("GND")
        for cls, a, b, w, layer, drill in gnd_items:
            if cls == "PCB_VIA":
                v = pcbnew.PCB_VIA(board); v.SetPosition(a); v.SetWidth(w); v.SetDrill(drill); v.SetNet(gnd)
                board.Add(v)
            else:
                t = pcbnew.PCB_TRACK(board); t.SetStart(a); t.SetEnd(b); t.SetWidth(w); t.SetLayer(layer)
                t.SetNet(gnd); board.Add(t)
        print(f"restored {len(gnd_items)} GND fan-out items")

    for ref in ("SJ1", "SJ2"):          # bridged solder jumpers: copper bridge is an intentional net tie
        fp = board.FindFootprintByReference(ref)
        fp.ClearNetTiePadGroups()
        fp.AddNetTiePadGroup("1,2")
    # keep the pour out of the bridged-jumper gaps (net-tie copper is not seen by the filler)
    for ref in ("SJ1", "SJ2"):
        fp = board.FindFootprintByReference(ref)
        c = fp.GetPosition()
        horiz = int(fp.GetOrientationDegrees()) % 180 == 0
        dx, dy = (0.45, 1.0) if horiz else (1.0, 0.45)
        k = pcbnew.ZONE(board)
        k.SetIsRuleArea(True); k.SetDoNotAllowCopperPour(True); k.SetDoNotAllowTracks(False)
        k.SetDoNotAllowVias(False); k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False)
        k.SetLayer(fp.GetLayer()); k.SetZoneName(f"NO_POUR_{ref}")
        o = k.Outline(); o.NewOutline()
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            o.Append(c.x + MM(sx * dx), c.y + MM(sy * dy))
        board.Add(k)
    # library model paths exactly as in KiCad's own footprints (avoids spurious library-mismatch flags)
    for fp in board.GetFootprints():
        ms = [(str(m.m_Filename), (m.m_Offset.x, m.m_Offset.y, m.m_Offset.z),
               (m.m_Rotation.x, m.m_Rotation.y, m.m_Rotation.z), (m.m_Scale.x, m.m_Scale.y, m.m_Scale.z), m.m_Show)
              for m in fp.Models()]
        if not any("KICAD7_3DMODEL_DIR" in f for f, *_ in ms):
            continue
        fp.Models().clear()
        for f, off, rot, sc, show in ms:
            m = pcbnew.FP_3DMODEL()
            m.m_Filename = f.replace("KICAD7_3DMODEL_DIR", "KICAD6_3DMODEL_DIR")
            m.m_Offset = pcbnew.VECTOR3D(*off); m.m_Rotation = pcbnew.VECTOR3D(*rot); m.m_Scale = pcbnew.VECTOR3D(*sc)
            m.m_Show = show
            fp.Add3DModel(m)
    for i, l in enumerate((pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)):
        gnd_zone(board, l)

    # ---- silkscreen
    dnp = {p["ref"] for p in PARTS if p.get("dnp")}
    for fp in board.GetFootprints():
        r = fp.Reference()
        ref = fp.GetReference()
        r.SetTextSize(pcbnew.VECTOR2I(MM(0.7), MM(0.7)))
        r.SetTextThickness(MM(0.12))
        # passives and mechanical parts: reference only on the assembly drawing (F.Fab/B.Fab)
        if ref.startswith(("H", "J5", "J6", "R", "C", "TP")) or ref == "U1":
            r.SetVisible(False)
        fp.Value().SetVisible(False)
    for i, name in enumerate(FEATHER_12):
        silk_text(board, name, 16.51 + 2.54 * i, 2.85, 0.6)
    for i, name in enumerate(FEATHER_16):
        silk_text(board, name, 6.35 + 2.54 * i, 20.0, 0.6)
    silk_text(board, "ZB-1", 36.5, 11.4, 1.6, bold=True)
    silk_text(board, "ZEMIZDAT rev0.1", 36.5, 13.6, 0.8)
    silk_text(board, "ANTENNA", 48.1, 11.43, 0.8, angle=90)
    silk_text(board, "USB-C", 1.0, 11.43, 0.6, angle=90)
    silk_text(board, "microSD", 9.0, 11.43, 1.0, layer=pcbnew.B_SilkS, angle=90)
    silk_text(board, "ZB-1 rev0.1 bottom", 38.0, 21.0 - 0.0, 0.7, layer=pcbnew.B_SilkS)
    j3 = board.FindFootprintByReference("J3")
    pads = {p.GetNumber(): p.GetPosition() for p in j3.Pads()}
    for num, sign in (("1", "-"), ("2", "+")):
        pp = pads[num]
        silk_text(board, sign, pcbnew.ToMM(pp.x) - OX, pcbnew.ToMM(pp.y) - OY - 2.2, 1.0, bold=True)
    for ref, label in (("SW1", "RST"), ("SW2", "BOOT"), ("LED2", "CHG")):
        fp = board.FindFootprintByReference(ref)
        pos = fp.GetPosition()
        silk_text(board, label, pcbnew.ToMM(pos.x) - OX, pcbnew.ToMM(pos.y) - OY + (2.6 if ref != "LED2" else -1.2), 0.6)
    sj1 = board.FindFootprintByReference("SJ1").GetPosition()
    silk_text(board, "CUT=I", pcbnew.ToMM(sj1.x) - OX, pcbnew.ToMM(sj1.y) - OY + 1.9, 0.6, layer=pcbnew.B_SilkS)

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    out = os.path.join(CAD, "zb1.kicad_pcb")
    board.Save(out)
    os.makedirs(os.path.join(CAD, "reports"), exist_ok=True)
    rpt = os.path.join(CAD, "reports", "drc.rpt")
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    print("saved", out, "DRC:", rpt)


if __name__ == "__main__":
    main()
