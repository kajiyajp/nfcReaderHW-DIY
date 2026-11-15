# 作成日: 2026-11-15
# 目的: design.py の定義から KiCad 回路図 (kicad/nfc_reader.kicad_sch) とプロジェクトファイルを生成する
#
# 使い方: python gen_sch.py
# 接続はすべて「ピン端に置いたネットラベル」で表現する（配線ワイヤは引かない）

import json
import os
import uuid

import kicad_lib as k
from design import PARTS

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kicad")
PROJECT = "nfc_reader"
GRID = 2.54
SHEET_W = 400.0
NS = uuid.UUID("6b1f2c1e-0000-4000-8000-000000000001")   # 再生成してもUUIDが変わらないように固定


# 名前から決定的なUUIDを作る
def uid(*names):
    return str(uuid.uuid5(NS, "/".join(names)))


# グリッドに丸める
def snap(v):
    return round(round(v / GRID) * GRID, 2)


# ピン方向から、ラベルの角度と寄せ方向を決める
def label_dir(pin_angle):
    a = int(pin_angle) % 360
    return {0: (180, "right"), 180: (0, "left"), 90: (270, "right"), 270: (90, "left")}[a]


# シンボルのピンが占める範囲（ラベル分の余白込み）を返す
def bbox(pins):
    if not pins:
        return -5, -5, 5, 5
    xs = [p[3] for p in pins]
    ys = [-p[4] for p in pins]
    return min(xs) - 14, min(ys) - 6, max(xs) + 14, max(ys) + 6


# 回路図テキストを組み立てて書き出す
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    root = uid("root")
    syms = {}
    for p in PARTS:
        if p.lib not in syms:
            lib, name = p.lib.split(":")
            syms[p.lib] = k.load_symbol(lib, name)

    # --- 配置（グループごとに棚詰め） ---
    placed = []
    x, y, row_h = 15.0, 20.0, 0.0
    last_group = None
    for p in PARTS:
        pins = k.pins(syms[p.lib])
        x0, y0, x1, y1 = bbox(pins)
        w, h = x1 - x0, y1 - y0
        if p.group != last_group and last_group is not None:
            x, y, row_h = 15.0, y + row_h + 10, 0.0       # グループが変わったら改行
        if x + w > SHEET_W:
            x, y, row_h = 15.0, y + row_h + 4, 0.0
        sx, sy = snap(x - x0), snap(y - y0)
        placed.append((p, sx, sy, pins))
        x += w + 4
        row_h = max(row_h, h)
        last_group = p.group
    paper = "A3" if y + row_h < 280 else "A2"

    out = [f'(kicad_sch (version 20260306) (generator "gen_sch.py") (generator_version "10.0") '
           f'(uuid "{root}") (paper "{paper}")']
    out.append('(title_block (title "NFC Reader (PN532 + ESP32-S3)") (date "2026-11-16") (rev "0.2"))')

    # --- 埋め込みシンボル定義 ---
    out.append("(lib_symbols")
    for lib_id, node in syms.items():
        n = list(node)
        n[1] = f'"{lib_id}"'
        out.append(k.dump(n))
    out.append(")")

    # --- 部品・ラベル・未接続マーク ---
    used_nets = set()
    for p, sx, sy, pins in placed:
        is_power = p.ref.startswith("#")
        fp = f'"{p.footprint}"'
        out.append(
            f'(symbol (lib_id "{p.lib}") (at {sx} {sy} 0) (unit 1) (exclude_from_sim no) '
            f'(in_bom {"no" if is_power or p.dnp else "yes"}) (on_board {"no" if is_power else "yes"}) '
            f'(dnp {"yes" if p.dnp else "no"}) (uuid "{uid(p.ref)}")'
            f'\n\t(property "Reference" "{p.ref}" (at {sx} {snap(sy - 3)} 0) (effects (font (size 1.27 1.27)) {"(hide yes)" if is_power else ""}))'
            f'\n\t(property "Value" "{p.value}" (at {sx} {snap(sy + 3)} 0) (effects (font (size 1.27 1.27))))'
            f'\n\t(property "Footprint" {fp} (at {sx} {sy} 0) (effects (font (size 1.27 1.27)) (hide yes)))'
            f'\n\t(property "Datasheet" "" (at {sx} {sy} 0) (effects (font (size 1.27 1.27)) (hide yes)))'
            f'\n\t(property "MPN" "{p.mpn}" (at {sx} {sy} 0) (effects (font (size 1.27 1.27)) (hide yes)))'
            f'\n\t(property "LCSC" "{p.lcsc}" (at {sx} {sy} 0) (effects (font (size 1.27 1.27)) (hide yes)))'
        )
        for num, *_ in pins:
            out.append(f'\t(pin "{num}" (uuid "{uid(p.ref, "pin", num)}"))')
        out.append(f'\t(instances (project "{PROJECT}" (path "/{root}" (reference "{p.ref}") (unit 1)))))')

        done = set()
        for num, name, etype, px, py, pa in pins:
            ax, ay = round(sx + px, 2), round(sy - py, 2)
            key = (ax, ay)
            if key in done:
                continue                                   # 同じ位置に重なったピン（積層ピン）は1回だけ
            done.add(key)
            net = p.nets.get(num)
            if net is None:
                # 同じ座標の別ピンにネットがあればそれを使う
                net = next((p.nets[n2] for n2, _, _, x2, y2, _ in pins
                            if (round(sx + x2, 2), round(sy - y2, 2)) == key and n2 in p.nets), None)
            if net is None:
                out.append(f'(no_connect (at {ax} {ay}) (uuid "{uid(p.ref, "nc", num)}"))')
                continue
            used_nets.add(net)
            ang, just = label_dir(pa)
            out.append(f'(label "{net}" (at {ax} {ay} {ang}) (effects (font (size 1.27 1.27)) (justify {just} bottom)) '
                       f'(uuid "{uid(p.ref, "lbl", num)}"))')

    out.append(f'(sheet_instances (path "/" (page "1")))')
    out.append("(embedded_fonts no))")

    with open(os.path.join(OUT_DIR, PROJECT + ".kicad_sch"), "w", encoding="utf8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    pro = os.path.join(OUT_DIR, PROJECT + ".kicad_pro")
    if not os.path.exists(pro):
        with open(pro, "w", encoding="utf8") as f:
            json.dump({"meta": {"filename": PROJECT + ".kicad_pro", "version": 3}}, f, indent=2)
    print(f"生成: {len(PARTS)}部品, {len(used_nets)}ネット, 用紙 {paper}")


if __name__ == "__main__":
    main()
