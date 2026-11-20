# 作成日: 2026-11-16 ／ 更新: 2026-11-20（ブザーを入れる場所と音の穴を追加）
# 目的: 市販の PN532 NFC モジュール V3（約 40×43mm）と XIAO RP2040、ブザーを入れるケース（本体＋蓋）を作り、
#       3D プリント用の STEP / STL を書き出す（firmware/xiao_rp2040_pn532_hid の読み取り機用）
#
# 使い方（FreeCAD 1.0 のコマンドライン版で実行）:
#   & "$env:LOCALAPPDATA\Programs\FreeCAD 1.1\bin\freecadcmd.exe" case\gen_case.py
#   （FreeCAD 1.0 を全員向けに入れた PC では "C:\Program Files\FreeCAD 1.0\bin\freecadcmd.exe"）
# 出力: case/nfc_case_base.step・.stl（本体）、nfc_case_lid.step・.stl（蓋）、nfc_case_assembly.step（基板の目安入りの組立図）
#
# 構成（上から見て、左から PN532・ブザー・XIAO。XIAO は上下の真ん中で、USB-C は右の壁から出す）
#   - PN532 と壁の間は 5mm あける（2026-11-20 の指示）
#   - PN532 は部品面（アンテナ）を上にして、取付穴 2 つのボス（M3 タッピングねじ）と、残りの角 2 つの支え柱に載せる。
#     基板の下は配線を通すすき間（ブザーの高さに合わせて本体を高くしたぶん広い。ブザーの 470Ω もここに置ける）。
#     カードは蓋の上からかざす（蓋の厚さ 1.2mm。PN532 の上と蓋の間は前と同じ）
#   - XIAO RP2040 は部品面を上にして底に置き、左右のガイドと奥の止めで位置を決める。蓋の柱で上から押さえる
#   - ブザー（winova の連続音ブザー。本体は丸く、底に取付耳が 2 つ）は音の出る面を上にして底に置き、
#     耳の穴に底のピンを通して位置を決める（ピンの先をこてで少しつぶすか、ホットボンドで留める）。
#     耳は縦向き。PN532 と XIAO の間の真ん中に置き、蓋のブザーの真上に音の穴をあける
#     （PN532 の基板の端から 4mm。ブザーの中の金属板で読み取りが弱まらないか、組んだら読み取り距離を確かめる）
#   - 蓋は内側に入るふち（リップ）で差し込む。固いときはリップを紙やすりで、緩いときは両面テープで調整する
#
# 寸法はすべて mm。基板の実寸（特に PN532 の取付穴の位置）は、届いたらノギスで測って下の定数を直す

import math
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
# ブザー（Amazon B0CZJ5DGDH）。商品ページに寸法がないので、同じ形の連続音ブザー（SFM-27 型）の一般的な寸法。
# 届いたらノギスで測って直す
BZ_D, BZ_H = 23.0, 15.0                      # 本体の直径・高さ（底から音の出る面まで）
BZ_SPAN, BZ_PITCH = 36.0, 30.0               # 取付耳の端から端まで・耳の穴の中心の間隔
BZ_EAR_W, BZ_EAR_T, BZ_HOLE_D = 7.0, 2.5, 3.0  # 耳の幅・厚さ・穴の径

# ---- ケース ----
WALL, FLOOR, LID_T = 2.0, 1.6, 1.2           # 壁・底・蓋（アンテナの上）の厚さ
PN_CLR = 5.0                                 # PN532 と壁のすき間（上下左。2026-11-20 に 0.5 → 5mm）
BZ_GAP = 4.0                                 # ブザーの本体と PN532・XIAO の奥の止めとの間（左右同じ。ブザーを真ん中に置く）
XI_END_CLR = 0.3                             # XIAO と右の壁（USB-C 側）のすき間
TOP_CLR = 0.7                                # PN532 の部品の上と蓋の間
BZ_TOP_CLR = 0.5                             # ブザーの上と蓋の間
LIP_DEPTH, LIP_T, LIP_CLR = 2.5, 1.2, 0.2    # 蓋のリップの深さ・厚さ・壁とのすき間
XI_GUIDE_T = 1.2                             # XIAO のガイドと奥の止めの厚さ（XIAO との間は 0.25・0.3）
# 内側の高さはブザーで決まる。PN532 の下のすき間（UNDER）を広げて、PN532 の上と蓋の間は TOP_CLR のまま保つ
IN_Z = max(6.0 + PN_T + PN_PARTS + TOP_CLR, BZ_H + BZ_TOP_CLR)
UNDER = IN_Z - (PN_T + PN_PARTS + TOP_CLR)   # PN532 の下のすき間（配線・ブザーの抵抗）
# 横の並び（左から）: PN532 ｜ ブザー（耳は縦向き）｜ XIAO（USB-C を右の壁へ）
IN_X = PN_CLR + PN_W + BZ_GAP + BZ_D + BZ_GAP + XI_GUIDE_T + 0.3 + XI_L + XI_END_CLR   # 内寸
IN_Y = max(PN_H + 2 * PN_CLR, BZ_SPAN + 2 * (LIP_CLR + LIP_T + 0.5))
OUT_X, OUT_Y = IN_X + 2 * WALL, IN_Y + 2 * WALL
BASE_Z = FLOOR + IN_Z                        # 本体の高さ（蓋は上に載る）
R_OUT = 3.0                                  # 外側の角の丸み
BOSS_D, BOSS_PILOT = 6.0, 2.5                # PN532 用ボス（M3 タッピングの下穴 2.5）
POST_D = 4.0                                 # 支え柱
USB_W, USB_H = 12.0, 7.0                     # USB-C の穴（ケーブルの根元まで入る大きさ）
BZ_PIN_D, BZ_PIN_H = 2.6, 4.0                # ブザーの耳の穴に通すピン（耳より 1.5mm 出る。先をつぶして留める）
SND_D, SND_PITCH = 2.0, 3.2                  # 蓋の音の穴の径・間隔（ブザーの真上に 7 個、六角形に並べる）

# 位置（ケースの外側の左下の角が原点。z は底面が 0）
PN_X0 = WALL + PN_CLR                        # PN532 の左下の角（上下は真ん中）
PN_Y0 = WALL + (IN_Y - PN_H) / 2
PN_Z0 = FLOOR + UNDER                        # PN532 の下面
XI_X0 = WALL + IN_X - XI_END_CLR - XI_L      # XIAO の奥側（USB と反対）の端（USB-C を右の壁に寄せる）
XI_Y0 = WALL + (IN_Y - XI_W) / 2             # XIAO の下側の辺（上下の真ん中）
BZ_CX = PN_X0 + PN_W + BZ_GAP + BZ_D / 2     # ブザーの中心（PN532 と XIAO の奥の止めの真ん中）
BZ_CY = WALL + IN_Y / 2


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
    g_t, g_h = XI_GUIDE_T, 2.0
    for gy in (XI_Y0 - 0.25 - g_t, XI_Y0 + XI_W + 0.25):
        body = body.fuse(Part.makeBox(XI_L - 4.0, g_t, g_h, App.Vector(XI_X0 + 2.0, gy, FLOOR - 0.01)))
    body = body.fuse(Part.makeBox(g_t, XI_W - 6.0, g_h, App.Vector(XI_X0 - 0.3 - g_t, XI_Y0 + 3.0, FLOOR - 0.01)))
    # ブザーの耳の穴に通すピン（2 本。耳は縦向き）
    for sy in (-1, 1):
        body = body.fuse(cyl(BZ_CX, BZ_CY + sy * BZ_PITCH / 2, FLOOR - 0.01, BZ_PIN_D, BZ_PIN_H + 0.01))
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
    # 音の穴（ブザーの真上に 7 個。中心 1 個＋まわりに 6 個）。うるさいときは内側からテープでふさぐ
    for i in range(7):
        if i == 0:
            hx, hy = BZ_CX, BZ_CY
        else:
            a = math.radians(60 * (i - 1))
            hx, hy = BZ_CX + SND_PITCH * math.cos(a), BZ_CY + SND_PITCH * math.sin(a)
        lid = lid.cut(cyl(hx, hy, z0 - 1, SND_D, LID_T + 2))
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
    # ブザー（本体の円柱＋底の取付耳。耳の穴はピンが通る）
    bz = cyl(BZ_CX, BZ_CY, FLOOR, BZ_D, BZ_H)
    bz = bz.fuse(Part.makeBox(BZ_EAR_W, BZ_SPAN, BZ_EAR_T, App.Vector(BZ_CX - BZ_EAR_W / 2, BZ_CY - BZ_SPAN / 2, FLOOR)))
    for sy in (-1, 1):
        bz = bz.cut(cyl(BZ_CX, BZ_CY + sy * BZ_PITCH / 2, FLOOR - 1, BZ_HOLE_D, BZ_EAR_T + 2))
    return pn, xi, bz


def main():
    base, lid = make_base(), make_lid()
    pn, xi, bz = make_dummies()
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
    Part.makeCompound([base, lid, pn, xi, bz]).exportStep(os.path.join(HERE, "nfc_case_assembly.step"))
    # 干渉チェック（中身の目安と本体・蓋、中身どうしが重ならないか）
    for a_name, a in (("base", base), ("lid", lid)):
        for b_name, b in (("PN532", pn), ("XIAO", xi), ("buzzer", bz)):
            v = a.common(b).Volume
            print(f"干渉 {a_name} × {b_name}: {v:.3f} mm3")
    for a_name, a, b_name, b in (("PN532", pn, "buzzer", bz), ("XIAO", xi, "buzzer", bz)):
        print(f"干渉 {a_name} × {b_name}: {a.common(b).Volume:.3f} mm3")
    print(f"外形 {OUT_X:.1f} × {OUT_Y:.1f} × {BASE_Z + LID_T:.1f} mm（本体 {BASE_Z:.1f}、蓋 {LID_T}）")
    print(f"PN532 の下のすき間 {UNDER:.1f} mm、ブザーと PN532 基板の端の距離 {BZ_CX - BZ_D / 2 - (PN_X0 + PN_W):.1f} mm、"
          f"ブザーと XIAO の奥の止めの距離 {XI_X0 - 0.3 - XI_GUIDE_T - (BZ_CX + BZ_D / 2):.1f} mm")
    # render_case.py に書き写す値（中身の目安の位置）
    print(f"[render] PN532 x0={PN_X0:.2f} y0={PN_Y0:.2f} z0={PN_Z0:.2f}  XIAO x0={XI_X0:.2f} y0={XI_Y0:.2f}  "
          f"buzzer cx={BZ_CX:.2f} cy={BZ_CY:.2f}")


main()
