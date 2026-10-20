"""Composite realistic top/bottom board-surface images (solder mask, copper, ENIG pads, silkscreen)
from per-layer black-and-white SVG plots made by kicad-cli. Used as textures by render3d.py and as
the 2D board previews.

Usage: python texture.py board.kicad_pcb outdir [px_per_mm]
Writes outdir/zb1_surface_top.png and zb1_surface_bottom.png (RGBA, transparent outside the board,
both in board coordinates as seen from the top, i.e. the bottom image is NOT mirrored).
"""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

MASK = (24, 88, 52)          # green solder mask over bare laminate
MASK_CU = (44, 128, 66)      # mask over copper
ENIG = (214, 178, 92)        # exposed copper, gold finish
SILK = (238, 238, 232)
HOLE = (20, 20, 22)


def plot(pcb, layers, out_png, px_per_mm, tmp):
    svg = os.path.join(tmp, "p.svg")
    subprocess.run(["kicad-cli", "pcb", "export", "svg", "--black-and-white", "--exclude-drawing-sheet",
                    "--page-size-mode", "2", "--layers", ",".join(["Edge.Cuts"] + layers), "-o", svg, pcb],
                   check=True, capture_output=True)
    subprocess.run(["rsvg-convert", "-b", "white", "-d", str(px_per_mm * 25.4), "-p", str(px_per_mm * 25.4),
                    "-o", out_png, svg], check=True)
    a = np.asarray(Image.open(out_png).convert("L")) < 128
    return a


def board_mask(edge):
    """Fill the closed outline drawn in `edge` to get the board area."""
    h, w = edge.shape
    img = Image.fromarray(np.where(edge, 0, 255).astype(np.uint8))
    from PIL import ImageDraw
    ImageDraw.floodfill(img, (0, 0), 128)
    ImageDraw.floodfill(img, (w - 1, h - 1), 128)
    arr = np.asarray(img)
    return arr != 128


def surface(pcb, side, px_per_mm, tmp):
    s = "F" if side == "top" else "B"
    edge = plot(pcb, [], os.path.join(tmp, "e.png"), px_per_mm, tmp)
    cu = plot(pcb, [f"{s}.Cu"], os.path.join(tmp, "c.png"), px_per_mm, tmp)
    mask_open = plot(pcb, [f"{s}.Mask"], os.path.join(tmp, "m.png"), px_per_mm, tmp)
    silk = plot(pcb, [f"{s}.SilkS"], os.path.join(tmp, "s.png"), px_per_mm, tmp)
    edge_d = np.asarray(Image.fromarray(edge.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
    cu &= ~edge_d; mask_open &= ~edge_d; silk &= ~edge_d
    area = board_mask(edge)
    img = np.zeros(edge.shape + (4,), dtype=np.uint8)
    img[..., :3] = MASK
    img[cu] = (*MASK_CU, 255)
    img[mask_open & cu, :3] = ENIG
    img[mask_open & ~cu, :3] = HOLE
    img[silk & ~mask_open, :3] = SILK
    img[..., 3] = np.where(area | edge, 255, 0)
    img[edge, :3] = (30, 60, 40)
    ys, xs = np.nonzero(edge)                       # crop exactly to the Edge.Cuts outline
    return Image.fromarray(img[ys.min():ys.max() + 1, xs.min():xs.max() + 1], "RGBA")


if __name__ == "__main__":
    pcb, outdir = sys.argv[1], sys.argv[2]
    ppm = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    os.makedirs(outdir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for side in ("top", "bottom"):
            im = surface(pcb, side, ppm, tmp)
            p = os.path.join(outdir, f"zb1_surface_{side}.png")
            im.save(p)
            print("wrote", p, im.size)
