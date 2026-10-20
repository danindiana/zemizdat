#!/usr/bin/env bash
# Rebuild the whole ZB-1 CAD package from scripts/zb1_design.py.
# Requires: KiCad 7 (kicad-cli + pcbnew python), kicad-symbols/footprints/packages3d,
# Java 17+, xvfb-run, rsvg-convert, python3 with shapely, pillow, numpy, cadquery-ocp, pyvista.
# FREEROUTING_JAR must point at a Freerouting 1.4.x jar (see README "Toolchain").
set -euo pipefail
cd "$(dirname "$0")"
export KIPRJMOD="$PWD"
export KICAD6_3DMODEL_DIR=/usr/share/kicad/3dmodels KICAD7_3DMODEL_DIR=/usr/share/kicad/3dmodels
export KICAD7_FOOTPRINT_DIR=/usr/share/kicad/footprints KICAD7_SYMBOL_DIR=/usr/share/kicad/symbols

python3 scripts/gen_libs.py          # project symbols, module footprint + STEP
python3 scripts/gen_models.py        # envelope 3D bodies for parts without library models
python3 scripts/gen_schematic.py     # zb1.kicad_sch from the design database
kicad-cli sch export netlist --format kicadxml -o build/net.xml zb1.kicad_sch
python3 scripts/verify_netlist.py build/net.xml
python3 scripts/gen_pcb.py           # outline, placement, keepouts  -> build/zb1_placed.kicad_pcb
# route.py: GND fan-out, maze pre-route of USB/crystal/VBUS hop, Freerouting -> build/zb1.ses
# finish.py: import, maze completion + rip-up, pours, silk, DRC -> zb1.kicad_pcb, reports/drc.rpt
python3 scripts/best_of.py           # runs route.py + finish.py for several pre-route sets, keeps the best
python3 scripts/export.py            # fab/, docs/, 3d/, images/
