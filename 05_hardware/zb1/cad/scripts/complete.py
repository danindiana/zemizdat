"""Finish connections the autorouter left open: a small net-aware maze router.

Grid A* (0.05 mm) over the three routing layers (F.Cu, In2, B.Cu) with through vias. Every
existing piece of copper of another net is an obstacle, inflated by clearance + half the track
width; keep-out rule areas and the board edge are respected. Paths become ordinary KiCad tracks
and vias, so KiCad's DRC checks them like everything else.
"""
from __future__ import annotations
import heapq
import math

import numpy as np
import pcbnew
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString, Point, Polygon, box

RES = 0.05                      # mm per cell
LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
CLR = 0.20                      # router clearance: DRC minimum 0.15 + grid discretisation margin
VIA_D, VIA_DRILL = 0.5, 0.25
EDGE_CLR = 0.3
T = pcbnew.ToMM


def width_for(net):
    return 0.3 if net in {"VBUS", "VSYS", "VBAT", "BATN", "3V3", "3V3_LDO", "SD_VDD"} else 0.15


class Grid:
    def __init__(self, board, ox, oy, w, h):
        self.b, self.ox, self.oy = board, ox, oy
        self.nx, self.ny = int(math.ceil(w / RES)) + 1, int(math.ceil(h / RES)) + 1
        self.w, self.h = w, h

    def c(self, x, y):
        return (x - self.ox) / RES, (y - self.oy) / RES

    def raster(self, geom, img=None, value=1):
        """Draw a shapely geometry into a PIL 'I' image (mode int)."""
        img = img or Image.new("I", (self.nx, self.ny), 0)
        d = ImageDraw.Draw(img)
        geoms = getattr(geom, "geoms", [geom])
        for g in geoms:
            if g.is_empty:
                continue
            pts = [self.c(x, y) for x, y in g.exterior.coords]
            d.polygon(pts, fill=value)
        return img


def item_shapes(board):
    """[(netname, set(layers), shapely geom in mm)] for pads, tracks, vias."""
    out = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            g = box(T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom()))
            if p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
                pos = p.GetPosition()
                g = Point(T(pos.x), T(pos.y)).buffer(T(p.GetSize().x) / 2)
            layers = {l for l in LAYERS + [pcbnew.In1_Cu] if p.IsOnLayer(l)}
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                layers = set(LAYERS) | {pcbnew.In1_Cu}
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    pos = p.GetPosition()
                    g = Point(T(pos.x), T(pos.y)).buffer(T(p.GetDrillSize().x) / 2)
            core = g.buffer(-0.3 * min(g.bounds[2] - g.bounds[0], g.bounds[3] - g.bounds[1]))
            out.append((p.GetNetname() or f"__np_{id(p)}", layers, g, p, core if not core.is_empty else g))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            pos = t.GetPosition()
            out.append((t.GetNetname(), set(LAYERS) | {pcbnew.In1_Cu},
                        Point(T(pos.x), T(pos.y)).buffer(T(t.GetWidth()) / 2), t,
                        Point(T(pos.x), T(pos.y)).buffer(0.08)))
        else:
            s, e = t.GetStart(), t.GetEnd()
            g = LineString([(T(s.x), T(s.y)), (T(e.x), T(e.y))]).buffer(T(t.GetWidth()) / 2)
            core = LineString([(T(s.x), T(s.y)), (T(e.x), T(e.y))]).buffer(0.03)
            out.append((t.GetNetname(), {t.GetLayer()}, g, t, core))
    return out


def clusters(items, net):
    mine = [(L, g, c) for n, L, g, _, c in items if n == net]
    parent = list(range(len(mine)))

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(mine)):
        for j in range(i + 1, len(mine)):
            if mine[i][0] & mine[j][0] and mine[i][1].intersects(mine[j][1]):
                parent[f(i)] = f(j)
    groups = {}
    for i, it in enumerate(mine):
        groups.setdefault(f(i), []).append(it)
    return list(groups.values())


def _fp_zones(board):
    out = []
    for fp in board.GetFootprints():
        try:
            out += list(fp.Zones())
        except TypeError:            # some KiCad 7 builds return an opaque vector here
            pass
    return out


def _file_keepouts(path):
    """[(layer ids or {'*'}, tracks_not_allowed, vias_not_allowed, [(x, y)...])] for every keep-out
    zone written inside a footprint in the .kicad_pcb file (absolute coordinates)."""
    import os
    from sexp import parse, find, find1
    if not path or not os.path.exists(path):
        return []
    root = parse(open(path, encoding="utf-8").read())[0]
    names = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu}
    out = []
    for fp in find(root, "footprint"):
        for z in find(fp, "zone"):
            ko = find1(z, "keepout")
            if ko is None:
                continue
            flags = {str(x[0]): str(x[1]) for x in ko[1:] if isinstance(x, list)}
            lay = find1(z, "layers") or find1(z, "layer")
            ls = set()
            for a in lay[1:]:
                a = str(a)
                ls |= {"*"} if a.startswith("*.Cu") or a == "*.Cu" else ({names[a]} if a in names else set())
            poly = find1(find1(z, "polygon"), "pts")
            pts = [(float(p[1]), float(p[2])) for p in poly[1:] if isinstance(p, list) and p[0] == "xy"]
            if len(pts) >= 3:
                out.append((ls, flags.get("tracks") == "not_allowed", flags.get("vias") == "not_allowed", pts))
    return out


def _static(board, ox, oy, w, h):
    g = Grid(board, ox, oy, w, h)
    # static obstacles: board edge band, NPTH holes, keep-out rule areas
    inner = box(ox, oy, ox + w, oy + h).buffer(-EDGE_CLR)
    edge_band = np.asarray(g.raster(box(ox - 1, oy - 1, ox + w + 1, oy + h + 1))) > 0
    edge_band &= ~(np.asarray(g.raster(inner)) > 0)
    no_track = {l: edge_band.copy() for l in LAYERS}
    no_via = edge_band.copy()
    # footprint-embedded keep-outs: KiCad 7's Python binding hides them, so read the saved file
    for layers_, no_tr, no_vi, pts in _file_keepouts(board.GetFileName()):
        m = np.asarray(g.raster(Polygon(pts))) > 0
        for l in LAYERS:
            if no_tr and (l in layers_ or "*" in layers_):
                no_track[l] |= m
        if no_vi:
            no_via |= m
    for z in [board.GetArea(i) for i in range(board.GetAreaCount())] + _fp_zones(board):
        if not z.GetIsRuleArea():
            continue
        o = z.Outline()
        pts = [(T(o.CVertex(i).x), T(o.CVertex(i).y)) for i in range(o.TotalVertices())]
        if len(pts) < 3:
            continue
        m = np.asarray(g.raster(Polygon(pts))) > 0
        for l in LAYERS:
            if z.IsOnLayer(l) and z.GetDoNotAllowTracks():
                no_track[l] |= m
        if z.GetDoNotAllowVias():
            no_via |= m

    # a via/track must not merely avoid the keep-out with its centre: grow the areas by its radius
    grow_v = distance_transform_edt(~no_via) * RES <= VIA_D / 2 + 0.02
    no_via = no_via | grow_v
    for l in LAYERS:
        no_track[l] = no_track[l] | (distance_transform_edt(~no_track[l]) * RES <= 0.16)
    return g, no_track, no_via


def keepout_offenders(board):
    """Nets having a via/track inside a keep-out (board rule areas + footprint keep-outs)."""
    from shapely.geometry import Polygon as _P
    areas = []
    for z in [board.GetArea(i) for i in range(board.GetAreaCount())]:
        if z.GetIsRuleArea() and (z.GetDoNotAllowVias() or z.GetDoNotAllowTracks()):
            o = z.Outline()
            pts = [(T(o.CVertex(i).x), T(o.CVertex(i).y)) for i in range(o.TotalVertices())]
            ls = {l for l in LAYERS if z.IsOnLayer(l)}
            areas.append((ls, z.GetDoNotAllowTracks(), z.GetDoNotAllowVias(), _P(pts)))
    for ls, tr, vi, pts in _file_keepouts(board.GetFileName()):
        areas.append((set(LAYERS) if "*" in ls else ls, tr, vi, _P(pts)))
    bad = []
    for n, L, gm, obj, _c in item_shapes(board):
        if obj.GetClass() not in ("PCB_TRACK", "PCB_VIA") or n == "GND":
            continue
        for ls, tr, vi, poly in areas:
            isvia = obj.GetClass() == "PCB_VIA"
            if ((isvia and vi) or (not isvia and tr and (L & ls))) and gm.intersects(poly):
                bad.append(obj)
                break
    # take the segments that end on an offending via with it, so the repair is local
    vpos = {(o.GetPosition().x, o.GetPosition().y) for o in bad if o.GetClass() == "PCB_VIA"}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t not in bad and \
                ((t.GetStart().x, t.GetStart().y) in vpos or (t.GetEnd().x, t.GetEnd().y) in vpos):
            bad.append(t)
    return bad


def complete(board, ox, oy, w, h, skip=("GND",), max_routes=60, ripup=True):
    g, no_track, no_via = _static(board, ox, oy, w, h)
    ctx = dict(g=g, no_track=no_track, no_via=no_via)
    routed, failed = 0, []
    hard = set(skip)
    for _ in range(max_routes):
        items = item_shapes(board)
        todo = next_open(items, hard)
        if todo is None:
            break
        net, cl = todo
        if route_net(board, ctx, items, net, cl) is not None:
            routed += 1
            continue
        if ripup and ripup_route(board, ctx, net, set(skip)):
            routed += 1
            continue
        failed.append(net)
        hard.add(net)
    return routed, failed


def preroute(board, ox, oy, w, h, nets):
    """Route `nets` first (on a nearly empty board) and lock them, so the autorouter works around them."""
    g, no_track, no_via = _static(board, ox, oy, w, h)
    ctx = dict(g=g, no_track=no_track, no_via=no_via)
    done = []
    for net in nets:
        if isinstance(net, tuple):            # (net, (refA, padA), (refB, padB)): one specific hop
            name, (ra, pa), (rb, pb) = net
            items = item_shapes(board)
            def pick(r, n):
                pads = [p for p in board.FindFootprintByReference(r).Pads() if p.GetNumber() == n]
                return [(L, g, c) for nn, L, g, o, c in items
                        if o.GetClass() == "PAD" and any(o.GetPosition() == p.GetPosition() for p in pads)]
            added = route_net(board, ctx, items, name, [pick(ra, pa), pick(rb, pb)])
            if added is None:
                print("  pre-route failed:", net)
            else:
                for t in added:
                    t.SetLocked(True)
                done.append(f"{name}:{ra}.{pa}-{rb}.{pb}")
            continue
        for _ in range(10):
            items = item_shapes(board)
            cl = clusters(items, net)
            if len(cl) < 2:
                break
            added = route_net(board, ctx, items, net, cl)
            if added is None:
                print("  pre-route failed:", net)
                break
            for t in added:
                t.SetLocked(True)
            done.append(net)
    return done


def next_open(items, skip):
    nets = sorted({n for n, _, _, _, _ in items if n and not n.startswith("__np_") and n not in skip})
    for n in nets:
        cl = clusters(items, n)
        if len(cl) > 1:
            return n, cl
    return None


def route_net(board, ctx, items, net, cl):
    """Join the largest cluster of `net` to the nearest other one. Returns added items or None."""
    g, no_track, no_via = ctx["g"], ctx["no_track"], ctx["no_via"]
    tw = width_for(net)
    other = {}
    for l in LAYERS:
        img = Image.new("I", (g.nx, g.ny), 0)
        for n, L, geom, _, _c in items:
            if l in L and n != net:
                g.raster(geom, img, 1)
        other[l] = np.asarray(img) > 0
    dist = {l: distance_transform_edt(~other[l]) * RES for l in LAYERS}
    free = {l: (dist[l] > tw / 2 + CLR) & ~no_track[l] for l in LAYERS}
    via_ok = ~no_via
    for l in LAYERS:
        via_ok = via_ok & (dist[l] > VIA_D / 2 + CLR)
    cl = sorted(cl, key=lambda c: -len(c))
    src = {l: np.zeros((g.ny, g.nx), bool) for l in LAYERS}
    dst = {l: np.zeros((g.ny, g.nx), bool) for l in LAYERS}
    for k, group in enumerate(cl):
        for L, geom, core in group:
            m = np.asarray(g.raster(core)) > 0
            for l in LAYERS:
                if l in L:
                    (src if k == 0 else dst)[l] |= m
    goal_any = np.zeros((g.ny, g.nx), bool)
    for l in LAYERS:
        goal_any |= dst[l]
    path = astar(free, via_ok, src, dst, distance_transform_edt(~goal_any))
    if path is None:
        return None
    return add_path(board, g, path, net, tw)


def _snapshot(t):
    """Plain-integer copy (KiCad position objects are references into the item and die with it)."""
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition()
        return ("v", str(t.GetNetname()), int(p.x), int(p.y), int(t.GetWidth()), int(t.GetDrill()))
    a, b = t.GetStart(), t.GetEnd()
    return ("t", str(t.GetNetname()), int(a.x), int(a.y), int(b.x), int(b.y), int(t.GetWidth()), int(t.GetLayer()))


def _restore(board, snap):
    ni = board.FindNet(snap[1])
    if snap[0] == "v":
        v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(snap[2], snap[3]))
        v.SetWidth(snap[4]); v.SetDrill(snap[5]); v.SetNet(ni); board.Add(v)
    else:
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(snap[2], snap[3])); t.SetEnd(pcbnew.VECTOR2I(snap[4], snap[5]))
        t.SetWidth(snap[6]); t.SetLayer(snap[7]); t.SetNet(ni); board.Add(t)


def ripup_route(board, ctx, net, protected, corridor=1.2, max_victims=16):
    """Remove other nets' routing near the open connection, route `net`, re-route the victims.
    Keep only if everything connects again; otherwise restore the board exactly."""
    items = item_shapes(board)
    cl = sorted(clusters(items, net), key=lambda c: -len(c))
    a = unary([gm for _, gm, _c in cl[0]])
    b = unary([gm for c in cl[1:] for _, gm, _c in c])
    pa, pb = nearest(a, b)
    zone = LineString([pa, pb]).buffer(corridor)
    victims = []
    for n, L, gm, obj, _c in items:
        if obj.GetClass() in ("PCB_TRACK", "PCB_VIA") and n not in protected and n != net \
                and n != "GND" and gm.intersects(zone) and n not in victims:
            victims.append(n)
    if len(victims) > max_victims:
        # fall back to clearing only around the stranded (smaller) piece's escape
        small = unary([gm for c in cl[1:] for _, gm, _c in c]) if len(cl[1:]) == 1 else a
        zone = small.buffer(1.6)
        victims = []
        for n, L, gm, obj, _c in items:
            if obj.GetClass() in ("PCB_TRACK", "PCB_VIA") and n not in protected and n != net \
                    and n != "GND" and gm.intersects(zone) and n not in victims:
                victims.append(n)
    if not victims or len(victims) > max_victims:
        print(f"  rip-up skipped for {net}: {len(victims)} nets in the way")
        return False
    removed = []
    for t in list(board.GetTracks()):
        if t.GetNetname() in victims:      # pre-routes may move; GND fan-out is never a victim
            removed.append(_snapshot(t)); board.Remove(t)
    added = []
    ok = True
    items = item_shapes(board)
    r = route_net(board, ctx, items, net, clusters(items, net))
    if r is None:
        ok = False
    else:
        added += r
        for _ in range(40):
            items = item_shapes(board)
            todo = next_open([it for it in items if it[0] in victims + [net]], set())
            if todo is None:
                break
            r = route_net(board, ctx, items, *todo)
            if r is None:
                ok = False
                break
            added += r
    if ok:
        print(f"  rip-up: routed {net} after re-routing {victims}")
        return True
    print(f"  rip-up for {net} failed (victims {victims}); board restored")
    for t in added:
        board.Remove(t)
    for snap in removed:
        _restore(board, snap)
    return False


def unary(gs):
    from shapely.ops import unary_union
    return unary_union(gs)


def nearest(a, b):
    from shapely.ops import nearest_points
    p, q = nearest_points(a, b)
    return (p.x, p.y), (q.x, q.y)


def astar(free, via_ok, src, dst, hmap):
    L = len(LAYERS)
    ny, nx = hmap.shape
    INF = 1e18
    best = {}
    heap = []
    for li, l in enumerate(LAYERS):
        ys, xs = np.nonzero(src[l])
        for y, x in zip(ys.tolist(), xs.tolist()):
            k = (li, y, x)
            best[k] = 0.0
            heapq.heappush(heap, (hmap[y, x], 0.0, li, y, x, None))
    came = {}
    moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
             (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
    VIA_COST = 30.0
    fr = [free[l] for l in LAYERS]
    dsts = [dst[l] for l in LAYERS]
    n = 0
    while heap:
        f, gc, li, y, x, prev = heapq.heappop(heap)
        k = (li, y, x)
        if gc > best.get(k, INF):
            continue
        if k not in came:
            came[k] = prev
        if dsts[li][y, x]:
            out = [k]
            while came[out[-1]] is not None:
                out.append(came[out[-1]])
            return out[::-1]
        n += 1
        if n > 3_000_000:
            return None
        for dy, dx, cst in moves:
            yy, xx = y + dy, x + dx
            if 0 <= yy < ny and 0 <= xx < nx and (fr[li][yy, xx] or dsts[li][yy, xx]):
                if dx and dy and not (fr[li][y, xx] or dsts[li][y, xx]) and not (fr[li][yy, x] or dsts[li][yy, x]):
                    continue
                ng = gc + cst
                kk = (li, yy, xx)
                if ng < best.get(kk, INF):
                    best[kk] = ng
                    came.pop(kk, None)
                    heapq.heappush(heap, (ng + hmap[yy, xx], ng, li, yy, xx, k))
                    came[kk] = k
        if via_ok[y, x]:
            for lj in range(L):
                if lj != li and (fr[lj][y, x] or dsts[lj][y, x]):
                    ng = gc + VIA_COST
                    kk = (lj, y, x)
                    if ng < best.get(kk, INF):
                        best[kk] = ng
                        heapq.heappush(heap, (ng + hmap[y, x], ng, lj, y, x, k))
                        came[kk] = k
    return None


def add_path(board, g, path, net, tw):
    ni = board.FindNet(net)
    added = []

    def pt(y, x):
        return pcbnew.VECTOR2I(pcbnew.FromMM(g.ox + x * RES), pcbnew.FromMM(g.oy + y * RES))
    # split into same-layer runs; vias at layer changes
    runs, cur = [], [path[0]]
    last_via = None
    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            runs.append(cur)
            cur = [b]
            if last_via == (a[1], a[2]):
                continue                      # consecutive layer changes share one through via
            last_via = (a[1], a[2])
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pt(a[1], a[2])); v.SetWidth(pcbnew.FromMM(VIA_D)); v.SetDrill(pcbnew.FromMM(VIA_DRILL))
            v.SetNet(ni); board.Add(v); added.append(v)
        else:
            cur.append(b)
    runs.append(cur)
    for run in runs:
        if len(run) < 2:
            continue
        layer = LAYERS[run[0][0]]
        # collapse collinear steps
        pts = [run[0]]
        for i in range(1, len(run) - 1):
            d1 = (run[i][1] - pts[-1][1], run[i][2] - pts[-1][2])
            d2 = (run[i + 1][1] - run[i][1], run[i + 1][2] - run[i][2])
            if d1[0] * d2[1] != d1[1] * d2[0]:
                pts.append(run[i])
        pts.append(run[-1])
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pt(a[1], a[2])); t.SetEnd(pt(b[1], b[2]))
            t.SetWidth(pcbnew.FromMM(tw)); t.SetLayer(layer); t.SetNet(ni)
            board.Add(t); added.append(t)
    return added
