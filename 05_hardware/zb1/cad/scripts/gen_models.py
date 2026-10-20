"""Simple dimensioned 3D bodies (STEP, coloured) for parts whose KiCad 7 library has no model.
Dimensions from the manufacturers' drawings, centred on each footprint's fab outline.
They are envelope models for collision checks and renders, not detailed mechanical models."""
import os
import sys

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorSurf

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "3dmodels")


def write(name, boxes):
    """boxes: [((x0,y0,z0),(x1,y1,z1),(r,g,b))] in footprint mm (KiCad 3D: +y is up the page)."""
    doc = TDocStd_Document(TCollection_ExtendedString("m"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    for (a, b, rgb) in boxes:
        sh = BRepPrimAPI_MakeBox(gp_Pnt(*a), gp_Pnt(*b)).Shape()
        lab = st.AddShape(sh, False)
        ct.SetColor(lab, Quantity_Color(*rgb, Quantity_TOC_RGB), XCAFDoc_ColorSurf)
    w = STEPCAFControl_Writer()
    w.SetColorMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    w.Write(os.path.join(OUT, name))
    print("wrote", name)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    silver, black, cream, tin = (0.78, 0.79, 0.8), (0.08, 0.08, 0.09), (0.93, 0.9, 0.8), (0.85, 0.85, 0.82)
    # C&K KMR2: 4.2 x 2.8 x 1.9 mm, metal cover, dark actuator. Fab outline y -1.4..1.4 (KiCad 3D y = -fab y)
    write("SW_KMR2_envelope.step", [((-2.1, -1.4, 0), (2.1, 1.4, 1.6), silver),
                                    ((-0.9, -0.6, 1.6), (0.9, 0.6, 1.9), black)])
    # JST B2B-PH-SM4-TB vertical: housing 7.95 x 5.0 x 6.0 mm; fab y -4.25..0.75 -> 3D y -0.75..4.25
    write("JST_PH_B2B-PH-SM4-TB_envelope.step", [((-3.975, -0.75, 0), (3.975, 4.25, 6.0), cream),
                                                 ((-3.0, 0.2, 6.0), (3.0, 3.3, 6.05), (0.55, 0.52, 0.45))])
    # 32.768 kHz crystal, 3.2 x 1.5 x 0.9 mm metal lid on ceramic base
    write("Crystal_3215_envelope.step", [((-1.6, -0.75, 0), (1.6, 0.75, 0.3), (0.85, 0.82, 0.7)),
                                         ((-1.5, -0.7, 0.3), (1.5, 0.7, 0.9), silver)])
    # USB-C receptacle (HRO TYPE-C-31-M-12): 8.94 x 7.35 x 3.16 mm shell, mouth toward fab +y (3D -y)
    write("USB_C_HRO_TYPE-C-31-M-12_envelope.step",
          [((-4.47, -3.7, 0.0), (4.47, 3.7, 3.16), silver),
           ((-3.9, -3.75, 0.45), (3.9, -3.0, 2.71), black),
           ((-2.9, -3.76, 1.25), (2.9, -2.4, 1.9), (0.25, 0.25, 0.27))])
    # Hirose DM3AT push-push microSD: body 13.95 x 16.0 x 1.98 mm, slot toward fab +y (3D -y)
    write("microSD_DM3AT_envelope.step",
          [((-6.975, -8.125, 0.0), (6.975, 7.875, 1.98), silver),
           ((-5.9, -8.2, 0.55), (5.1, -6.5, 1.45), black)])
    # JST BM04B-SRSS-TB (STEMMA-QT/Qwiic, vertical): 6.1 x 3.0 x 4.25 mm, cream housing
    write("JST_SH_BM04B-SRSS-TB_envelope.step",
          [((-3.05, -1.05, 0.0), (3.05, 1.95, 4.25), cream),
           ((-2.4, -0.6, 4.25), (2.4, 1.5, 4.3), (0.55, 0.52, 0.45))])
