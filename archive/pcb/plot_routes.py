# 作成日: 2026-11-15
# 目的: 配線確認用の図を描く（ベタを除き、F.Cu=赤 / B.Cu=青 / ビア=黄 / パッド=灰 / RF系ネット=太線強調）
#
# 使い方（KiCad付属のPythonで実行）:
#   & "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" plot_routes.py [出力.png] [x0 y0 x1 y1(基板相対mm)]

import os
import sys

import pcbnew
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "kicad", "nfc_reader.kicad_pcb")
sys.path.insert(0, HERE)
from gen_pcb import OX, OY, BW, BH  # noqa: E402  基板の原点とサイズは gen_pcb.py に合わせる
RF = ("/TX1", "/TX2", "/TXF1", "/TXF2", "/ANTM1", "/ANTM2", "/ANT1", "/ANT2")


# 基板を読み込んで図を描く
def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "routes.png")
    x0, y0, x1, y1 = (float(v) for v in sys.argv[2:6]) if len(sys.argv) >= 6 else (0, 0, BW, BH)
    s = 1600 / (x1 - x0)                       # px/mm
    img = Image.new("RGB", (int((x1 - x0) * s), int((y1 - y0) * s)), (20, 20, 20))
    d = ImageDraw.Draw(img)
    b = pcbnew.LoadBoard(PCB)

    # mm(内部単位) → 画像座標
    def P(v):
        return ((v.x / 1e6 - OX - x0) * s, (v.y / 1e6 - OY - y0) * s)

    for fp in b.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            a, c = P(bb.GetOrigin()), P(bb.GetEnd())
            d.rectangle([a, c], fill=(90, 90, 90))
        r = P(fp.GetPosition())
        d.text((r[0] + 3, r[1] - 12), fp.GetReference(), fill=(230, 230, 230))
    for layer, col in ((pcbnew.B_Cu, (60, 120, 255)), (pcbnew.F_Cu, (255, 70, 70))):
        for t in b.GetTracks():
            if t.GetClass() == "PCB_TRACK" and t.GetLayer() == layer:
                w = max(1, int(t.GetWidth() / 1e6 * s))
                c = (255, 200, 0) if False else col
                if t.GetNetname() in RF:
                    c = tuple(min(255, v + 60) for v in col)
                    w += 2
                d.line([P(t.GetStart()), P(t.GetEnd())], fill=c, width=w)
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            q = P(t.GetPosition())
            r = 0.3 * s
            d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=(240, 220, 0))
    img.save(out)
    print("出力:", out)


if __name__ == "__main__":
    main()
