"""Render the assembled board (STEP exported by kicad-cli) to PNG images.

STEP -> OpenCASCADE (XCAF, keeps KiCad's per-part colours) -> triangle meshes grouped by
colour -> PyVista/VTK off-screen rendering. Run under xvfb-run.
Usage: python render3d.py board.step outdir
"""
from __future__ import annotations
import os
import sys
from collections import defaultdict

import numpy as np
import pyvista as pv
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
from OCP.TDF import TDF_Label
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFDoc import XCAFDoc_ColorTool, XCAFDoc_DocumentTool, XCAFDoc_ColorSurf, XCAFDoc_ColorGen


def load(path):
    doc = TDocStd_Document(TCollection_ExtendedString("zb1"))
    r = STEPCAFControl_Reader()
    r.SetColorMode(True)
    r.SetNameMode(True)
    assert r.ReadFile(path) == 1, "STEP read failed"
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    groups = defaultdict(lambda: ([], []))   # rgb -> (points list, faces list)

    def color_of_label(lab):
        c = Quantity_Color()
        for t in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen):
            try:
                if XCAFDoc_ColorTool.GetColor_s(lab, t, c):
                    return (round(c.Red(), 3), round(c.Green(), 3), round(c.Blue(), 3))
            except TypeError:
                return None
        return None

    def color_of_shape(sh):
        c = Quantity_Color()
        for t in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen):
            if ct.GetColor(sh, t, c):
                return (round(c.Red(), 3), round(c.Green(), 3), round(c.Blue(), 3))
        return None

    def mesh_shape(shape, loc, default):
        BRepMesh_IncrementalMesh(shape, 0.03, False, 0.35, True)
        exp = TopExp_Explorer(shape, TopAbs_FACE)
        trsf = loc.Transformation()
        while exp.More():
            face = TopoDS.Face(exp.Current())
            col = color_of_shape(face) or default or (0.6, 0.6, 0.6)
            fl = TopLoc_Location()
            tri = BRep_Tool.Triangulation_s(face, fl)
            if tri is not None:
                ft = fl.Transformation()
                pts, faces = groups[col]
                base = sum(len(p) for p in pts)
                arr = np.empty((tri.NbNodes(), 3))
                for i in range(1, tri.NbNodes() + 1):
                    pnt = tri.Node(i).Transformed(ft).Transformed(trsf)
                    arr[i - 1] = (pnt.X(), pnt.Y(), pnt.Z())
                pts.append(arr)
                rev = face.Orientation() == TopAbs_REVERSED
                fs = np.empty((tri.NbTriangles(), 4), dtype=np.int64)
                for i in range(1, tri.NbTriangles() + 1):
                    a, b, c = tri.Triangle(i).Get()
                    if rev:
                        b, c = c, b
                    fs[i - 1] = (3, base + a - 1, base + b - 1, base + c - 1)
                faces.append(fs)
            exp.Next()

    def walk(lab, loc, inherited):
        col = color_of_label(lab) or inherited
        if st.IsAssembly_s(lab):
            comps = TDF_LabelSequence()
            st.GetComponents_s(lab, comps)
            for i in range(1, comps.Length() + 1):
                walk(comps.Value(i), loc, col)
        elif st.IsReference_s(lab):
            ref = TDF_Label()
            st.GetReferredShape_s(lab, ref)
            cloc = loc.Multiplied(st.GetLocation_s(lab))
            walk(ref, cloc, color_of_label(lab) or col)
        else:
            shape = st.GetShape_s(lab)
            mesh_shape(shape, loc, col)

    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    for i in range(1, roots.Length() + 1):
        walk(roots.Value(i), TopLoc_Location(), None)

    meshes = []
    for col, (pts, faces) in groups.items():
        if not pts:
            continue
        m = pv.PolyData(np.vstack(pts), np.vstack(faces).ravel())
        meshes.append((col, m))
    return meshes


def board_bounds(meshes):
    """Bounds of the bare board: the colour group spanning z 0..~1.6 with the largest xy extent."""
    best = None
    for col, m in meshes:
        b = m.bounds
        if abs(b[4]) < 0.05 and 1.4 < b[5] < 1.8:
            area = (b[1] - b[0]) * (b[3] - b[2])
            if best is None or area > best[0]:
                best = (area, b)
    return best[1] if best else None


TEXTURES = {}


def render(meshes, out, view, size=(2400, 1350)):
    pl = pv.Plotter(off_screen=True, window_size=size)
    pl.set_background("#0d1117", top="#2b3240")
    for col, m in meshes:
        pl.add_mesh(m, color=col, smooth_shading=False, specular=0.35, specular_power=20, ambient=0.18,
                    diffuse=0.85)
    bb = board_bounds(meshes)
    if bb is not None and TEXTURES:
        cx, cy = (bb[0] + bb[1]) / 2, (bb[2] + bb[3]) / 2
        for side, z in (("top", bb[5] + 0.012), ("bottom", bb[4] - 0.012)):
            if side not in TEXTURES:
                continue
            plane = pv.Plane(center=(cx, cy, z), direction=(0, 0, 1), i_size=bb[1] - bb[0],
                             j_size=bb[3] - bb[2], i_resolution=1, j_resolution=1)
            plane.texture_map_to_plane(inplace=True)
            pl.add_mesh(plane, texture=TEXTURES[side], ambient=0.25, diffuse=0.8, specular=0.25)
    pl.enable_anti_aliasing("ssaa")
    pl.add_light(pv.Light(position=(60, -80, 120), light_type="scene light", intensity=0.5))
    allp = np.vstack([m.points for _, m in meshes])
    c = (allp.min(0) + allp.max(0)) / 2
    d = 75
    cams = {
        "iso_top": [(c[0] - 0.55 * d, c[1] - 0.95 * d, c[2] + 0.85 * d), c, (0, 0, 1)],
        "iso_bottom": [(c[0] + 0.55 * d, c[1] - 0.95 * d, c[2] - 0.85 * d), c, (0, 0, -1)],
        "top": [(c[0], c[1], c[2] + 1.6 * d), c, (0, 1, 0)],
        "bottom": [(c[0], c[1], c[2] - 1.6 * d), c, (0, 1, 0)],
        "usb_end": [(c[0] - 1.1 * d, c[1] - 0.45 * d, c[2] + 0.35 * d), c, (0, 0, 1)],
    }
    pl.camera_position = cams[view]
    if view in ("top", "bottom"):
        pl.enable_parallel_projection()
        pl.camera.parallel_scale = 15.5
    else:
        pl.camera.zoom(1.25 if view != "usb_end" else 1.6)
    pl.screenshot(out)
    pl.close()


if __name__ == "__main__":
    step, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    if len(sys.argv) > 4:
        from PIL import Image
        for side, path in (("top", sys.argv[3]), ("bottom", sys.argv[4])):
            TEXTURES[side] = pv.Texture(np.asarray(Image.open(path).convert("RGBA")).copy())
    meshes = load(step)
    print(f"{len(meshes)} colour groups, {sum(m.n_cells for _, m in meshes)} triangles")
    for v in ("iso_top", "iso_bottom", "top", "bottom", "usb_end"):
        render(meshes, os.path.join(outdir, f"zb1_3d_{v}.png"), v)
        print("rendered", v)
