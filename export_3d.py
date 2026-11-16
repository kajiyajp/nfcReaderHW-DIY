# 作成日: 2026-11-16
# 目的: 基板を3Dデータ（STEP / GLB）と3D画像（PNG）に書き出す
#
# 使い方（KiCad付属のPythonで実行）:
#   & "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" export_3d.py
# 出力: kicad/3d/nfc_reader.step（機構CAD向け）, nfc_reader.glb（ビューア向け）, render_*.png
#
# KiCad 10 の標準ライブラリに 3D モデルが無い部品は、外形寸法だけ合わせた代わりの箱（または同寸の別モデル）を使う。
# 元の基板ファイルは書き換えず、モデルの差し替えは一時コピーにだけ行う。

import os
import subprocess
import tempfile

import pcbnew

from kicad_lib import KICAD_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "kicad", "nfc_reader.kicad_pcb")
OUT = os.path.join(HERE, "kicad", "3d")
MODELS = os.path.join(OUT, "models")
CLI = os.path.join(KICAD_DIR, "bin", "kicad-cli.exe")

# 代わりの箱: 参照記号 → (ファイル名, x範囲, y範囲(3D座標=上が+), 高さ, 色RGB)。寸法はデータシート（概略）に合わせる
BOXES = {
    "U2": ("ESP32-S3-MINI-1_box.step", (-7.7, 7.7), (-10.25, 10.25 - 0.5), 2.4, (0.62, 0.64, 0.66)),   # 15.4×20.5×2.4mm
    "BZ1": ("CMT-8504-100-SMT_box.step", (-4.25, 4.25), (-4.25, 4.25), 4.0, (0.10, 0.10, 0.10)),     # 8.5×8.5×約4mm
}
# 同じ外形の別モデルに差し替える部品（PN532 の HVQFN40 6×6 は放熱パッドの大きさだけ違う QFN-40 で代用）
SUBST = {
    "U1": "${KICAD10_3DMODEL_DIR}/Package_DFN_QFN.3dshapes/QFN-40-1EP_6x6mm_P0.5mm_EP4.6x4.6mm.step",
}


# 直方体1個の STEP（AP214）を書く
def write_box_step(path, xr, yr, h, rgb):
    ents = []

    def e(s):
        ents.append(s)
        return "#%d" % len(ents)

    def f(v):
        return "%.4f" % v

    def pt(p):
        return e("CARTESIAN_POINT('',(%s,%s,%s))" % (f(p[0]), f(p[1]), f(p[2])))

    def dr(d):
        return e("DIRECTION('',(%s,%s,%s))" % (f(d[0]), f(d[1]), f(d[2])))

    vx = [(xr[i & 1], yr[(i >> 1) & 1], (0.0, h)[(i >> 2) & 1]) for i in range(8)]
    verts = [e("VERTEX_POINT('',%s)" % pt(p)) for p in vx]
    edges = {}

    # 頂点a→bの辺（向きを含めて返す）
    def edge(a, b):
        if (b, a) in edges:
            return edges[(b, a)], ".F."
        if (a, b) not in edges:
            d = [vx[b][k] - vx[a][k] for k in range(3)]
            n = sum(c * c for c in d) ** 0.5
            ln = e("LINE('',%s,%s)" % (pt(vx[a]), e("VECTOR('',%s,1.)" % dr([c / n for c in d]))))
            edges[(a, b)] = e("EDGE_CURVE('',%s,%s,%s,.T.)" % (verts[a], verts[b], ln))
        return edges[(a, b)], ".T."

    # 面: 頂点4つと外向き法線
    quads = [((0, 1, 3, 2), (0, 0, -1)), ((4, 6, 7, 5), (0, 0, 1)), ((0, 4, 5, 1), (0, -1, 0)),
             ((2, 3, 7, 6), (0, 1, 0)), ((0, 2, 6, 4), (-1, 0, 0)), ((1, 5, 7, 3), (1, 0, 0))]
    faces = []
    for q, nrm in quads:
        a, b, c = (vx[i] for i in q[:3])
        u = [b[k] - a[k] for k in range(3)]
        w = [c[k] - b[k] for k in range(3)]
        cr = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        if sum(cr[k] * nrm[k] for k in range(3)) < 0:
            q = q[::-1]
        oes = []
        for i in range(4):
            ec, o = edge(q[i], q[(i + 1) % 4])
            oes.append(e("ORIENTED_EDGE('',*,*,%s,%s)" % (ec, o)))
        bound = e("FACE_OUTER_BOUND('',%s,.T.)" % e("EDGE_LOOP('',(%s))" % ",".join(oes)))
        ref = (1, 0, 0) if nrm[0] == 0 else (0, 1, 0)
        ax = e("AXIS2_PLACEMENT_3D('',%s,%s,%s)" % (pt(vx[q[0]]), dr(nrm), dr(ref)))
        faces.append(e("ADVANCED_FACE('',(%s),%s,.T.)" % (bound, e("PLANE('',%s)" % ax))))
    shell = e("CLOSED_SHELL('',(%s))" % ",".join(faces))
    solid = e("MANIFOLD_SOLID_BREP('box',%s)" % shell)
    origin = e("AXIS2_PLACEMENT_3D('',%s,%s,%s)" % (pt((0, 0, 0)), dr((0, 0, 1)), dr((1, 0, 0))))
    lu = e("( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) )")
    au = e("( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )")
    su = e("( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )")
    unc = e("UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),%s,'distance_accuracy_value','')" % lu)
    ctx = e("( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((%s)) "
            "GLOBAL_UNIT_ASSIGNED_CONTEXT((%s,%s,%s)) REPRESENTATION_CONTEXT('',''))" % (unc, lu, au, su))
    rep = e("ADVANCED_BREP_SHAPE_REPRESENTATION('',(%s,%s),%s)" % (origin, solid, ctx))
    actx = e("APPLICATION_CONTEXT('automotive design')")
    e("APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,%s)" % actx)
    prod = e("PRODUCT('box','box','',(%s))" % e("PRODUCT_CONTEXT('',%s,'mechanical')" % actx))
    pdf = e("PRODUCT_DEFINITION_FORMATION('','',%s)" % prod)
    pd = e("PRODUCT_DEFINITION('design','',%s,%s)" % (pdf, e("PRODUCT_DEFINITION_CONTEXT('part definition',%s,'design')" % actx)))
    e("SHAPE_DEFINITION_REPRESENTATION(%s,%s)" % (e("PRODUCT_DEFINITION_SHAPE('','',%s)" % pd), rep))
    # 色
    col = e("COLOUR_RGB('',%s,%s,%s)" % tuple(f(v) for v in rgb))
    fill = e("FILL_AREA_STYLE('',(%s))" % e("FILL_AREA_STYLE_COLOUR('',%s)" % col))
    side = e("SURFACE_SIDE_STYLE('',(%s))" % e("SURFACE_STYLE_FILL_AREA(%s)" % fill))
    psa = e("PRESENTATION_STYLE_ASSIGNMENT((%s))" % e("SURFACE_STYLE_USAGE(.BOTH.,%s)" % side))
    sty = e("STYLED_ITEM('color',(%s),%s)" % (psa, solid))
    e("MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',(%s),%s)" % (sty, ctx))

    lines = ["ISO-10303-21;", "HEADER;", "FILE_DESCRIPTION(('placeholder box'),'2;1');",
             "FILE_NAME('%s','2026-11-16T00:00:00',(''),(''),'export_3d.py','','');" % os.path.basename(path),
             "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));", "ENDSEC;", "DATA;"]
    lines += ["#%d=%s;" % (i, s) for i, s in enumerate(ents, 1)]
    lines += ["ENDSEC;", "END-ISO-10303-21;", ""]
    with open(path, "w", encoding="ascii") as fh:
        fh.write("\n".join(lines))


# 一時コピーの基板で 3D モデルを差し替える
def prepare_board(tmp_pcb):
    board = pcbnew.LoadBoard(PCB)
    for ref, path in [(r, os.path.join(MODELS, b[0]).replace("\\", "/")) for r, b in BOXES.items()] + list(SUBST.items()):
        fp = board.FindFootprintByReference(ref)
        models = fp.Models()
        m = models[0] if len(models) else pcbnew.FP_3DMODEL()
        m.m_Filename = path
        if not len(models):
            models.push_back(m)
    pcbnew.SaveBoard(tmp_pcb, board)


# kicad-cli を実行する
def cli(*args):
    r = subprocess.run([CLI, *args], capture_output=True, text=True, encoding="utf8", errors="replace")
    msg = (r.stdout + r.stderr).strip().splitlines()
    for line in msg:
        if "Could not" in line or "not found" in line or "rror" in line:
            print("  ", line)
    if r.returncode:
        raise SystemExit(f"kicad-cli 失敗: {' '.join(args[:3])}")


# 3Dデータと画像を書き出す
def main():
    os.makedirs(MODELS, exist_ok=True)
    for name, xr, yr, h, rgb in BOXES.values():
        write_box_step(os.path.join(MODELS, name), xr, yr, h, rgb)
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "nfc_reader.kicad_pcb")
        prepare_board(tmp)
        common = ["--subst-models", "--include-tracks", "--include-zones", "--include-silkscreen", "--include-soldermask", "-f"]
        cli("pcb", "export", "step", *common, "-o", os.path.join(OUT, "nfc_reader.step"), tmp)
        cli("pcb", "export", "glb", *common, "-o", os.path.join(OUT, "nfc_reader.glb"), tmp)
        for side, extra in (("top", ["--side", "top"]), ("bottom", ["--side", "bottom"]),
                            ("iso", ["--side", "top", "--rotate", "-40,0,-25"])):
            cli("pcb", "render", *extra, "--quality", "high", "--width", "1600", "--height", "1000",
                "--background", "opaque", "-o", os.path.join(OUT, f"render_{side}.png"), tmp)
    for n in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, n)
        if os.path.isfile(p):
            print(f"出力: kicad/3d/{n}（{os.path.getsize(p) // 1024} KB）")


if __name__ == "__main__":
    main()
