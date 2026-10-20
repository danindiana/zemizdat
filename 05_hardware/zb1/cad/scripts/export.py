"""Stage 4: every deliverable from the finished KiCad project.

fab/      Gerbers + Excellon drill (zipped for upload), pick-and-place CSV, BOM CSV
docs/     schematic PDF, assembly drawings (top/bottom), drill map
3d/       zb1.step (whole assembly, for enclosure CAD)
images/   schematic PNG, per-layer plots, realistic board-surface images, 3D renders
reports/  netlist check (schematic vs design database)
Run from anywhere: python export.py   (needs kicad-cli 7, rsvg-convert, xvfb-run, OCP, pyvista)
"""
from __future__ import annotations
import csv
import glob
import os
import shutil
import subprocess
import sys
import zipfile
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CAD = os.path.dirname(HERE)
from zb1_design import PARTS  # noqa: E402

PCB = os.path.join(CAD, "zb1.kicad_pcb")
SCH = os.path.join(CAD, "zb1.kicad_sch")
ENV = dict(os.environ, KIPRJMOD=CAD, KICAD6_3DMODEL_DIR="/usr/share/kicad/3dmodels",
           KICAD7_3DMODEL_DIR="/usr/share/kicad/3dmodels")


def run(*args, **kw):
    r = subprocess.run(list(args), capture_output=True, text=True, env=ENV, **kw)
    if r.returncode != 0:
        print("FAILED:", " ".join(args), "\n", r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit(1)
    return r.stdout


def d(*p):
    path = os.path.join(CAD, *p)
    os.makedirs(path, exist_ok=True)
    return path


def svg2png(svg, png, width=2400, bg="#0d1117"):
    subprocess.run(["rsvg-convert", "-b", bg, "-w", str(width), "-o", png, svg], check=True)


def main():
    fab, docs, td, img, rep = d("fab"), d("docs"), d("3d"), d("images"), d("reports")
    tmp = d("build", "export_tmp")

    # ---------------- schematic
    run("kicad-cli", "sch", "export", "pdf", "-o", os.path.join(docs, "zb1_schematic.pdf"), SCH)
    run("kicad-cli", "sch", "export", "svg", "-o", tmp, SCH)
    svg2png(os.path.join(tmp, "zb1.svg"), os.path.join(img, "zb1_schematic.png"), 4200, "white")
    run("kicad-cli", "sch", "export", "netlist", "--format", "kicadxml", "-o", os.path.join(tmp, "net.xml"), SCH)
    chk = subprocess.run([sys.executable, os.path.join(HERE, "verify_netlist.py"), os.path.join(tmp, "net.xml")],
                         capture_output=True, text=True)
    open(os.path.join(rep, "netlist_check.txt"), "w").write(chk.stdout)
    print(chk.stdout.strip().splitlines()[-1])

    # ---------------- fabrication
    gdir = os.path.join(fab, "gerbers")
    shutil.rmtree(gdir, ignore_errors=True)
    os.makedirs(gdir)
    layers = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    run("kicad-cli", "pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask", "-o", gdir + "/", PCB)
    run("kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
        "--generate-map", "--map-format", "pdf", "-u", "mm", "-o", gdir + "/", PCB)
    for m in glob.glob(os.path.join(gdir, "*-drl_map.pdf")):
        shutil.move(m, os.path.join(docs, os.path.basename(m)))
    zp = os.path.join(fab, "zb1_gerbers.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)
    run("kicad-cli", "pcb", "export", "pos", "--side", "both", "--format", "csv", "--units", "mm",
        "--exclude-fp-th", "--use-drill-file-origin", "-o", os.path.join(fab, "zb1_pos.csv"), PCB)

    # BOM grouped by value + footprint + MPN, DNP listed separately
    groups = OrderedDict()
    for p in PARTS:
        key = (p["value"], p["fp"].split(":")[1], p["mpn"], bool(p.get("dnp")))
        groups.setdefault(key, []).append(p["ref"])
    with open(os.path.join(fab, "zb1_bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Qty", "References", "Value", "Footprint", "MPN / description", "Populate"])
        for (val, fp, mpn, dnp), refs in sorted(groups.items(), key=lambda kv: (kv[0][3], kv[1][0][0], kv[1][0])):
            w.writerow([len(refs), " ".join(refs), val, fp, mpn, "DNP" if dnp else "yes"])

    # ---------------- assembly drawings
    run("kicad-cli", "pcb", "export", "pdf", "--layers", "F.Fab,F.SilkS,Edge.Cuts", "--ibt",
        "-o", os.path.join(docs, "zb1_assembly_top.pdf"), PCB)
    run("kicad-cli", "pcb", "export", "pdf", "--layers", "B.Fab,B.SilkS,Edge.Cuts", "--ibt", "--mirror",
        "-o", os.path.join(docs, "zb1_assembly_bottom.pdf"), PCB)

    # ---------------- layer plots
    for layer in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
        svg = os.path.join(tmp, f"{layer}.svg")
        run("kicad-cli", "pcb", "export", "svg", "--exclude-drawing-sheet", "--page-size-mode", "2",
            "--layers", f"Edge.Cuts,{layer}", "-o", svg, PCB)
        svg2png(svg, os.path.join(img, f"zb1_layer_{layer.replace('.', '_')}.png"), 2400)

    # ---------------- realistic surfaces + 3D
    run(sys.executable, os.path.join(HERE, "texture.py"), PCB, img, "40")
    step = os.path.join(td, "zb1.step")
    out = run("kicad-cli", "pcb", "export", "step", "--subst-models", "--force", "-o", step, PCB)
    missing = [l for l in out.splitlines() if "Could not add 3D model" in l]
    open(os.path.join(rep, "step_export.txt"), "w").write(
        "3D models missing from the STEP: " + (", ".join(missing) if missing else "none") + "\n")
    print("STEP:", os.path.getsize(step) // 1024, "KiB; missing models:", len(missing))
    run("xvfb-run", "-a", sys.executable, os.path.join(HERE, "render3d.py"), step, img,
        os.path.join(img, "zb1_surface_top.png"), os.path.join(img, "zb1_surface_bottom.png"))
    print("exports done")


if __name__ == "__main__":
    main()
