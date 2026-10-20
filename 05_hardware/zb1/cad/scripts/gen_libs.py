"""Generate the project libraries: zb1.kicad_sym (parts missing from KiCad 7) and zb1.pretty
(ESP32-S3-MINI-1 footprint from espressif/kicad-libraries, CC-BY-SA 4.0 with the KiCad
design exception), plus the module STEP model under 3dmodels/."""
from __future__ import annotations
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAD = os.path.dirname(HERE)
ESP_LIB = os.environ.get("ESP_KICAD_LIB", "/home/claude/cadlibs/kicad-libraries")

# name -> (ref prefix, description, datasheet, footprint, left pins, right pins)
# pins: (number, name, electrical type)
CUSTOM = {
    "BQ21040": ("U", "1-cell Li-ion linear charger, 800 mA, TS input, SOT-23-6",
                "https://www.ti.com/lit/ds/symlink/bq21040.pdf", "Package_TO_SOT_SMD:SOT-23-6",
                [("6", "VIN", "power_in"), ("4", "ISET", "passive"), ("1", "TS", "input"), ("5", "VSS", "power_in")],
                [("2", "OUT", "power_out"), ("3", "~{CHG}", "open_collector")]),
    "RT9080-33": ("U", "600 mA 2 uA-Iq LDO, 3.3 V, SOT-23-5 (pinout: VIN GND EN NC VOUT)",
                  "https://www.richtek.com/assets/product_file/RT9080/DS9080-08.pdf", "Package_TO_SOT_SMD:SOT-23-5",
                  [("1", "VIN", "power_in"), ("3", "EN", "input"), ("2", "GND", "power_in")],
                  [("5", "VOUT", "power_out"), ("4", "NC", "no_connect")]),
    "DW01A": ("U", "1-cell Li-ion protection controller, SOT-23-6", "", "Package_TO_SOT_SMD:SOT-23-6",
              [("5", "VCC", "power_in"), ("2", "CS", "input"), ("4", "TD", "passive"), ("6", "GND", "power_in")],
              [("1", "OD", "output"), ("3", "OC", "output")]),
    "FS8205A": ("Q", "Dual N-MOSFET, common drain, 20 V, TSSOP-8", "", "Package_SO:TSSOP-8_4.4x3mm_P0.65mm",
                [("2", "S1", "passive"), ("3", "S1", "passive"), ("4", "G1", "input"), ("1", "D", "passive")],
                [("7", "S2", "passive"), ("6", "S2", "passive"), ("5", "G2", "input"), ("8", "D", "passive")]),
    "MAX17048": ("U", "1-cell ModelGauge fuel gauge, I2C, TDFN-8 2x2",
                 "https://www.analog.com/media/en/technical-documentation/data-sheets/MAX17048-MAX17049.pdf",
                 "Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm",
                 [("3", "VDD", "power_in"), ("2", "CELL", "input"), ("1", "CTG", "passive"), ("4", "GND", "power_in"),
                  ("9", "EP", "passive")],
                 [("8", "SDA", "bidirectional"), ("7", "SCL", "input"), ("5", "~{ALRT}", "open_collector"),
                  ("6", "QSTRT", "input")]),
}


def q(s):
    return '"' + s.replace('"', '\\"') + '"'


def symbol(name, prefix, desc, ds, fp, left, right):
    rows = max(len(left), len(right))
    h = rows * 2.54 + 2.54
    w = 12.7 if name != "MAX17048" else 15.24
    top = h / 2
    out = [f'  (symbol {q(name)} (in_bom yes) (on_board yes)',
           f'    (property "Reference" {q(prefix)} (at 0 {top + 2.54:.2f} 0) (effects (font (size 1.27 1.27))))',
           f'    (property "Value" {q(name)} (at 0 {-top - 2.54:.2f} 0) (effects (font (size 1.27 1.27))))',
           f'    (property "Footprint" {q(fp)} (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           f'    (property "Datasheet" {q(ds)} (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           f'    (property "ki_description" {q(desc)} (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           f'    (symbol {q(name + "_0_1")}',
           f'      (rectangle (start {-w/2:.2f} {top:.2f}) (end {w/2:.2f} {-top:.2f}) (stroke (width 0.254) (type default)) (fill (type background))))',
           f'    (symbol {q(name + "_1_1")}']
    for side, pins in (("L", left), ("R", right)):
        for i, (num, pname, et) in enumerate(pins):
            y = top - 2.54 * (i + 1)
            x = -w / 2 - 2.54 if side == "L" else w / 2 + 2.54
            ang = 0 if side == "L" else 180
            out.append(f'      (pin {et} line (at {x:.2f} {y:.2f} {ang}) (length 2.54) '
                       f'(name {q(pname)} (effects (font (size 1.27 1.27)))) (number {q(num)} (effects (font (size 1.27 1.27)))))')
    out.append("    ))")
    return "\n".join(out)


def main():
    body = "\n".join(symbol(n, *v) for n, v in CUSTOM.items())
    with open(os.path.join(CAD, "lib", "zb1.kicad_sym"), "w") as f:
        f.write(f'(kicad_symbol_lib (version 20220914) (generator zb1_gen_libs)\n{body}\n)\n')

    # footprint + 3D model
    src = os.path.join(ESP_LIB, "footprints", "Espressif.pretty", "ESP32-S3-MINI-1.kicad_mod")
    step = os.path.join(ESP_LIB, "3dmodels", "espressif.3dshapes", "ESP32-S3-MINI-1.STEP")
    os.makedirs(os.path.join(CAD, "lib", "zb1.pretty"), exist_ok=True)
    os.makedirs(os.path.join(CAD, "lib", "3dmodels"), exist_ok=True)
    txt = open(src).read()
    txt = re.sub(r'\(model "[^"]*"', '(model "${KIPRJMOD}/lib/3dmodels/ESP32-S3-MINI-1.STEP"', txt)
    open(os.path.join(CAD, "lib", "zb1.pretty", "ESP32-S3-MINI-1.kicad_mod"), "w").write(txt)
    shutil.copy(step, os.path.join(CAD, "lib", "3dmodels", "ESP32-S3-MINI-1.STEP"))
    print("libraries written")


if __name__ == "__main__":
    os.makedirs(os.path.join(CAD, "lib"), exist_ok=True)
    main()
