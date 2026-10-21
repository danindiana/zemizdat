# Licensing

ZEMIZDAT is open source. Copyright © 2026 Benjamin W. Denio.

Software, hardware designs and documentation need different licences, so the repository is
licensed in three parts. All three are permissive. You may use, modify and redistribute the work,
including in commercial or closed products, as long as you keep the copyright and licence
notices and credit the source.

| Part | Licence | SPDX | Covers |
|---|---|---|---|
| **Software** | [Apache License 2.0](LICENSES/Apache-2.0.txt) | `Apache-2.0` | All source code and scripts. That includes `03_protocol/reference_py/`, `03_protocol/reference_c/`, `04_mathematical_analysis/scripts/`, every `.py` file and `tests/` in `06_simulation/`, `05_hardware/zb1/firmware/`, `05_hardware/zb1/arduino/`, `05_hardware/zb1/cad/scripts/`, `05_hardware/zb1/cad/build.sh` and `.github/` |
| **Hardware design** | [CERN Open Hardware Licence v2 – Permissive](LICENSES/CERN-OHL-P-2.0.txt) | `CERN-OHL-P-2.0` | The ZB-1 board. That covers `05_hardware/zb1/cad/` (KiCad project, project libraries, Gerbers, drill, pick-and-place, BOM, STEP model and envelope 3D models) and `05_hardware/zb1/bom.csv` and `pinmap.csv`. Excluded: `cad/scripts/` (software) and the third-party files listed below |
| **Documentation** | [Creative Commons Attribution 4.0](LICENSES/CC-BY-4.0.txt) | `CC-BY-4.0` | Everything else: all Markdown documents (specifications, analyses, reviews, READMEs), `diagrams/`, rendered images, PDFs, and the result data under `04_mathematical_analysis/results/` and `06_simulation/results/` |

The top-level [`LICENSE`](LICENSE) file holds the Apache-2.0 text, so GitHub reports the code
licence. The table above is what applies.

## Third-party material

| Files | Owner | Licence |
|---|---|---|
| `05_hardware/zb1/cad/lib/zb1.pretty/ESP32-S3-MINI-1.kicad_mod`, `05_hardware/zb1/cad/lib/3dmodels/ESP32-S3-MINI-1.STEP` | Espressif Systems, [espressif/kicad-libraries](https://github.com/espressif/kicad-libraries) | CC-BY-SA 4.0 with the KiCad design exception. They stay under that licence. Boards designed with them are not "Adapted Material", so the ZB-1 design itself can be CERN-OHL-P |

KiCad's own symbol, footprint and 3D-model libraries are referenced, not copied
([licence](https://www.kicad.org/libraries/license/)).

## Notes for people building on this

* **Software:** keep [`NOTICE`](NOTICE) with redistributed copies, as Apache-2.0 §4(d) requires.
  Apache-2.0 also includes a patent licence from contributors.
* **Hardware:** CERN-OHL-P §3 asks you to keep the existing notices and to add a notice saying
  you modified the design, if you did. §4 asks that anyone receiving a board you make can see
  those notices, for example through a link in the documentation. Pointing back to
  <https://github.com/danindiana/zemizdat> is appreciated but not required.
* **Documentation:** attribute "ZEMIZDAT, © 2026 Benjamin W. Denio, CC BY 4.0", link the source,
  and indicate any changes you made.
* **Contributions** are accepted under the same licence as the part of the repository they
  change: inbound = outbound.

Nothing in these licences is a statement about the legality of the device or of any content
carried with it in a given jurisdiction. That remains the responsibility of whoever builds or uses it.
