"""ZB-1 design database: the single source of truth for schematic, PCB and BOM.

Every part: reference, symbol (lib:name), footprint (lib:name), value, MPN, populate flag,
schematic block, and a pin-number -> net map. Pins not listed are no-connect.
Net names are the ones used in ../README.md and ../pinmap.csv.
"""

R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
LED0603 = "LED_SMD:LED_0603_1608Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT23_5 = "Package_TO_SOT_SMD:SOT-23-5"
SOT23_6 = "Package_TO_SOT_SMD:SOT-23-6"
TP = "TestPoint:TestPoint_Pad_D1.0mm"


def R(ref, val, a, b, block, mpn="", fp=R0402, dnp=False):
    return dict(ref=ref, sym="Device:R", fp=fp, value=val, mpn=mpn or f"{val} 1% {fp.split('_')[-2] if '_' in fp else ''}",
                dnp=dnp, block=block, pins={"1": a, "2": b})


def C(ref, val, a, b, block, fp=C0402, dnp=False, mpn=""):
    return dict(ref=ref, sym="Device:C", fp=fp, value=val, mpn=mpn or f"{val} X5R/X7R", dnp=dnp,
                block=block, pins={"1": a, "2": b})


PARTS = [
    # ------------------------------------------------------------------ USB-C + ESD
    dict(ref="J1", sym="Connector:USB_C_Receptacle_USB2.0_16P",
         fp="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", value="USB-C", mpn="HRO TYPE-C-31-M-12",
         block="usb", pins={"A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
                            "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND",
                            "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP",
                            "A7": "USB_DN", "B7": "USB_DN", "S1": "SHIELD"}),
    R("R1", "5.1k", "CC1", "GND", "usb"),
    R("R2", "5.1k", "CC2", "GND", "usb"),
    R("R22", "1M", "SHIELD", "GND", "usb"),
    C("C12", "4.7nF", "SHIELD", "GND", "usb"),
    dict(ref="U5", sym="Power_Protection:USBLC6-2SC6", fp=SOT23_6, value="USBLC6-2SC6",
         mpn="ST USBLC6-2SC6", block="usb",
         pins={"1": "USB_DN", "6": "USB_DN", "3": "USB_DP", "4": "USB_DP", "2": "GND", "5": "VBUS"}),

    # ------------------------------------------------------------------ charger + power path
    dict(ref="U2", sym="zb1:BQ21040", fp=SOT23_6, value="BQ21040DBVR", mpn="TI BQ21040DBVR",
         block="charger", pins={"1": "CHG_TS", "2": "VBAT", "3": "CHG_N", "4": "CHG_ISET",
                                "5": "GND", "6": "VBUS"}),
    R("R3", "1.07k", "CHG_ISET", "GND", "charger"),
    R("R4", "10k", "CHG_TS", "GND", "charger", mpn="10k 1% (or 10k NTC on the cell)"),
    C("C1", "10uF", "VBUS", "GND", "charger", fp=C0603),
    C("C2", "4.7uF", "VBAT", "GND", "charger", fp=C0603),
    dict(ref="LED2", sym="Device:LED", fp=LED0603, value="CHG orange", mpn="orange 0603 LED",
         block="charger", pins={"1": "CHG_N", "2": "CHG_LED_A"}),
    R("R21", "1k", "VBUS", "CHG_LED_A", "charger"),
    dict(ref="D1", sym="Device:D_Schottky", fp="Diode_SMD:D_SOD-123", value="B5819W",
         mpn="B5819W SOD-123", block="charger", pins={"1": "VSYS", "2": "VBUS"}),
    dict(ref="Q1", sym="Device:Q_PMOS_GSD", fp=SOT23, value="DMG3415U", mpn="Diodes DMG3415U-7",
         block="charger", pins={"1": "VBUS", "2": "VSYS", "3": "VBAT"}),
    R("R7", "100k", "VBUS", "GND", "charger"),
    C("C3", "22uF", "VSYS", "GND", "charger", fp=C0805),
    dict(ref="J3", sym="Connector_Generic:Conn_01x02",
         fp="Connector_JST:JST_PH_B2B-PH-SM4-TB_1x02-1MP_P2.00mm_Vertical", value="BATT JST-PH",
         mpn="JST B2B-PH-SM4-TB", block="charger", pins={"1": "BATN", "2": "VBAT"}),
    # optional cell protection (DNP by default; SJ2 bridges BATN to GND)
    dict(ref="U6", sym="zb1:DW01A", fp=SOT23_6, value="DW01A", mpn="Fortune DW01A", dnp=True,
         block="protect", pins={"1": "PROT_OD", "2": "PROT_CS", "3": "PROT_OC", "5": "PROT_VCC",
                                "6": "BATN"}),
    dict(ref="Q2", sym="zb1:FS8205A", fp="Package_SO:TSSOP-8_4.4x3mm_P0.65mm", value="FS8205A",
         mpn="Fortune FS8205A", dnp=True, block="protect",
         pins={"1": "PROT_D", "8": "PROT_D", "2": "BATN", "3": "BATN", "4": "PROT_OD",
               "5": "PROT_OC", "6": "GND", "7": "GND"}),
    R("R23", "100", "VBAT", "PROT_VCC", "protect", dnp=True),
    C("C13", "100nF", "PROT_VCC", "BATN", "protect", dnp=True),
    R("R24", "2k", "PROT_CS", "GND", "protect", dnp=True),
    dict(ref="SJ2", sym="Jumper:SolderJumper_2_Bridged",
         fp="Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm", value="PROT bypass",
         mpn="(PCB) cut if U6/Q2 fitted", block="protect", pins={"1": "BATN", "2": "GND"}),

    # ------------------------------------------------------------------ 3.3 V regulator + test hooks
    dict(ref="U3", sym="zb1:RT9080-33", fp=SOT23_5, value="RT9080-33GJ5", mpn="Richtek RT9080-33GJ5",
         block="ldo", pins={"1": "VSYS", "2": "GND", "3": "LDO_EN", "5": "3V3_LDO"}),
    R("R8", "1M", "VSYS", "LDO_EN", "ldo"),
    C("C4", "1uF", "VSYS", "GND", "ldo"),
    C("C5", "22uF", "3V3_LDO", "GND", "ldo", fp=C0805),
    dict(ref="SJ1", sym="Jumper:SolderJumper_2_Bridged",
         fp="Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm", value="I_MEAS",
         mpn="(PCB) cut to measure current", block="ldo", pins={"1": "3V3_LDO", "2": "3V3"}),
    dict(ref="TP1", sym="Connector:TestPoint", fp=TP, value="TP_EN", mpn="(PCB)", block="ldo",
         pins={"1": "LDO_EN"}),
    dict(ref="TP2", sym="Connector:TestPoint", fp=TP, value="VBAT", mpn="(PCB)", block="ldo",
         pins={"1": "VBAT"}),
    dict(ref="TP3", sym="Connector:TestPoint", fp=TP, value="VSYS", mpn="(PCB)", block="ldo",
         pins={"1": "VSYS"}),
    dict(ref="TP4", sym="Connector:TestPoint", fp=TP, value="3V3", mpn="(PCB)", block="ldo",
         pins={"1": "3V3"}),
    dict(ref="TP5", sym="Connector:TestPoint", fp=TP, value="GND", mpn="(PCB)", block="ldo",
         pins={"1": "GND"}),
    R("R5", "1M", "VBAT", "VBAT_SENSE", "ldo"),
    R("R6", "1M", "VBAT_SENSE", "GND", "ldo"),
    C("C14", "100nF", "VBAT_SENSE", "GND", "ldo"),

    # ------------------------------------------------------------------ module
    dict(ref="U1", sym="MCU_Espressif:ESP32-S3-MINI-1", fp="zb1:ESP32-S3-MINI-1",
         value="ESP32-S3-MINI-1-N8", mpn="Espressif ESP32-S3-MINI-1-N8", block="mcu",
         pins={**{str(n): "GND" for n in [1, 2, 42, 43] + list(range(46, 66))},
               "3": "3V3", "45": "CHIP_EN", "4": "BOOT", "5": "A4", "6": "VBAT_SENSE",
               "8": "A0", "9": "A1", "10": "A2", "11": "A3", "12": "SDA",
               "13": "SD_D2", "14": "SD_D3", "15": "SD_CMD", "16": "SD_CLK_MCU", "17": "SD_D0",
               "18": "SD_D1", "19": "XTAL32_P", "20": "XTAL32_N", "21": "D5", "22": "SCL",
               "23": "USB_DN", "24": "USB_DP", "25": "SD_PWR_EN", "26": "SD_DET", "27": "LED",
               "28": "D11", "29": "D12", "30": "MISO", "34": "D10", "35": "D6", "36": "D9",
               "37": "SCK", "38": "MOSI", "39": "TX", "40": "RX"}),
    C("C6", "10uF", "3V3", "GND", "mcu", fp=C0603),
    C("C7", "100nF", "3V3", "GND", "mcu"),
    R("R9", "10k", "3V3", "CHIP_EN", "mcu"),
    C("C15", "1uF", "CHIP_EN", "GND", "mcu"),
    R("R25", "10k", "3V3", "BOOT", "mcu"),
    dict(ref="SW1", sym="Switch:SW_Push", fp="Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2",
         value="RESET", mpn="C&K KMR221GLFS", block="mcu", pins={"1": "CHIP_EN", "2": "GND"}),
    dict(ref="SW2", sym="Switch:SW_Push", fp="Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2",
         value="BOOT", mpn="C&K KMR221GLFS", block="mcu", pins={"1": "BOOT", "2": "GND"}),
    dict(ref="Y1", sym="Device:Crystal", fp="Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm",
         value="32.768kHz 12.5pF", mpn="Epson FC-135 32.768kHz 12.5pF", block="mcu",
         pins={"1": "XTAL32_P", "2": "XTAL32_N"}),
    C("C8", "18pF", "XTAL32_P", "GND", "mcu", mpn="18pF C0G"),
    C("C9", "18pF", "XTAL32_N", "GND", "mcu", mpn="18pF C0G"),
    dict(ref="LED1", sym="Device:LED", fp=LED0603, value="USER red", mpn="red 0603 LED",
         block="mcu", pins={"1": "GND", "2": "LED_A"}),
    R("R20", "2.2k", "LED", "LED_A", "mcu"),

    # ------------------------------------------------------------------ microSD
    dict(ref="U4", sym="Power_Management:TPS22917DBV", fp=SOT23_6, value="TPS22917DBVR",
         mpn="TI TPS22917DBVR", block="sd",
         pins={"1": "3V3", "2": "GND", "3": "SD_PWR_EN", "5": "SD_VDD", "6": "SD_VDD"}),
    R("R17", "100k", "SD_PWR_EN", "GND", "sd"),
    C("C10", "1uF", "3V3", "GND", "sd"),
    C("C11", "10uF", "SD_VDD", "GND", "sd", fp=C0603),
    dict(ref="J2", sym="Connector:Micro_SD_Card_Det_Hirose_DM3AT",
         fp="Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5", value="microSD push-push",
         mpn="Hirose DM3AT-SF-PEJM5", block="sd",
         pins={"1": "SD_D2", "2": "SD_D3", "3": "SD_CMD", "4": "SD_VDD", "5": "SD_CLK", "6": "GND",
               "7": "SD_D0", "8": "SD_D1", "9": "GND", "10": "SD_DET", "11": "GND"}),
    R("R15", "33", "SD_CLK_MCU", "SD_CLK", "sd"),
    R("R10", "10k", "SD_VDD", "SD_CMD", "sd"),
    R("R11", "10k", "SD_VDD", "SD_D0", "sd"),
    R("R12", "10k", "SD_VDD", "SD_D1", "sd"),
    R("R13", "10k", "SD_VDD", "SD_D2", "sd"),
    R("R14", "10k", "SD_VDD", "SD_D3", "sd"),
    R("R16", "100k", "3V3", "SD_DET", "sd"),

    # ------------------------------------------------------------------ I2C, fuel gauge, headers
    R("R18", "4.7k", "3V3", "SDA", "io"),
    R("R19", "4.7k", "3V3", "SCL", "io"),
    dict(ref="J4", sym="Connector_Generic:Conn_01x04",
         fp="Connector_JST:JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical", value="STEMMA-QT",
         mpn="JST BM04B-SRSS-TB", block="io", pins={"1": "GND", "2": "3V3", "3": "SDA", "4": "SCL"}),
    dict(ref="U7", sym="zb1:MAX17048", fp="Package_DFN_QFN:TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm",
         value="MAX17048G+T10", mpn="Analog Devices MAX17048G+T10", dnp=True, block="io",
         pins={"1": "GND", "2": "VBAT", "3": "VBAT", "4": "GND", "6": "GND", "7": "SCL",
               "8": "SDA", "9": "GND"}),
    C("C16", "1uF", "VBAT", "GND", "io", dnp=True),
    dict(ref="J5", sym="Connector_Generic:Conn_01x16",
         fp="Connector_PinHeader_2.54mm:PinHeader_1x16_P2.54mm_Vertical", value="Feather 16",
         mpn="1x16 2.54mm header (ship loose)", block="io",
         pins={"1": "CHIP_EN", "2": "3V3", "4": "GND", "5": "A0", "6": "A1", "7": "A2", "8": "A3",
               "9": "A4", "11": "SCK", "12": "MOSI", "13": "MISO", "14": "RX", "15": "TX"}),
    dict(ref="J6", sym="Connector_Generic:Conn_01x12",
         fp="Connector_PinHeader_2.54mm:PinHeader_1x12_P2.54mm_Vertical", value="Feather 12",
         mpn="1x12 2.54mm header (ship loose)", block="io",
         pins={"1": "VBAT", "2": "LDO_EN", "3": "VBUS", "4": "LED", "5": "D12", "6": "D11",
               "7": "D10", "8": "D9", "9": "D6", "10": "D5", "11": "SCL", "12": "SDA"}),
]

# mechanical (PCB only, no schematic pins)
MECH = [
    dict(ref="H1", fp="MountingHole:MountingHole_2.2mm_M2", value="M2"),
    dict(ref="H2", fp="MountingHole:MountingHole_2.2mm_M2", value="M2"),
    dict(ref="H3", fp="MountingHole:MountingHole_2.2mm_M2", value="M2"),
    dict(ref="H4", fp="MountingHole:MountingHole_2.2mm_M2", value="M2"),
]

BLOCKS = {
    "usb": "USB-C input and ESD",
    "charger": "Li-ion charger and load-sharing power path",
    "protect": "Optional cell protection (DNP; SJ2 bypass fitted)",
    "ldo": "3.3 V regulator, battery sense, test hooks (E6/E7)",
    "mcu": "ESP32-S3-MINI-1-N8, reset/boot, 32 kHz crystal, LED",
    "sd": "microSD (4-bit SDMMC), power switch, pull-ups",
    "io": "I2C / STEMMA-QT, optional fuel gauge, Feather headers",
}

POWER_NETS = {"VBUS", "VSYS", "VBAT", "3V3", "3V3_LDO", "SD_VDD", "GND", "BATN"}


def nets():
    """net -> [(ref, pin)]"""
    out: dict[str, list] = {}
    for p in PARTS:
        for pin, n in p["pins"].items():
            out.setdefault(n, []).append((p["ref"], pin))
    return out


if __name__ == "__main__":
    ns = nets()
    for n in sorted(ns):
        flag = "  <-- single-pin net" if len(ns[n]) < 2 else ""
        print(f"{n:12s} {len(ns[n]):3d} {ns[n][:6]}{flag}")
    print(len(PARTS), "parts,", len(ns), "nets")
