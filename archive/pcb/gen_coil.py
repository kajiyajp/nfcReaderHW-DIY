# 作成日: 2026-11-15 ／ 更新: 2026-11-16（端子をコイル左辺の中央に移し、整合部を左右対称に並べられるようにした）
# 目的: antenna_calc.py と同じ寸法で、NFCコイルのフットプリント（ネットタイ付き）を生成し、
#       プロジェクト用のライブラリ表（sym-lib-table / fp-lib-table）も書き出す
#
# 使い方: python gen_coil.py
# 構造: F.Cu の矩形スパイラル。左辺の中央（y=+TERM_HALF）から始まり、内側へ N 巻きして左辺の中央（y=-TERM_HALF）で終わる。
#       内側の端はスルーホール(パッド2)から B.Cu で左へ引き出す（橋の配線は gen_pcb.py が引く）。
#       端子(パッド1/2)はコイル左辺の 2.5mm 外側に、中心線に対して上下対称（間隔 2*TERM_HALF）に並ぶ。
#       → 整合部の2列（TX1側/TX2側）をまっすぐ横に引いて、そのまま端子に入れられる。
#       コイル内側は銅ベタ禁止のキープアウト領域にする。

import os
import uuid

import antenna_calc as ac

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kicad")
LIB = os.path.join(OUT, "nfc_reader.pretty")
NAME = f"NFC_Coil_{ac.A0*1e3:.0f}x{ac.B0*1e3:.0f}_{ac.N}T"
NS = uuid.UUID("6b1f2c1e-0000-4000-8000-000000000002")
TERM_HALF = 2.4      # 端子の上下間隔の半分 [mm]（整合部2列の間隔 4.8mm に合わせる。gen_pcb.py もこれを使う）
TERM_OUT = 2.5       # コイル外形の左辺から端子中心までの距離 [mm]
A0_MM = ac.A0 * 1e3  # コイル外形の横幅 [mm]（gen_pcb.py が使う）
_n = [0]


# 連番から決定的なUUIDを作る
def uid():
    _n[0] += 1
    return str(uuid.uuid5(NS, f"{NAME}/{_n[0]}"))


# 銅箔の線分を1本出力する
def line(a, b, layer, w):
    return (f'\t(fp_line (start {a[0]:.3f} {a[1]:.3f}) (end {b[0]:.3f} {b[1]:.3f}) '
            f'(stroke (width {w}) (type solid)) (layer "{layer}") (uuid "{uid()}"))')


# スパイラルの頂点列を返す（フットプリント座標, mm, y下向き）
#   左辺 (x=-ax, y=+s) から上へ出発し、時計回りに n 巻きして、左辺の内側 (x=-ax+n*p, y=-s) で終わる
#   巻数・線長は旧版（左下の角から始まる n 巻き）とほぼ同じ（差は +1mm 程度）なので antenna_calc.py の値はそのまま使える
def spiral(n, w, g, a0, b0, s):
    p = w + g
    ax, by = a0 / 2 - w / 2, b0 / 2 - w / 2
    pts = [(-ax, s)]
    for i in range(n):
        d = i * p
        pts += [(-ax + d, -by + d), (ax - d, -by + d), (ax - d, by - d), (-ax + d + p, by - d)]
    pts.append((-ax + n * p, -s))
    return pts, ax, by, p


# フットプリントを生成する
def main():
    os.makedirs(LIB, exist_ok=True)
    w, g = ac.W * 1e3, ac.G * 1e3
    a0, b0 = ac.A0 * 1e3, ac.B0 * 1e3
    pts, ax, by, p = spiral(ac.N, w, g, a0, b0, TERM_HALF)
    inner = pts[-1]
    term_x = -a0 / 2 - TERM_OUT              # 端子パッドのX（コイル左辺の外側）
    pad1 = (term_x, TERM_HALF)               # 外側端の左
    pad2_out = (term_x, -TERM_HALF)          # 内側端の左（B.Cu で左へ引き出す）
    out = [f'(footprint "{NAME}"',
           '\t(version 20260206) (generator "gen_coil.py") (generator_version "10.0")',
           '\t(layer "F.Cu")',
           f'\t(descr "NFC 13.56MHz PCB coil {a0:.0f}x{b0:.0f}mm {ac.N} turns, w/g {w}/{g}mm, terminals at left center")',
           '\t(tags "NFC antenna coil net tie")',
           f'\t(property "Reference" "AE**" (at {-a0/2 + 3:.2f} {-b0/2 - 1.5:.2f} 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))',
           f'\t(property "Value" "{NAME}" (at 0 {b0/2 - 3:.2f} 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 1 1) (thickness 0.15))))',
           '\t(attr smd exclude_from_bom)',
           '\t(net_tie_pad_groups "1, 2")']
    # スパイラル本体（F.Cu）
    out.append(line(pad1, pts[0], "F.Cu", w))
    for a, b in zip(pts, pts[1:]):
        out.append(line(a, b, "F.Cu", w))
    # 内側端 → 外側の橋（B.Cu）はフットプリントに含めず、gen_pcb.py が基板上の配線として引く
    #   （フットプリント内の図形線はKiCadの接続判定に含まれず、未配線扱いになるため）
    # パッド：1=外側端(SMD), 2=内側端と外側端(スルーホール)
    out.append(f'\t(pad "1" smd rect (at {pad1[0]:.3f} {pad1[1]:.3f}) (size 1.2 1.2) (layers "F.Cu" "F.Mask") (uuid "{uid()}"))')
    for q in (inner, pad2_out):
        out.append(f'\t(pad "2" thru_hole circle (at {q[0]:.3f} {q[1]:.3f}) (size 0.9 0.9) (drill 0.4) '
                   f'(layers "*.Cu" "*.Mask") (uuid "{uid()}"))')
    # 外形（シルク）。端子の引き出し部分は空けておく
    hx, hy = a0 / 2 + 0.5, b0 / 2 + 0.5
    gap = TERM_HALF + 1.0
    silk = [[(-hx, -gap), (-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy), (-hx, gap)]]
    for poly in silk:
        for a, b in zip(poly, poly[1:]):
            out.append(line(a, b, "F.SilkS", 0.12))
    # コートヤード（端子を含む）
    cxl, cxr, cy = term_x - 0.6 - 0.25, hx + 0.5, hy + 0.5
    cbox = [(cxl, -cy), (cxr, -cy), (cxr, cy), (cxl, cy), (cxl, -cy)]
    for a, b in zip(cbox, cbox[1:]):
        out.append(line(a, b, "F.CrtYd", 0.05))
    # コイル内側＋線路の下は銅ベタ禁止（両面）
    kx, ky = a0 / 2 + 1.0, b0 / 2 + 1.0
    poly = " ".join(f"(xy {x:.3f} {y:.3f})" for x, y in [(-kx, -ky), (kx, -ky), (kx, ky), (-kx, ky)])
    out.append(f'\t(zone (layers "F.Cu" "B.Cu") (uuid "{uid()}") (name "NFC_keepout") (hatch edge 0.5) '
               '(connect_pads (clearance 0)) (min_thickness 0.25) '
               '(keepout (tracks allowed) (vias allowed) (pads allowed) (copperpour not_allowed) (footprints allowed)) '
               '(placement (enabled no) (sheetname "")) '
               '(fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0)) '
               f'(polygon (pts {poly})))')
    out.append("\t(embedded_fonts no)")
    out.append(")")
    path = os.path.join(LIB, NAME + ".kicad_mod")
    with open(path, "w", encoding="utf8", newline="\n") as f:
        f.write("\n".join(out) + "\n")

    # プロジェクト用ライブラリ表（KiCad 標準ライブラリ＋自作）
    syms = ["Device", "Connector", "Connector_Generic", "Power_Protection", "Regulator_Linear", "RF_Module", "RF_NFC",
            "Switch", "Transistor_BJT", "Mechanical", "power"]
    fps = ["Resistor_SMD", "Capacitor_SMD", "Inductor_SMD", "Connector_USB", "Connector_PinHeader_2.54mm",
           "Package_TO_SOT_SMD", "Package_DFN_QFN", "RF_Module", "Button_Switch_SMD", "LED_SMD", "Buzzer_Beeper",
           "Diode_SMD", "Crystal", "MountingHole", "TestPoint"]
    with open(os.path.join(OUT, "sym-lib-table"), "w", encoding="utf8", newline="\n") as f:
        f.write("(sym_lib_table\n  (version 7)\n")
        for s in syms:
            f.write(f'  (lib (name "{s}")(type "KiCad")(uri "${{KICAD10_SYMBOL_DIR}}/{s}.kicad_sym")(options "")(descr ""))\n')
        f.write(")\n")
    with open(os.path.join(OUT, "fp-lib-table"), "w", encoding="utf8", newline="\n") as f:
        f.write("(fp_lib_table\n  (version 7)\n")
        for s in fps:
            f.write(f'  (lib (name "{s}")(type "KiCad")(uri "${{KICAD10_FOOTPRINT_DIR}}/{s}.pretty")(options "")(descr ""))\n')
        f.write('  (lib (name "nfc_reader")(type "KiCad")(uri "${KIPRJMOD}/nfc_reader.pretty")(options "")(descr "自作"))\n')
        f.write(")\n")
    print(f"生成: {path}（頂点 {len(pts)}、内側端 {inner}、端子 {pad1} / {pad2_out}）")


if __name__ == "__main__":
    main()
