# 作成日: 2026-11-15 ／ 更新: 2026-11-16（ESP32-S3-MINI-1 へ変更、92x52mm に縮小、整合部を手配線で左右対称に固定。
#   RF 測定用のはんだジャンパと測定端子を整合部に入れ、99x52mm に）
# 目的: design.py の定義から KiCad 基板 (kicad/nfc_reader.kicad_pcb) を生成する（外形・部品配置・ネット・設計ルール・RF固定配線）
#
# 使い方（KiCad付属のPythonで実行する）:
#   & "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" gen_pcb.py
# 注意: 既存の .kicad_pcb は上書きされる（配線は消える。route.py で引き直す）
#
# レイアウトの考え方（座標は基板左上からの相対 [mm]）:
#   - 右側に NFC コイル。端子はコイル左辺の中央に上下対称（y = CY ± 2.4）
#   - PN532 の TX ピン側（右辺）をコイルへ向け、整合部 L0→C0→C1(+予備)→C2(+予備)→Rq を
#     TX2 列（上）と TX1 列（下）の2列に、中心線 y=CY に対して鏡像に並べる。直列部品は列の上、並列部品は列の外側
#   - TVDD のデカップリング(C13)は2列の間、TVDD ピンの直近
#   - ESP32-S3-MINI-1 は左上。モジュールのアンテナを基板の上端に合わせる（アンテナ下とその左右は銅箔なし）

import json
import os
import sys
import uuid

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from design import PARTS  # noqa: E402
import gen_coil  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
KICAD_DIR = os.path.dirname(os.path.dirname(sys.executable))
FP_DIR = os.path.join(KICAD_DIR, "share", "kicad", "footprints")
OUT = os.path.join(HERE, "kicad", "nfc_reader.kicad_pcb")
NS_SCH = uuid.UUID("6b1f2c1e-0000-4000-8000-000000000001")   # gen_sch.py と同じ名前空間

OX, OY = 100.0, 100.0          # 基板左上の座標 [mm]
BW, BH = 99.0, 52.0            # 基板サイズ [mm]（rev 0.1 は 100x60mm。RF 測定用のジャンパと端子を入れるため 92 → 99mm）

# --- RF 部の基準寸法 ---
CX, CY = 74.5, 26.0                                # コイル中心
ROW2, ROW1 = CY - gen_coil.TERM_HALF, CY + gen_coil.TERM_HALF   # TX2 列（上）/ TX1 列（下）。コイル端子と同じ高さ
UX = 20.4                                          # PN532 の中心X
UY = ROW2 + 0.25                                   # 180度回転で TX2(6番) ピンが ROW2 の高さに来る
PX = UX + 2.94                                     # PN532 右辺パッドの中心X
# 整合部の部品中心X（PX からの距離）。コートヤードが重ならない最小間隔で詰めてある
#   L0 → 測定用はんだジャンパ JP → 測定端子 J3（TXF2/GND/TXF1 の縦3ピン）→ C0 → C1 → C2 → Rq
XL = PX + 5.5
XJP = XL + 1.79 + 1.695                            # L0 のコートヤード右端 + ジャンパのコートヤード半幅
XJ3 = XJP + 1.695 + 1.815                          # ジャンパ + ピンヘッダのコートヤード半幅
DX = 7.05                                          # ジャンパと端子を入れたぶん、C0 以降を右へずらす量
XC0, XC1, XC2, XC2B, XRQ = (PX + v + DX for v in (8.1, 10.4, 12.7, 14.3, 16.6))
SPARE_C1 = 1.5                                     # C1 予備パッドを列の外側へずらす量

# 部品配置: ref -> (x, y, 回転[度])  ※基板左上からの相対座標 [mm]
PLACE = {
    # --- NFCコイル（右側） ---
    "AE1": (CX, CY, 0),
    # --- ESP32-S3-MINI-1（左上。アンテナを上端へ） ---
    "U2": (8.5, 10.75, 0),
    "C3": (1.9, 23.8, 90), "C4": (3.9, 23.6, 90),
    # EN / BOOT / I2C プルアップ（モジュールの右上に一列）
    "R3": (18.0, 8.0, 90), "C5": (19.5, 8.0, 90), "R4": (21.0, 8.0, 90), "R7": (22.5, 8.0, 90), "R8": (24.0, 8.0, 90),
    # --- LED ---
    "R9": (24.0, 10.5, 0), "D1": (27.0, 10.5, 0),
    # --- PN532（中央左）。180度回転で TX ピンが右（コイル側）、I2C ピンが左（ESP32側）を向く ---
    "U1": (UX, UY, 180),
    "Y1": (20.5, 16.8, 0), "C14": (19.0, 13.6, 0), "C15": (22.0, 13.6, 0),
    "C8": (16.2, 28.6, 90),                                            # PVDD（左辺）
    "R11": (17.8, 29.6, 90), "C12": (19.5, 29.9, 90), "C9": (21.0, 29.9, 90), "C10": (22.5, 29.6, 90),
    "C7": (23.6, 29.6, 90), "C6": (25.2, 31.8, 0),                     # DVDD / VBAT（下辺）
    "C13": (PX + 3.0, ROW2 + 1.15, 270),                               # TVDD（2列の間）
    # RX 経路・AVDD（右上）とテストポイント
    "C11": (25.0, 19.6, 90), "R13": (26.5, 19.6, 90), "C17": (28.0, 19.6, 90),
    "C16": (26.5, 16.8, 90), "R12": (28.0, 16.8, 90),
    "TP1": (30.5, 15.0, 0), "TP2": (32.8, 15.0, 0), "TP3": (35.1, 15.0, 0),
    # --- USB・電源（左下） ---
    "J1": (4.0, 38.0, 270),
    "R1": (10.5, 34.5, 90), "R2": (10.5, 41.5, 90),
    "U4": (14.5, 38.0, 0), "U3": (21.0, 38.0, 0),
    "C1": (14.5, 43.0, 0), "C2": (21.0, 43.0, 0),
    "SW1": (11.35, 48.3, 0), "SW2": (20.0, 48.3, 0),
    # --- ブザー・デバッグヘッダ（下中央） ---
    "Q1": (27.5, 36.0, 0), "R10": (27.5, 39.5, 90), "D2": (27.5, 43.0, 90),
    "BZ1": (35.5, 39.5, 0),
    "J2": (26.2, 48.5, 90),
    # --- 取付穴 ---
    "H1": (3.5, 48.5, 0), "H2": (BW - 3.5, 3.5, 0), "H3": (BW - 3.5, 48.5, 0), "H4": (35.0, 3.5, 0),
    # --- RF 測定端子（1番=TXF2 が上の列、3番=TXF1 が下の列に重なる） ---
    "J3": (XJ3, CY - 2.54, 0),
}

# 整合部（2列の鏡像）。s = 外側の向き（TX2列=-1=上、TX1列=+1=下）
for side, row, s in (("1", ROW1, 1), ("2", ROW2, -1)):
    n = int(side)
    shunt_rot = 90 if s < 0 else 270      # 並列部品の1番パッド（信号側）を列の上に置く向き
    PLACE.update({
        f"L{n}": (XL, row, 0),
        f"JP{n}": (XJP, row, 0),                          # 測定用はんだジャンパ（1番=L0 側）
        f"C{20+n}": (XC0, row + s * 0.78, shunt_rot),     # EMC C0
        f"C{22+n}": (XC1, row, 0),                        # 整合 C1
        f"C{24+n}": (XC1, row + s * SPARE_C1, 0),         # C1 予備
        f"C{26+n}": (XC2, row + s * 0.78, shunt_rot),     # 整合 C2
        f"C{28+n}": (XC2B, row + s * 0.78, shunt_rot),    # C2 予備
        f"R{20+n}": (XRQ, row, 0),                        # ダンピング Rq
    })

# シルクの部品番号を F.Fab（組立図）へ移す小さな受動部品のライブラリ（シルクの重なりを避ける）
FAB_REF_LIBS = ("Resistor_SMD", "Capacitor_SMD", "Inductor_SMD", "TestPoint", "MountingHole", "Jumper")
FAB_REF_PARTS = ("U1", "U2", "Y1")   # IC はシルクの外形だけで分かるので、部品番号は組立図へ


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


# 内部単位の座標を基板相対の mm に戻す
def rel(v):
    return (v.x / 1e6 - OX, v.y / 1e6 - OY)


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
    ("RF", 0.25, 0.15, ["/TX?", "/TXL?", "/TXF?", "/ANTM?", "/ANT?"]),   # 整合部は gen_pcb.py が 0.4mm で固定配線する
]


# 設計ルールとネットクラスをプロジェクトファイル(.kicad_pro)に書く（DRCはこちらを読む）
def write_project_rules():
    pro = os.path.join(HERE, "kicad", "nfc_reader.kicad_pro")
    d = json.load(open(pro, encoding="utf8")) if os.path.exists(pro) else {"meta": {"filename": "nfc_reader.kicad_pro", "version": 3}}
    rules = d.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
    rules.update({
        "min_clearance": 0.15, "min_track_width": 0.15, "min_copper_edge_clearance": 0.3,
        "min_through_hole_diameter": 0.3,
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


# 固定配線を1本の折れ線として追加する（pts は基板相対 mm の点列）
def add_track(board, net, pts, width, layer=pcbnew.F_Cu):
    ni = board.FindNet("/" + net)
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pt(*a))
        t.SetEnd(pt(*b))
        t.SetLayer(layer)
        t.SetWidth(pcbnew.FromMM(width))
        t.SetNet(ni)
        t.SetLocked(True)
        board.Add(t)


# 固定ビアを追加する
def add_via(board, net, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(x, y))
    v.SetWidth(pcbnew.FromMM(0.6))
    v.SetDrill(pcbnew.FromMM(0.3))
    v.SetNet(board.FindNet("/" + net))
    v.SetLocked(True)
    board.Add(v)


# 部品のパッド中心（基板相対 mm）を返す
def pad(board, ref, num):
    fp = board.FindFootprintByReference(ref)
    return rel(next(p for p in fp.Pads() if p.GetNumber() == num).GetPosition())


# 整合部（TX → L0 → C1 → Rq → コイル端子）と GND ビアを、2列とも同じ形で固定配線する
def add_rf_routes(board):
    W_PIN, W_RF = 0.3, 0.4         # ピン直近（0.5mmピッチ）/ 列の上
    # TX2: 6番ピンから水平にそのまま列へ
    tx2 = pad(board, "U1", "6")
    add_track(board, "TX2", [tx2, (PX + 0.6, ROW2)], W_PIN)
    add_track(board, "TX2", [(PX + 0.6, ROW2), pad(board, "L2", "1")], W_RF)
    # TX1: 4番ピンから 0.8mm 右へ出て、45度で TX1 列へ下りる（斜めの終点は L1 の1番パッドの中）
    tx1 = pad(board, "U1", "4")
    knee = (PX + 0.8, tx1[1])
    add_track(board, "TX1", [tx1, knee], W_PIN)
    add_track(board, "TX1", [knee, (knee[0] + (ROW1 - knee[1]), ROW1)], W_RF)
    # TVDD(5番) → C13 → GND ビア（2列の間）
    tvdd = pad(board, "U1", "5")
    c13a, c13b = pad(board, "C13", "1"), pad(board, "C13", "2")
    add_track(board, "PN_DVDD", [tvdd, (c13a[0], tvdd[1]), c13a], 0.25)
    # TVDD を裏面経由で DVDD 側へつなぐビア（2列の間からは表面で抜けられない。Freerouting 任せだと引き残すことがある）
    vd = (c13a[0] - 1.132, c13a[1] + 0.261)
    add_track(board, "PN_DVDD", [c13a, (c13a[0] - 0.261, vd[1]), vd], 0.25)
    add_via(board, "PN_DVDD", *vd)
    add_track(board, "GND", [c13b, (PX + 3.9, c13b[1])], 0.3)
    add_via(board, "GND", PX + 3.9, c13b[1])
    # TVSS(3,7番) は内側の放熱パッド(GND)へ短く引く
    for num in ("3", "7"):
        q = pad(board, "U1", num)
        add_track(board, "GND", [q, (UX + 1.6, q[1])], 0.25)
    # PN532 放熱パッドのGNDビア（3x3）
    for dx in (-1.2, 0, 1.2):
        for dy in (-1.2, 0, 1.2):
            add_via(board, "GND", UX + dx, UY + dy)
    # 2列（鏡像）
    for side, row, s in (("1", ROW1, 1), ("2", ROW2, -1)):
        n = int(side)
        c1a, c1b = pad(board, f"C{22+n}", "1"), pad(board, f"C{22+n}", "2")
        sp_a, sp_b = pad(board, f"C{24+n}", "1"), pad(board, f"C{24+n}", "2")
        jp_a, jp_b = pad(board, f"JP{n}", "1"), pad(board, f"JP{n}", "2")
        add_track(board, f"TXL{side}", [pad(board, f"L{n}", "2"), jp_a], W_RF)         # L0 → ジャンパ
        add_track(board, f"TXF{side}", [jp_b, (XJ3, row), c1a], W_RF)                  # ジャンパ → 測定端子 → (C0) → C1
        add_track(board, f"ANTM{side}", [c1b, pad(board, f"R{20+n}", "1")], W_RF)      # C1 → (C2, C2予備) → Rq
        add_track(board, f"TXF{side}", [c1a, sp_a], W_RF)                              # C1 予備（並列）
        add_track(board, f"ANTM{side}", [c1b, sp_b], W_RF)
        # コイルの外側端子（列と同じ高さ、コイルの左外側にあるパッド）
        ant = [rel(p.GetPosition()) for p in board.FindFootprintByReference("AE1").Pads()
               if abs(rel(p.GetPosition())[1] - row) < 0.01 and rel(p.GetPosition())[0] < CX - 23]
        add_track(board, f"ANT{side}", [pad(board, f"R{20+n}", "2"), ant[0]], W_RF)
        # 並列部品の GND 側 → 外側の GND ビア
        for ref in (f"C{20+n}", f"C{26+n}", f"C{28+n}"):
            g = pad(board, ref, "2")
            v = (g[0], row + s * 2.6)
            add_track(board, "GND", [g, v], W_RF)
            add_via(board, "GND", *v)


# ESP32 モジュール裏の GND パッドにビアを打つ（放熱と GND の低インピーダンス化）
def add_module_gnd_vias(board):
    fp = board.FindFootprintByReference("U2")
    seen = set()
    for p in fp.Pads():
        if p.GetNumber() in [str(i) for i in range(57, 66)] and p.GetSize(pcbnew.F_Cu).x > pcbnew.FromMM(1.0):
            x, y = rel(p.GetPosition())
            key = (round(x, 2), round(y, 2))
            if key not in seen:
                seen.add(key)
                add_via(board, "GND", x, y)


# コイル内側の橋（パッド2: 内側端 → 外側端子）を B.Cu に固定配線する
def add_coil_bridge(board):
    fp = board.FindFootprintByReference("AE1")
    p2 = [p for p in fp.Pads() if p.GetNumber() == "2"]
    add_track(board, "ANT2", [rel(p2[0].GetPosition()), rel(p2[1].GetPosition())], 0.6, pcbnew.B_Cu)


# 配線禁止のルールエリア（ビア・ベタは可）を1つ追加する。rect = (x0, y0, x1, y1) 基板相対 mm
def add_track_keepout(board, name, layer, rect):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    z.SetLayer(layer)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(False)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetDoNotAllowZoneFills(False)
    o = z.Outline()
    o.NewOutline()
    x0, y0, x1, y1 = rect
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        o.Append(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))
    board.Add(z)


# 整合部の2列の間（表面）に自動配線の線を通さない
#   固定配線（2列そのもの・並列部品の GND 線）はこの範囲に入らないように範囲を取ってある
#   FIXME: 裏面（整合部の真下）も禁止にすると Freerouting が 10本前後引き残すため、裏面は禁止していない。
#          裏面には上下をつなぐ信号線が数本横切る（README §5 参照）。手配線で寄せられれば GND ベタがより連続する
def add_rf_keepouts(board):
    x_end = CX - gen_coil.A0_MM / 2 - gen_coil.TERM_OUT - 0.8      # コイル端子の手前まで
    add_track_keepout(board, "RF_no_tracks_F", pcbnew.F_Cu, (PX + 4.5, ROW2 + 0.7, x_end, ROW1 - 0.7))


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
        if p.footprint.split(":")[0] in FAB_REF_LIBS or p.ref in FAB_REF_PARTS:
            fp.Reference().SetLayer(pcbnew.F_Fab)
        for pad_ in fp.Pads():
            n = p.nets.get(pad_.GetNumber())
            if n:
                pad_.SetNet(nets[n])
        board.Add(fp)
    if missing:
        raise SystemExit(f"配置が未定義の部品: {missing}")

    add_coil_bridge(board)
    add_rf_routes(board)
    add_module_gnd_vias(board)
    add_rf_keepouts(board)
    for pad_ in board.FindFootprintByReference("J1").Pads():
        if pad_.GetNumber() == "SH":
            pad_.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)   # シールドはGNDベタに全面接続
    board.BuildConnectivity()
    pcbnew.SaveBoard(OUT, board)
    write_project_rules()
    print(f"生成: {OUT}（部品 {len(board.GetFootprints())}、ネット {len(nets)}）")


if __name__ == "__main__":
    main()
