# 作成日: 2026-11-16
# 目的: FusionPCB（Seeed Fusion PCBA）に入稿するガーバー・ドリル・BOM・CPL を fab/ に書き出す
#
# 使い方（KiCad付属のPythonで実行）:
#   & "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" export_fab.py
# 出力（fab/）:
#   nfc_reader_gerber.zip … ガーバー（RS-274X、Protel 拡張子）＋ドリル（Excellon、.TXT）。基板 PCB の注文に使う
#   nfc_reader_bom.csv    … Designator, MPN, Qty, Link（実装してもらう部品だけ。部品番号はカンマ区切り）
#   nfc_reader_cpl.csv    … Designator, X, Y, Rotation, Side（mm、基板の左下が原点、上が +Y。Seeed の記事の例の列）
#   nfc_reader_assembly_top.pdf … 組立図（F.Fab＋F.CrtYd＋外形、A3 に 3 倍。未実装には×、値は省略）
#
# 原点: ガーバー・ドリル・CPL のすべてを「基板の左下」を原点に揃える（一時コピーの基板に補助原点を置いて書き出す）。
# 実装しないもの: 未実装（DNP）、はんだジャンパ（銅箔だけ）、テストポイント（パッドだけ）、取付穴、基板パターンのコイル

import csv
import datetime
import os
import shutil
import subprocess
import tempfile
import zipfile

import pcbnew

from design import PARTS
from gen_pcb import OX, OY, BH
from kicad_lib import KICAD_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "kicad", "nfc_reader.kicad_pcb")
OUT = os.path.join(HERE, "fab")
CLI = os.path.join(KICAD_DIR, "bin", "kicad-cli.exe")

# ガーバーにする層と、Fusion の案内に合わせた拡張子
LAYERS = {
    "F.Cu": "GTL", "B.Cu": "GBL", "F.Mask": "GTS", "B.Mask": "GBS",
    "F.Silkscreen": "GTO", "B.Silkscreen": "GBO", "F.Paste": "GTP", "B.Paste": "GBP", "Edge.Cuts": "GML",
}

# 型番が未定の受動部品は、Fusion の担当者が汎用品を選べるよう「種類 値 サイズ 特性」を MPN 欄に書く
SIZE = {"0402": "0402", "0603": "0603", "0805": "0805"}


# 実装してもらう部品か
def assembled(p):
    if p.ref.startswith("#") or p.dnp:
        return False
    lib = p.footprint.split(":")[0]
    return not (p.ref.startswith(("JP", "TP", "H", "AE")) or lib in ("TestPoint", "MountingHole", "Jumper"))


# MPN 欄の文字（型番がなければ汎用の仕様）
def mpn_of(p):
    if p.mpn:
        return p.mpn
    size = next((v for k, v in SIZE.items() if f"_{k}_" in p.footprint), "")
    kind = {"R": "RES", "C": "CAP", "L": "IND"}.get(p.ref.rstrip("0123456789"), "")
    spec = ""
    if kind == "CAP":
        spec = " C0G" if ("C0G" in p.note or p.value.endswith("p")) else " X7R"
    if kind == "RES":
        spec = " 1%"
    return f"{kind} {p.value} {size}{spec}".strip()


# kicad-cli を実行する
def cli(*args):
    r = subprocess.run([CLI, *args], capture_output=True, text=True, encoding="utf8", errors="replace")
    if r.returncode:
        raise SystemExit(f"kicad-cli 失敗: {' '.join(args[:3])}\n{r.stdout}{r.stderr}")


# 部品番号を自然な順に並べるためのキー（C2 < C10）
def ref_key(ref):
    head = ref.rstrip("0123456789")
    return (head, int(ref[len(head):] or 0))


# BOM を書く
def write_bom(parts, path):
    groups = {}
    for p in parts:
        groups.setdefault((mpn_of(p), p.lcsc), []).append(p.ref)
    rows = sorted(groups.items(), key=lambda kv: ref_key(sorted(kv[1], key=ref_key)[0]))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "MPN", "Qty", "Link"])
        for (mpn, lcsc), refs in rows:
            refs = sorted(refs, key=ref_key)
            link = f"https://www.lcsc.com/product-detail/{lcsc}.html" if lcsc else ""
            w.writerow([",".join(refs), mpn, len(refs), link])
    return len(rows)


# CPL を書く（座標は基板左下が原点、上が +Y）
def write_cpl(board, refs, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "X", "Y", "Rotation", "Side"])     # Seeed の記事の例と同じ列
        for ref in sorted(refs, key=ref_key):
            fp = board.FindFootprintByReference(ref)
            p = fp.GetPosition()
            x = p.x / 1e6 - OX
            y = (OY + BH) - p.y / 1e6
            side = "Bottom" if fp.IsFlipped() else "Top"
            w.writerow([ref, f"{x:.3f} mm", f"{y:.3f} mm", f"{fp.GetOrientationDegrees() % 360:.0f}", side])


# 書き出す
def main():
    os.makedirs(OUT, exist_ok=True)
    parts = [p for p in PARTS if assembled(p)]
    with tempfile.TemporaryDirectory() as td:
        # 一時コピーに補助原点（基板の左下）を置く
        board = pcbnew.LoadBoard(PCB)
        board.GetDesignSettings().SetAuxOrigin(pcbnew.VECTOR2I_MM(OX, OY + BH))
        # 組立図用：表題欄を埋める（用紙は保存後に A3 へ書き換える。PAGE_INFO は Python から変えられない）
        tb = board.GetTitleBlock()
        tb.SetTitle("NFC Reader - Assembly Drawing (TOP)")
        tb.SetRevision("0.2")
        tb.SetDate(datetime.date.today().isoformat())
        tb.SetComment(0, "Single-sided assembly (TOP only). Crossed-out parts are DNP (not assembled).")
        tb.SetComment(1, "JP1/JP2 are copper solder jumpers (no part). Values are listed in the BOM.")
        board.SetTitleBlock(tb)
        tmp = os.path.join(td, "nfc_reader.kicad_pcb")
        pcbnew.SaveBoard(tmp, board)
        with open(tmp, encoding="utf8") as f:
            text = f.read()
        if '(paper "A4")' not in text:
            raise SystemExit("用紙設定 (paper \"A4\") が見つからない")
        with open(tmp, "w", encoding="utf8") as f:
            f.write(text.replace('(paper "A4")', '(paper "A3")', 1))
        for ext in ("kicad_pro",):
            src = os.path.join(HERE, "kicad", "nfc_reader." + ext)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(td, "nfc_reader." + ext))

        gdir = os.path.join(td, "gerber")
        os.makedirs(gdir)
        cli("pcb", "export", "gerbers", "-l", ",".join(LAYERS), "--use-drill-file-origin", "--no-x2",
            "--subtract-soldermask", "-o", gdir + os.sep, tmp)
        cli("pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--drill-origin", "plot",
            "--excellon-zeros-format", "decimal", "-o", gdir + os.sep, tmp)
        # Fusion の案内どおりの拡張子に揃える
        zpath = os.path.join(OUT, "nfc_reader_gerber.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for n in sorted(os.listdir(gdir)):
                src = os.path.join(gdir, n)
                base, ext = os.path.splitext(n)
                if ext.lower() == ".drl":
                    arc = "nfc_reader.TXT"
                elif ext.lower() == ".gbrjob":
                    continue
                else:
                    layer = next((ly for ly in LAYERS if base.endswith("-" + ly.replace(".", "_"))), None)
                    if layer is None:
                        raise SystemExit(f"層の分からないガーバー: {n}")
                    arc = f"nfc_reader.{LAYERS[layer]}"
                z.write(src, arc)
            names = z.namelist()

        # 組立図（表面だけ。部品は片面実装）：組立図層(F.Fab)＋占有範囲(F.CrtYd)＋外形を 1 ページの PDF に
        #   パッドの輪郭も描き（向きが分かるように）、未実装（DNP）の部品には×を付ける。
        #   値は BOM にあるので省き（部品番号の重なりを減らす）、A3 に 3 倍で描く
        cli("pcb", "export", "pdf", "-l", "F.Fab,F.Courtyard,Edge.Cuts", "--mode-single", "--black-and-white",
            "--include-border-title", "--sketch-pads-on-fab-layers", "--crossout-DNP-footprints-on-fab-layers",
            "--exclude-value", "--scale", "3", "-o", os.path.join(OUT, "nfc_reader_assembly_top.pdf"), tmp)

    nbom = write_bom(parts, os.path.join(OUT, "nfc_reader_bom.csv"))
    write_cpl(board, [p.ref for p in parts], os.path.join(OUT, "nfc_reader_cpl.csv"))
    print("ガーバー:", ", ".join(names))
    print(f"BOM: {nbom} 行（部品 {len(parts)} 個） / CPL: {len(parts)} 行")
    for n in sorted(os.listdir(OUT)):
        print(f"出力: fab/{n}（{os.path.getsize(os.path.join(OUT, n)) // 1024} KB）")


if __name__ == "__main__":
    main()
