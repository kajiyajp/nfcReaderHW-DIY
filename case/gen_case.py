# 作成日: 2026-11-16
# 目的: 市販の PN532 NFC モジュール V3（約 40×43mm）と XIAO RP2040 を入れるケース（本体＋蓋）を作り、
#       3D プリント用の STEP / STL を書き出す（firmware/xiao_rp2040_pn532_hid の読み取り機用）
#
# 使い方（FreeCAD 1.0 のコマンドライン版で実行）:
#   & "C:\Program Files\FreeCAD 1.0\bin\freecadcmd.exe" case\gen_case.py
# 出力: case/nfc_case_base.step・.stl（本体）、nfc_case_lid.step・.stl（蓋）、nfc_case_assembly.step（基板の目安入りの組立図）
#
# 構成（上から見て、左に PN532、右に XIAO。USB-C は右の壁から出す）
#   - PN532 は部品面（アンテナ）を上にして、取付穴 2 つのボス（M3 タッピングねじ）と、残りの角 2 つの支え柱に載せる。
#     基板の下は配線を通す 6mm のすき間。カードは蓋の上からかざす（蓋の厚さ 1.2mm）
#   - XIAO RP2040 は部品面を上にして底に置き、左右のガイドと奥の止めで位置を決める。蓋の柱で上から押さえる
#   - 蓋は内側に入るふち（リップ）で差し込む。固いときはリップを紙やすりで、緩いときは両面テープで調整する
#
# 寸法はすべて mm。基板の実寸（特に PN532 の取付穴の位置）は、届いたらノギスで測って下の定数を直す

import os

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- 中に入れる基板（実物で要確認） ----
PN_W, PN_H, PN_T = 40.0, 43.0, 1.6          # PN532 モジュールの横・縦・厚さ（商品画像の寸法）
PN_PARTS = 2.5                               # PN532 の部品面の高さ（ディップスイッチ・コンデンサ）
# 取付穴の中心（基板の左上の角から、右へ x・下へ y）。商品画像から読んだ値
PN_HOLES = [(32.5, 7.3), (7.9, 34.6)]
PN_HOLE_D = 3.2                              # 取付穴の径（M3 が通る）
XI_L, XI_W, XI_T = 21.0, 17.8, 1.0           # XIAO RP2040 の長さ（USB の向き）・幅・基板の厚さ
XI_TOP = 3.6                                 # XIAO の底から部品（USB-C・シールド）の上面まで
USB_CZ = 2.6                                 # XIAO の底から USB-C の中心まで

# ---- ケース ----
WALL, FLOOR, LID_T = 2.0, 1.6, 1.2           # 壁・底・蓋（アンテナの上）の厚さ
CLR = 0.5                                    # 基板と壁のすき間
GAP = 4.0                                    # PN532 と XIAO の間（配線を通す）
UNDER = 6.0                                  # PN532 の下のすき間（配線）
TOP_CLR = 0.7                                # PN532 の部品の上と蓋の間
IN_X = CLR + PN_W + GAP + XI_L + 0.3         # 内寸
IN_Y = PN_H + 2 * CLR
IN_Z = UNDER + PN_T + PN_PARTS + TOP_CLR
OUT_X, OUT_Y = IN_X + 2 * WALL, IN_Y + 2 * WALL
BASE_Z = FLOOR + IN_Z                        # 本体の高さ（蓋は上に載る）
R_OUT = 3.0                                  # 外側の角の丸み
LIP_DEPTH, LIP_T, LIP_CLR = 2.5, 1.2, 0.2    # 蓋のリップの深さ・厚さ・壁とのすき間
BOSS_D, BOSS_PILOT = 6.0, 2.5                # PN532 用ボス（M3 タッピングの下穴 2.5）
POST_D = 4.0                                 # 支え柱
USB_W, USB_H = 12.0, 7.0                     # USB-C の穴（ケーブルの根元まで入る大きさ）

# 位置（ケースの外側の左下の角が原点。z は底面が 0）
PN_X0, PN_Y0 = WALL + CLR, WALL + CLR        # PN532 の左下の角
PN_Z0 = FLOOR + UNDER                        # PN532 の下面
XI_X0 = WALL + CLR + PN_W + GAP              # XIAO の奥側（USB と反対）の端
XI_Y0 = WALL + (IN_Y - XI_W) / 2             # XIAO の下側の辺


# 角を丸めた箱（上下方向の辺だけ丸める）
def rounded_box(x, y, z, w, d, h, r):
    b = Part.makeBox(w, d, h, App.Vector(x, y, z))
    if r > 0:
        edges = [e for e in b.Edges if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1e-6]
        b = b.makeFillet(r, edges)
    return b


# 円柱
def cyl(x, y, z, d, h):
    return Part.makeCylinder(d / 2, h, App.Vector(x, y, z))


# PN532 の取付穴の位置（ケース座標）
def pn_hole_xy():
    return [(PN_X0 + hx, PN_Y0 + PN_H - hy) for hx, hy in PN_HOLES]


# 本体
def make_base():
    body = rounded_box(0, 0, 0, OUT_X, OUT_Y, BASE_Z, R_OUT)
    cavity = rounded_box(WALL, WALL, FLOOR, IN_X, IN_Y, BASE_Z, max(R_OUT - WALL, 0.5))
    body = body.cut(cavity)
    # PN532 のボス（取付穴 2 つ）と支え柱（残りの角 2 つ）
    for x, y in pn_hole_xy():
        boss = cyl(x, y, FLOOR - 0.01, BOSS_D, UNDER + 0.01).cut(cyl(x, y, FLOOR, BOSS_PILOT, UNDER + 1))
        body = body.fuse(boss)
    for cx, cy in ((PN_X0 + 3.0, PN_Y0 + PN_H - 3.0), (PN_X0 + PN_W - 3.0, PN_Y0 + 3.0)):
        body = body.fuse(cyl(cx, cy, FLOOR - 0.01, POST_D, UNDER + 0.01))
    # XIAO のガイド（左右の細い壁）と奥の止め
    g_t, g_h = 1.2, 2.0
    for gy in (XI_Y0 - 0.25 - g_t, XI_Y0 + XI_W + 0.25):
        body = body.fuse(Part.makeBox(XI_L - 4.0, g_t, g_h, App.Vector(XI_X0 + 2.0, gy, FLOOR - 0.01)))
    body = body.fuse(Part.makeBox(g_t, XI_W - 6.0, g_h, App.Vector(XI_X0 - 0.3 - g_t, XI_Y0 + 3.0, FLOOR - 0.01)))
    # USB-C の穴（右の壁。底面から上へ）
    usb_cy = XI_Y0 + XI_W / 2
    usb_cz = FLOOR + max(USB_CZ, USB_H / 2)
    hole = rounded_box(OUT_X - WALL - 1.0, usb_cy - USB_W / 2, usb_cz - USB_H / 2, WALL + 2.0, USB_W, USB_H, 0)
    hole = hole.makeFillet(1.5, [e for e in hole.Edges
                                 if abs(e.Vertexes[0].Point.x - e.Vertexes[1].Point.x) > 1e-6])
    body = body.cut(hole)
    return body.removeSplitter()


# 蓋（上板＋内側に入るリップ＋XIAO の押さえ柱＋かざす位置の目印の溝）
def make_lid():
    z0 = BASE_Z
    plate = rounded_box(0, 0, z0, OUT_X, OUT_Y, LID_T, R_OUT)
    lx, ly = WALL + LIP_CLR, WALL + LIP_CLR
    lw, ld = IN_X - 2 * LIP_CLR, IN_Y - 2 * LIP_CLR
    lip = rounded_box(lx, ly, z0 - LIP_DEPTH, lw, ld, LIP_DEPTH + 0.01, max(R_OUT - WALL - LIP_CLR, 0.5))
    lip = lip.cut(rounded_box(lx + LIP_T, ly + LIP_T, z0 - LIP_DEPTH - 1, lw - 2 * LIP_T, ld - 2 * LIP_T,
                              LIP_DEPTH + 2, 0.5))
    lid = plate.fuse(lip)
    # XIAO の押さえ柱（シールドの上を押す。USB-C より奥側）
    press_top = FLOOR + XI_TOP + 0.2
    lid = lid.fuse(cyl(XI_X0 + 7.0, XI_Y0 + XI_W / 2, press_top, 5.0, z0 - press_top + 0.01))
    # かざす位置の目印（PN532 の中心に、深さ 0.4mm の輪）
    cx, cy = PN_X0 + PN_W / 2, PN_Y0 + PN_H / 2
    ring = cyl(cx, cy, z0 + LID_T - 0.4, 30.0, 1.0).cut(cyl(cx, cy, z0 + LID_T - 0.5, 28.0, 1.2))
    lid = lid.cut(ring)
    return lid.removeSplitter()


# 中身の目安（組立図用。印刷はしない）
def make_dummies():
    pn = Part.makeBox(PN_W, PN_H, PN_T, App.Vector(PN_X0, PN_Y0, PN_Z0))
    for x, y in pn_hole_xy():
        pn = pn.cut(cyl(x, y, PN_Z0 - 1, PN_HOLE_D, PN_T + 2))
    pn = pn.fuse(Part.makeBox(PN_W - 8, PN_H - 16, PN_PARTS, App.Vector(PN_X0 + 4, PN_Y0 + 8, PN_Z0 + PN_T)))
    xi = Part.makeBox(XI_L, XI_W, XI_T, App.Vector(XI_X0, XI_Y0, FLOOR))
    xi = xi.fuse(Part.makeBox(7.5, 8.9, 3.2, App.Vector(XI_X0 + XI_L - 7.5 + 0.8, XI_Y0 + (XI_W - 8.9) / 2, FLOOR + XI_T)))
    xi = xi.fuse(Part.makeBox(12.0, 12.0, 2.2, App.Vector(XI_X0 + 2.5, XI_Y0 + 2.9, FLOOR + XI_T)))
    return pn, xi


def main():
    base, lid = make_base(), make_lid()
    pn, xi = make_dummies()
    out = {
        "nfc_case_base": base,
        "nfc_case_lid": lid,
    }
    for name, shape in out.items():
        shape.exportStep(os.path.join(HERE, name + ".step"))
        mesh = shape.tessellate(0.05)
        import Mesh
        Mesh.Mesh([[mesh[0][i] for i in tri] for tri in mesh[1]]).write(os.path.join(HERE, name + ".stl"))
        print(f"{name}: 体積 {shape.Volume / 1000:.1f} cm3、有効な立体 {shape.isValid()}")
    # 組立図（本体・蓋・基板の目安）
    Part.makeCompound([base, lid, pn, xi]).exportStep(os.path.join(HERE, "nfc_case_assembly.step"))
    # 干渉チェック（基板の目安と本体・蓋が重ならないか）
    for a_name, a in (("base", base), ("lid", lid)):
        for b_name, b in (("PN532", pn), ("XIAO", xi)):
            v = a.common(b).Volume
            print(f"干渉 {a_name} × {b_name}: {v:.3f} mm3")
    print(f"外形 {OUT_X:.1f} × {OUT_Y:.1f} × {BASE_Z + LID_T:.1f} mm（本体 {BASE_Z:.1f}、蓋 {LID_T}）")


main()
