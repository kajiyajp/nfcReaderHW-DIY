# 作成日: 2026-11-15
# 目的: 生成済み基板を Freerouting で自動配線し、GNDベタを張って保存する
#
# 使い方（KiCad付属のPythonで実行）:
#   & "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" route.py [--passes 30]
# 流れ: 既存の配線とベタを消す → DSN書き出し → freerouting-cli → SES読み込み → GNDベタ(両面) → 塗りつぶし → 保存

import argparse
import os
import subprocess

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "kicad", "nfc_reader.kicad_pcb")
DSN = os.path.join(HERE, "kicad", "nfc_reader.dsn")
SES = os.path.join(HERE, "kicad", "nfc_reader.ses")
TOOLS = os.path.join(os.environ["LOCALAPPDATA"], "freerouting-cli")
JAVA = os.path.join(TOOLS, "jre", "jdk-25.0.5+8-jre", "bin", "java.exe")   # 持ち運び版JRE 25（jarがJava25向けビルドのため。システム未登録）
JAR = os.path.join(TOOLS, "app", "freerouting-2.5.0.jar")
# FIXME: freerouting-cli.exe（ネイティブ版 v2.5.0）は配線開始直後に UnsupportedFeatureError で停止するため jar 版を使う


# 既存の配線・ビア・ベタ（部品内のキープアウトは除く）を消す
def clear_routing(board):
    for t in list(board.GetTracks()):
        if not t.IsLocked():          # gen_pcb.py が引いた固定配線（コイルの橋）は残す
            board.Delete(t)
    for z in list(board.Zones()):
        board.Delete(z)


# 片側の層にしか配線がつながっていないビアを消す（GNDはベタで生きるので残す）。消した数を返す
def remove_dangling_vias(board):
    segs = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    n = 0
    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
        if v.GetNetname() == "/GND" or v.IsLocked():
            continue
        p = v.GetPosition()
        r2 = (v.GetWidth(pcbnew.F_Cu) // 2) ** 2
        layers = {t.GetLayer() for t in segs if t.GetNetCode() == v.GetNetCode()
                  and any((q.x - p.x) ** 2 + (q.y - p.y) ** 2 <= r2 for q in (t.GetStart(), t.GetEnd()))}
        if len(layers) < 2:
            board.Delete(v)               # Remove()だと後でクラッシュするためDelete()
            n += 1
    return n


# 基板外形いっぱいのGNDベタを1層ぶん追加する
def add_gnd_zone(board, layer):
    # 外形は gen_pcb.py と同じ定数から作る（SWIGの型変換が不安定なため境界箱APIは使わない）
    l, t, r, b = (pcbnew.FromMM(v) for v in (100.0, 100.0, 200.0, 160.0))
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet("/GND"))
    z.SetLocalClearance(pcbnew.FromMM(0.3))
    z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(pcbnew.FromMM(0.3))
    z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.4))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)   # 孤立した銅は残さない
    # ゾーン自身の外形に直接書く（別に作った多角形を SetOutline で渡すと、Python側の解放でクラッシュする）
    o = z.Outline()
    o.NewOutline()
    for x, y in ((l, t), (r, t), (r, b), (l, b)):
        o.Append(x, y)
    board.Add(z)


# 自動配線からベタ塗りまでを実行する
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--passes", type=int, default=30)
    args = ap.parse_args()

    board = pcbnew.LoadBoard(PCB)
    clear_routing(board)
    if not pcbnew.ExportSpecctraDSN(board, DSN):
        raise SystemExit("DSN の書き出しに失敗")
    if os.path.exists(SES):
        os.remove(SES)
    log = os.path.join(HERE, "kicad", "freerouting_run.log")
    with open(log, "w", encoding="utf8") as lf:
        subprocess.run([JAVA, "-Djava.awt.headless=true", "-jar", JAR, "--gui.enabled=false",
                        "-de", DSN, "-do", SES, "-mp", str(args.passes)],
                       check=True, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
                       cwd=os.path.join(HERE, "kicad"), timeout=1800)
    if not os.path.exists(SES):
        raise SystemExit(f"SES が出力されなかった。ログ: {log}")
    if not pcbnew.ImportSpecctraSES(board, SES):
        raise SystemExit("SES の読み込みに失敗")

    removed = remove_dangling_vias(board)
    add_gnd_zone(board, pcbnew.F_Cu)
    add_gnd_zone(board, pcbnew.B_Cu)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print(f"未接続ビアを {removed} 個削除")
    pcbnew.SaveBoard(PCB, board)
    print(f"保存: {PCB}（配線 {len(board.GetTracks())} 本）")


if __name__ == "__main__":
    main()
