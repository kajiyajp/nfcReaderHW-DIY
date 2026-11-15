# 作成日: 2026-11-15
# 目的: NFCリーダー基板の部品と接続（ネット）の唯一の定義。回路図・基板生成スクリプトはここを読む

from dataclasses import dataclass, field


@dataclass
class Part:
    ref: str
    lib: str              # "ライブラリ:シンボル名"
    value: str
    footprint: str
    nets: dict            # ピン番号 -> ネット名（書かないピンは未接続扱い）
    mpn: str = ""
    dnp: bool = False     # True = 未実装（予備パッド）
    group: str = ""       # 回路図の配置グループ
    note: str = ""


R0402 = "Resistor_SMD:R_0402_1005Metric"
R0603 = "Resistor_SMD:R_0603_1608Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
ANT_FP = "nfc_reader:NFC_Coil_45x35_4T"   # 自作フットプリント（gen_coil.py で生成）

PARTS = []


# 部品を追加するヘルパー
def add(*a, **k):
    PARTS.append(Part(*a, **k))


# 2端子部品（R/C/L）を追加するヘルパー
def two(ref, kind, value, fp, n1, n2, group, mpn="", dnp=False, note=""):
    add(ref, f"Device:{kind}", value, fp, {"1": n1, "2": n2}, mpn=mpn, dnp=dnp, group=group, note=note)


# ===== USB / 電源 =====
add("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C",
    "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
    {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
     "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
     "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN"},
    mpn="USB4105-GF-A", group="power")
two("R1", "R", "5.1k", R0402, "CC1", "GND", "power")
two("R2", "R", "5.1k", R0402, "CC2", "GND", "power")
add("U4", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
    {"1": "USB_DP", "6": "USB_DP", "3": "USB_DN", "4": "USB_DN", "5": "VBUS", "2": "GND"},
    mpn="USBLC6-2SC6", group="power")
add("U3", "Regulator_Linear:AP2112K-3.3", "AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5",
    {"1": "VBUS", "3": "VBUS", "2": "GND", "5": "+3V3"}, mpn="AP2112K-3.3TRG1", group="power")
two("C1", "C", "10u", C0805, "VBUS", "GND", "power")
two("C2", "C", "10u", C0805, "+3V3", "GND", "power")
add("#FLG1", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "VBUS"}, group="power")
add("#FLG2", "power:PWR_FLAG", "PWR_FLAG", "", {"1": "GND"}, group="power")

# ===== ESP32-C3 =====
add("U2", "RF_Module:ESP32-C3-WROOM-02", "ESP32-C3-WROOM-02", "RF_Module:ESP32-C3-WROOM-02",
    {"1": "+3V3", "9": "GND", "19": "GND", "2": "EN",
     "3": "SDA", "4": "SCL", "5": "NFC_IRQ", "6": "NFC_RST",
     "7": "IO8", "8": "BOOT", "16": "IO2", "10": "LED_IO", "15": "BUZ_IO",
     "13": "USB_DN", "14": "USB_DP"},
    mpn="ESP32-C3-WROOM-02-N4", group="mcu")
two("C3", "C", "10u", C0805, "+3V3", "GND", "mcu")
two("C4", "C", "100n", C0402, "+3V3", "GND", "mcu")
two("R3", "R", "10k", R0402, "+3V3", "EN", "mcu")
two("C5", "C", "1u", C0402, "EN", "GND", "mcu")
add("SW1", "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_SPST_TL3342", {"1": "EN", "2": "GND"}, group="mcu")
two("R4", "R", "10k", R0402, "+3V3", "BOOT", "mcu")
add("SW2", "Switch:SW_Push", "BOOT", "Button_Switch_SMD:SW_SPST_TL3342", {"1": "BOOT", "2": "GND"}, group="mcu")
two("R5", "R", "10k", R0402, "+3V3", "IO8", "mcu", note="ストラップ: 起動時High")
two("R6", "R", "10k", R0402, "+3V3", "IO2", "mcu", note="ストラップ: 起動時High")
two("R7", "R", "4.7k", R0402, "+3V3", "SDA", "mcu")
two("R8", "R", "4.7k", R0402, "+3V3", "SCL", "mcu")

# ===== UI（LED・ブザー） =====
two("R9", "R", "330", R0402, "LED_IO", "LED_A", "ui")
add("D1", "Device:LED", "GREEN", "LED_SMD:LED_0603_1608Metric", {"2": "LED_A", "1": "GND"}, group="ui")
two("R10", "R", "1k", R0402, "BUZ_IO", "BUZ_B", "ui")
add("Q1", "Transistor_BJT:MMBT3904", "MMBT3904", "Package_TO_SOT_SMD:SOT-23",
    {"1": "BUZ_B", "2": "GND", "3": "BUZ_N"}, mpn="MMBT3904", group="ui")
add("BZ1", "Device:Buzzer", "CMT-8504", "Buzzer_Beeper:MagneticBuzzer_CUI_CMT-8504-100-SMT",
    {"1": "+3V3", "2": "BUZ_N"}, mpn="CMT-8504-100-SMT-TR", group="ui")
add("D2", "Device:D", "1N4148W", "Diode_SMD:D_SOD-123", {"1": "+3V3", "2": "BUZ_N"}, mpn="1N4148W", group="ui")

# ===== PN532 =====
add("U1", "RF_NFC:PN5321A3HN_C1xx", "PN532", "Package_DFN_QFN:HVQFN-40-1EP_6x6mm_P0.5mm_EP4.1x4.1mm",
    {"40": "+3V3", "23": "+3V3", "39": "PN_DVDD", "8": "PN_DVDD", "5": "PN_DVDD",
     "1": "GND", "3": "GND", "7": "GND", "11": "GND", "41": "GND",
     "16": "GND", "17": "PN_DVDD", "18": "GND", "36": "GND",          # I0=L, I1=H → I2C
     "27": "SCL", "28": "SDA", "25": "NFC_IRQ", "38": "NFC_RST",
     "14": "OSCIN", "15": "OSCOUT", "4": "TX1", "6": "TX2", "9": "VMID", "10": "RX"},
    mpn="PN5321A3HN/C106", group="nfc")
two("R11", "R", "10k", R0402, "+3V3", "NFC_RST", "nfc")
two("C6", "C", "4.7u", C0603, "+3V3", "GND", "nfc", note="VBAT")
two("C7", "C", "100n", C0402, "+3V3", "GND", "nfc", note="VBAT")
two("C8", "C", "100n", C0402, "+3V3", "GND", "nfc", note="PVDD")
two("C9", "C", "4.7u", C0603, "PN_DVDD", "GND", "nfc", note="DVDD")
two("C10", "C", "100n", C0402, "PN_DVDD", "GND", "nfc", note="DVDD")
two("C11", "C", "100n", C0402, "PN_DVDD", "GND", "nfc", note="AVDD")
two("C12", "C", "4.7u", C0603, "PN_DVDD", "GND", "nfc", note="TVDD")
two("C13", "C", "100n", C0402, "PN_DVDD", "GND", "nfc", note="TVDD")
add("Y1", "Device:Crystal_GND24", "27.12MHz", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
    {"1": "OSCIN", "3": "OSCOUT", "2": "GND", "4": "GND"}, group="nfc", note="CL=10pF")
two("C14", "C", "15p", C0402, "OSCIN", "GND", "nfc")
two("C15", "C", "15p", C0402, "OSCOUT", "GND", "nfc")
# RX経路（データシート Fig.51）
two("R12", "R", "2.7k", R0402, "TXF1", "RXC", "nfc")
two("C16", "C", "1n", C0402, "RXC", "RX", "nfc")
two("R13", "R", "1k", R0402, "RX", "VMID", "nfc")
two("C17", "C", "100n", C0402, "VMID", "GND", "nfc")

# ===== アンテナ整合（左右対称。*B は予備パッド=未実装） =====
for side, tx in (("1", "TX1"), ("2", "TX2")):
    s = int(side)
    two(f"L{s}", "L", "560n", "Inductor_SMD:L_0805_2012Metric", tx, f"TXF{side}", "rf", note="EMC L0")
    two(f"C{20+s}", "C", "220p", C0603, f"TXF{side}", "GND", "rf", note="EMC C0 (C0G)")
    two(f"C{22+s}", "C", "33p", C0603, f"TXF{side}", f"ANTM{side}", "rf", note="整合 直列C1 (C0G)")
    two(f"C{24+s}", "C", "DNP", C0603, f"TXF{side}", f"ANTM{side}", "rf", dnp=True, note="C1 調整用予備")
    two(f"C{26+s}", "C", "180p", C0603, f"ANTM{side}", "GND", "rf", note="整合 並列C2 (C0G)")
    two(f"C{28+s}", "C", "DNP", C0603, f"ANTM{side}", "GND", "rf", dnp=True, note="C2 調整用予備")
    two(f"R{20+s}", "R", "1.5", R0603, f"ANTM{side}", f"ANT{side}", "rf", note="ダンピング Rq")
add("AE1", "Device:L", "NFC_Coil", ANT_FP, {"1": "ANT1", "2": "ANT2"}, group="rf", note="基板パターン 約1.34uH")

# ===== 取付穴 =====
for i in range(1, 5):
    add(f"H{i}", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", {}, group="mech")
