# 作成日: 2026-11-16
# 目的: ケースの STL を読んで確認用の画像（本体・蓋の裏・組み合わせ・中身の目安入り）を描く
#
# 使い方（FreeCAD 付属の Python で実行。VTK が入っている）:
#   & "$env:LOCALAPPDATA\Programs\FreeCAD 1.1\bin\python.exe" case\render_case.py
#   （FreeCAD 1.0 を全員向けに入れた PC では "C:\Program Files\FreeCAD 1.0\bin\python.exe"）
# 出力: case/preview_case.png

import os

import vtkmodules.vtkInteractionStyle  # noqa: F401
import vtkmodules.vtkRenderingFreeType  # noqa: F401  文字を描くのに要る
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
from vtkmodules.vtkFiltersSources import vtkCubeSource, vtkCylinderSource
from vtkmodules.vtkIOGeometry import vtkSTLReader
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkRenderingCore import (vtkActor, vtkPolyDataMapper, vtkRenderer, vtkRenderWindow,
                                         vtkWindowToImageFilter, vtkTextActor)

HERE = os.path.dirname(os.path.abspath(__file__))


# STL を色付きの部品にする（dz で上下にずらす）
def actor_stl(name, rgb, dz=0.0, opacity=1.0):
    r = vtkSTLReader()
    r.SetFileName(os.path.join(HERE, name))
    m = vtkPolyDataMapper()
    m.SetInputConnection(r.GetOutputPort())
    a = vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*rgb)
    a.GetProperty().SetOpacity(opacity)
    a.SetPosition(0, 0, dz)
    return a


# 箱（中身の目安）
def actor_box(x0, y0, z0, w, d, h, rgb):
    c = vtkCubeSource()
    c.SetBounds(x0, x0 + w, y0, y0 + d, z0, z0 + h)
    m = vtkPolyDataMapper()
    m.SetInputConnection(c.GetOutputPort())
    a = vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*rgb)
    return a


# 円柱（中身の目安。底の中心 (cx, cy, z0) から上へ高さ h）
def actor_cyl(cx, cy, z0, d, h, rgb):
    c = vtkCylinderSource()
    c.SetRadius(d / 2)
    c.SetHeight(h)
    c.SetResolution(48)
    m = vtkPolyDataMapper()
    m.SetInputConnection(c.GetOutputPort())
    a = vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*rgb)
    a.RotateX(90)                 # vtkCylinderSource は Y 軸向きなので Z 軸向きに立てる
    a.SetPosition(cx, cy, z0 + h / 2)
    return a


def view(win, vp, actors, cam_pos, title, focal=(51, 28, 9), up=(0, 0, 1)):
    ren = vtkRenderer()
    ren.SetViewport(*vp)
    ren.SetBackground(0.97, 0.97, 0.97)
    for a in actors:
        ren.AddActor(a)
    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(*focal)
    cam.SetPosition(*cam_pos)
    cam.SetViewUp(*up)
    ren.ResetCamera()
    cam.Zoom(1.05)
    t = vtkTextActor()
    t.SetInput(title)
    t.GetTextProperty().SetFontSize(18)
    t.GetTextProperty().SetColor(0.1, 0.1, 0.1)
    t.SetPosition(10, 10)
    ren.AddActor2D(t)
    win.AddRenderer(ren)


if __name__ == "__main__":
    # gen_case.py は FreeCAD（freecadcmd）でしか import できないので、中身の目安の位置は gen_case.py の計算結果を書き写している
    blue, orange = (0.29, 0.56, 0.85), (0.88, 0.63, 0.19)
    black = (0.15, 0.15, 0.15)
    win = vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(1800, 600)
    # 中身の目安（gen_case.py の最後に「[render]」で表示される値。PN532 は赤い基板、XIAO は黒い基板、ブザーは灰色）
    pn = actor_box(7.0, 7.0, 12.3, 40.0, 43.0, 1.6, (0.8, 0.15, 0.15))
    xi = actor_box(79.5, 19.6, 1.6, 21.0, 17.8, 1.0, black)
    usb = actor_box(79.5 + 21.0 - 7.5 + 0.8, 19.6 + (17.8 - 8.9) / 2, 2.6, 7.5, 8.9, 3.2, (0.75, 0.75, 0.75))
    bz_body = actor_cyl(62.5, 28.5, 1.6, 23.0, 15.0, (0.45, 0.45, 0.45))
    bz_ears = actor_box(62.5 - 3.5, 28.5 - 18.0, 1.6, 7.0, 36.0, 2.5, (0.45, 0.45, 0.45))   # 耳は縦向き
    view(win, (0, 0, 1 / 3, 1), [actor_stl("nfc_case_base.stl", blue), pn, xi, usb, bz_body, bz_ears],
         (-40, -80, 100), "base + parts (red: PN532, black: XIAO, gray: buzzer)")
    view(win, (1 / 3, 0, 2 / 3, 1), [actor_stl("nfc_case_lid.stl", orange)],
         (-40, -80, -70), "lid underside (lip, XIAO press post, sound holes)")
    view(win, (2 / 3, 0, 1, 1), [actor_stl("nfc_case_base.stl", blue), actor_stl("nfc_case_lid.stl", orange)],
         (140, -70, 90), "assembled (USB-C on the right, tap ring and sound holes on top)")
    win.Render()
    w2i = vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    out = os.path.join(HERE, "preview_case.png")
    wr = vtkPNGWriter()
    wr.SetFileName(out)
    wr.SetInputConnection(w2i.GetOutputPort())
    wr.Write()
    print("出力:", out)
