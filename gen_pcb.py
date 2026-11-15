# 作成日: 2026-11-15
# 目的: design.py の定義から KiCad 基板 (kicad/nfc_reader.kicad_pcb) を生成する（外形・部品配置・ネット・設計ルール）
#
# 使い方（KiCad付属のPythonで実行する）:
#   & "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" gen_pcb.py
# 注意: 既存の .kicad_pcb は上書きされる（配線済みなら --keep-tracks で配線を引き継ぐ）

import json
import os
import sys
import uuid

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from design import PARTS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
KICAD_DIR = os.path.dirname(os.path.dirname(sys.executable))
FP_DIR = os.path.join(KICAD_DIR, "share", "kicad", "footprints")
OUT = os.path.join(HERE, "kicad", "nfc_reader.kicad_pcb")
NS_SCH = uuid.UUID("6b1f2c1e-0000-4000-8000-000000000001")   # gen_sch.py と同じ名前空間

OX, OY = 100.0, 100.0          # 基板左上の座標 [mm]
BW, BH = 100.0, 60.0           # 基板サイズ [mm]

# 部品配置: ref -> (x, y, 回転[度])  ※基板左上からの相対座標 [mm]
PLACE = {
    # --- NFCコイル（右側）。端子は (50.8, 47.7) と (55.6, 47.7) に来る ---
    "AE1": (73.0, 28.0, 0),
    # --- ESP32（左上、アンテナを上端へ） ---
    "U2": (15.5, 18.4, 0),
    # ESP32 周辺の受動部品（ESP32の下に一列）
    "C3": (9.0, 28.5, 90), "C4": (11.3, 28.5, 90), "R3": (13.6, 28.5, 90), "C5": (15.9, 28.5, 90),
    "R4": (18.2, 28.5, 90), "R5": (20.5, 28.5, 90), "R6": (22.8, 28.5, 90), "R7": (25.1, 28.5, 90),
    "R8": (27.4, 28.5, 90), "R11": (29.7, 28.5, 90),
    # --- UI（ブザー・LED） ---
    "BZ1": (38.0, 7.0, 0),
    "Q1": (35.0, 15.0, 0), "R10": (38.0, 15.0, 90), "D2": (41.5, 15.0, 90),
    "D1": (35.0, 19.5, 0), "R9": (38.5, 19.5, 0),
    # --- PN532（中央）。180度回転でTXピンが右、I2Cピンが左を向く ---
    "U1": (36.0, 32.0, 180),
    "Y1": (37.0, 25.5, 0), "C14": (33.6, 25.5, 90), "C15": (40.4, 25.5, 90),
    # 電源デカップリング（PN532の下）
    "C6": (31.0, 38.5, 90), "C7": (33.0, 38.5, 90), "C8": (35.0, 38.5, 90), "C9": (37.0, 38.5, 90),
    "C10": (39.0, 38.5, 90), "C11": (41.0, 38.5, 90), "C12": (43.0, 38.5, 90), "C13": (45.0, 38.5, 90),
    # RX経路（PN532の右上）
    "R12": (42.5, 29.5, 90), "C16": (42.5, 33.0, 90), "R13": (44.6, 29.5, 90), "C17": (44.6, 33.0, 90),
    # --- アンテナ整合（下端の帯。上段=TX1、下段=TX2） ---
    "L1": (34.0, 50.5, 0), "C21": (37.0, 48.6, 90), "C23": (40.0, 50.5, 0), "C25": (40.0, 48.6, 0),
    "C27": (43.0, 48.6, 90), "C29": (44.8, 48.6, 90), "R21": (47.6, 50.5, 0),
    "L2": (34.0, 56.0, 0), "C22": (37.0, 57.9, 90), "C24": (40.0, 56.0, 0), "C26": (40.0, 57.9, 0),
    "C28": (43.0, 57.9, 90), "C30": (44.8, 57.9, 90), "R22": (47.6, 56.0, 0),
    # --- USB・電源（左下） ---
    "J1": (4.0, 44.0, 270),
    "R1": (10.5, 40.5, 90), "R2": (10.5, 47.5, 90),
    "U4": (14.5, 44.0, 0), "U3": (21.0, 44.0, 0),
    "C1": (14.5, 49.0, 0), "C2": (21.0, 49.0, 0),
    "SW1": (16.0, 56.5, 0), "SW2": (26.0, 56.5, 0),
    # --- 取付穴 ---
    "H1": (3.5, 30.5, 0), "H2": (96.5, 3.5, 0), "H3": (96.5, 56.5, 0), "H4": (3.5, 56.5, 0),
}


# "ライブラリ:名前" のフットプリントを読み込む
def load_fp(fpid):
    lib, name = fpid.split(":")
    path = os.path.join(HERE, "kicad", lib + ".pretty") if lib == "nfc_reader" else os.path.join(FP_DIR, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError(f"フットプリントが見つからない: {fpid}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


# mm を内部単位の座標に変換する
def pt(x, y):
    return pcbnew.VECTOR2I_MM(OX + x, OY + y)


# 基板外形（Edge.Cuts）を描く
def add_outline(board):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_RECT)
    s.SetStart(pt(0, 0))
    s.SetEnd(pt(BW, BH))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(pcbnew.FromMM(0.1))
    board.Add(s)


# ネットクラス定義: (名前, 線幅, クリアランス, 対象ネットのパターン)
NETCLASSES = [
    ("Power", 0.25, 0.15, ["/GND", "/+3V3", "/VBUS", "/PN_DVDD"]),   # PN532(0.5mmピッチ)に入れる太さ。USB-Cのパッド間隔に合わせて0.15
    ("RF", 0.25, 0.15, ["/TX?", "/TXF?", "/ANTM?", "/ANT?"]),
]


# 設計ルールとネットクラスをプロジェクトファイル(.kicad_pro)に書く（DRCはこちらを読む）
def write_project_rules():
    pro = os.path.join(HERE, "kicad", "nfc_reader.kicad_pro")
    d = json.load(open(pro, encoding="utf8")) if os.path.exists(pro) else {"meta": {"filename": "nfc_reader.kicad_pro", "version": 3}}
    rules = d.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
    rules.update({
        "min_clearance": 0.15, "min_track_width": 0.15, "min_copper_edge_clearance": 0.3,
        "min_through_hole_diameter": 0.2,   # ESP32フットプリントの放熱ビアが0.2mm（TODO: Fusionで可否確認）
        "min_hole_clearance": 0.15,         # USB4105フットプリントの穴-銅が0.19mm
        "min_hole_to_hole": 0.25, "min_via_diameter": 0.6, "min_via_annular_width": 0.13,
        "min_silk_clearance": 0.0, "min_text_height": 0.8, "min_text_thickness": 0.08,
        "min_resolved_spokes": 1,           # 小さいGNDパッドはベタへのつなぎ1本でも可
    })
    base = {"bus_width": 12, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
            "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "pcb_color": "rgba(0, 0, 0, 0.000)",
            "schematic_color": "rgba(0, 0, 0, 0.000)", "tuning_profile": "", "via_diameter": 0.6, "via_drill": 0.3,
            "wire_width": 6}
    classes = [dict(base, name="Default", clearance=0.2, track_width=0.25, priority=2147483647)]
    patterns = []
    for i, (name, w, c, pats) in enumerate(NETCLASSES):
        classes.append(dict(base, name=name, clearance=c, track_width=w, priority=i))
        patterns += [{"netclass": name, "pattern": pt_} for pt_ in pats]
    ns = d.setdefault("net_settings", {})
    ns["classes"] = classes
    ns["netclass_patterns"] = patterns
    ns.setdefault("meta", {"version": 4})
    with open(pro, "w", encoding="utf8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


# 基板側の設計ルール（板厚など）を設定する
def set_rules(board):
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(pcbnew.FromMM(1.6))


# 手配線（固定）: 自動配線がPN532の0.5mmピッチから引き出せなかったTX2を先に引く
#   座標は基板左上からの相対 [mm]。(層, 始点, 終点) の線分と、ビア位置のリスト
PREROUTES = {
    "TX2": {
        "tracks": [("F", (38.94, 31.75), (39.95, 31.75)),      # U1 6番ピン → 右へ
                   ("B", (39.95, 31.75), (39.95, 46.0)),       # 裏面を下へ
                   ("B", (39.95, 46.0), (33.0, 52.95)),        # 斜めに L2 の上へ
                   ("F", (33.0, 52.95), (32.94, 56.0))],       # 表面で L2 の1番パッドへ
        "vias": [(39.95, 31.75), (33.0, 52.95)],
    },
}


# PREROUTES を固定配線として基板に追加する
def add_preroutes(board):
    for net, d in PREROUTES.items():
        ni = board.FindNet("/" + net)
        for layer, a, b in d["tracks"]:
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pt(*a))
            t.SetEnd(pt(*b))
            t.SetLayer(pcbnew.F_Cu if layer == "F" else pcbnew.B_Cu)
            t.SetWidth(pcbnew.FromMM(0.25))
            t.SetNet(ni)
            t.SetLocked(True)
            board.Add(t)
        for x, y in d["vias"]:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pt(x, y))
            v.SetWidth(pcbnew.FromMM(0.6))
            v.SetDrill(pcbnew.FromMM(0.3))
            v.SetNet(ni)
            v.SetLocked(True)
            board.Add(v)


# コイル内側端(パッド2)から外側端子(パッド2)へ、裏面(B.Cu)に固定配線を引く
def add_coil_bridge(board):
    fp = board.FindFootprintByReference("AE1")
    p2 = [p for p in fp.Pads() if p.GetNumber() == "2"]
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(p2[0].GetPosition())
    t.SetEnd(p2[1].GetPosition())
    t.SetLayer(pcbnew.B_Cu)
    t.SetWidth(pcbnew.FromMM(0.6))
    t.SetNet(p2[0].GetNet())
    t.SetLocked(True)
    board.Add(t)


# 基板を組み立てて保存する
def main():
    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(2)
    add_outline(board)
    set_rules(board)

    nets = {}
    for p in PARTS:
        for n in p.nets.values():
            if n not in nets:
                ni = pcbnew.NETINFO_ITEM(board, "/" + n)   # 回路図のローカルラベルと同じ名前
                board.Add(ni)
                nets[n] = ni

    missing = []
    for p in PARTS:
        if p.ref.startswith("#"):
            continue
        if p.ref not in PLACE:
            missing.append(p.ref)
            continue
        fp = load_fp(p.footprint)
        fp.SetReference(p.ref)
        fp.SetValue(p.value)
        fp.SetPath(pcbnew.KIID_PATH("/" + str(uuid.uuid5(NS_SCH, p.ref))))   # 回路図のシンボルと紐づける
        x, y, rot = PLACE[p.ref]
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        if p.dnp:
            fp.SetDNP(True)
            fp.SetExcludedFromBOM(True)
            fp.SetExcludedFromPosFiles(True)
        for pad in fp.Pads():
            n = p.nets.get(pad.GetNumber())
            if n:
                pad.SetNet(nets[n])
        board.Add(fp)
    if missing:
        raise SystemExit(f"配置が未定義の部品: {missing}")

    add_coil_bridge(board)
    add_preroutes(board)
    for pad in board.FindFootprintByReference("J1").Pads():
        if pad.GetNumber() == "SH":
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)   # シールドはGNDベタに全面接続
    board.BuildConnectivity()
    pcbnew.SaveBoard(OUT, board)
    write_project_rules()
    print(f"生成: {OUT}（部品 {len(board.GetFootprints())}、ネット {len(nets)}）")


if __name__ == "__main__":
    main()
