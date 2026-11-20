# 作成日: 2026-11-15
# 目的: PN532用 基板パターンアンテナ（13.56MHz）のインダクタンス・Q・整合回路定数を計算する
#
# 使い方:  python antenna_calc.py
#   パラメータは下の「設定」ブロックを書き換える。外部ライブラリ不要（標準ライブラリのみ）。
#
# 回路モデル（差動回路の片側＝半回路で計算）:
#   TX1 ──L0──┬──C1──┬── Rq/2 ── La/2 ── (仮想GND)
#             C0     C2
#            GND    GND
#   L0/C0 : EMCフィルタ（ローパス）
#   C1/C2 : 直列/並列の整合コンデンサ
#   Rq    : Q調整用ダンピング抵抗（左右合計）
#
# FIXME: 計算値は出発点。実基板ではVNA(ベクトルネットワークアナライザ)等で測って C1/C2 を追い込むこと。

import cmath
import math

# ===== 設定 =====
F = 13.56e6              # 動作周波数 [Hz]
A0 = 45e-3               # アンテナ外形 横 [m]
B0 = 35e-3               # アンテナ外形 縦 [m]
N = 4                    # 巻数
W = 0.6e-3               # 線幅 [m]
G = 0.6e-3               # 線間 [m]
T = 35e-6                # 銅厚 [m]（1oz）
L0 = 560e-9              # EMCフィルタ インダクタ [H]（PN532データシート Fig.51）
C0 = 220e-12             # EMCフィルタ コンデンサ [F]（同上。fc ≈ 14.5MHz）
Q_TARGET = 30            # 目標Q（106kbps通信なら30前後が目安）
R_MATCH = 25.0           # TX片側から見た目標インピーダンス [Ω]（TODO: PN532の推奨範囲と照合）
E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]

MU0 = 4e-7 * math.pi
RHO_CU = 1.72e-8


# 矩形スパイラルのインダクタンス（NXP AN流の近似式）を返す
def loop_inductance(a0, b0, n, w, g, t):
    a = a0 - n * (g + w)          # 平均横寸法
    b = b0 - n * (g + w)          # 平均縦寸法
    d = 2 * (t + w) / math.pi     # 等価導体径
    diag = math.hypot(a, b)
    x1 = a * math.log(2 * a * b / (d * (a + diag)))
    x2 = b * math.log(2 * a * b / (d * (b + diag)))
    x3 = 2 * (a + b - diag)
    x4 = (a + b) / 4
    return MU0 / math.pi * (x1 + x2 - x3 + x4) * n ** 1.8, a, b


# 表皮効果込みの導体AC抵抗を返す
def loop_resistance(a, b, n, w, t, f):
    length = 2 * (a + b) * n
    delta = math.sqrt(RHO_CU / (math.pi * f * MU0))   # 表皮深さ
    t_eff = min(t, delta)
    return RHO_CU * length / (w * t_eff)


# 値を最も近いE12系列に丸めて返す
def nearest_e12(x):
    exp = math.floor(math.log10(x))
    cands = [m * 10 ** e for e in (exp - 1, exp, exp + 1) for m in E12]
    return min(cands, key=lambda c: abs(c - x))


# 半回路の入力インピーダンスを返す
def z_in(c1, c2, c0, la, r_tot, w):
    z_ant = r_tot / 2 + 1j * w * la / 2
    z_b = 1 / (1 / z_ant + 1j * w * c2)          # C2 並列
    z_a1 = z_b + 1 / (1j * w * c1)               # C1 直列
    z_a = 1 / (1 / z_a1 + 1j * w * c0)           # C0 並列
    return z_a + 1j * w * L0                     # L0 直列


# Z_in = target + j0 となる C1, C2 を出力側から逆算する（閉形式）。解なしなら ValueError
def solve_match(c0, la, r_tot, w, target):
    # TX側から L0, C0 を剥がして、C1 の手前で必要なインピーダンス Z_A1 を求める
    z_a = target - 1j * w * L0
    z_a1 = 1 / (1 / z_a - 1j * w * c0)
    r1 = z_a1.real
    # アンテナ側のアドミタンス G + jBa に C2 (jB) を足して、実部が r1 になる B を求める
    y_ant = 1 / (r_tot / 2 + 1j * w * la / 2)
    g, ba = y_ant.real, y_ant.imag
    disc = g / r1 - g * g
    if r1 <= 0 or disc < 0:
        raise ValueError("この条件では整合できない（R_MATCH か C0 を見直す）")
    for sign in (1, -1):
        b = -ba + sign * math.sqrt(disc)
        if b <= 0:
            continue
        z_b = 1 / (y_ant + 1j * b)
        x_c1 = z_b.imag - z_a1.imag              # C1 のリアクタンス 1/(wC1)
        if x_c1 > 0:
            return 1 / (w * x_c1), b / w
    raise ValueError("正の C1/C2 の解がない（巻数や寸法を見直す）")


# 計算結果を表示する
def main():
    w = 2 * math.pi * F
    la, a, b = loop_inductance(A0, B0, N, W, G, T)
    ra = loop_resistance(a, b, N, W, T, F)
    q_raw = w * la / ra
    r_tot = w * la / Q_TARGET                 # 目標Qに必要な総直列抵抗
    rq = max(r_tot - ra, 0)
    c0 = C0
    fc = 1 / (2 * math.pi * math.sqrt(L0 * C0))
    c1, c2 = solve_match(c0, la, r_tot, w, R_MATCH)

    print("=== アンテナ ===")
    print(f"外形 {A0*1e3:.0f}x{B0*1e3:.0f}mm, {N}巻, 線幅/線間 {W*1e3:.2f}/{G*1e3:.2f}mm")
    print(f"La = {la*1e6:.3f} uH   Ra(AC) = {ra:.2f} ohm   素のQ = {q_raw:.0f}")
    print(f"目標Q={Q_TARGET} → ダンピング抵抗 合計 {rq:.2f} ohm（片側 {rq/2:.2f} ohm → E12: {nearest_e12(rq/2):.2g} ohm）")
    print("\n=== EMCフィルタ ===")
    print(f"L0 = {L0*1e9:.0f} nH, C0 = {c0*1e12:.0f} pF, fc = {fc/1e6:.1f} MHz")
    print("\n=== 整合（片側, 各2個ずつ実装） ===")
    print(f"C1 = {c1*1e12:.1f} pF（E12: {nearest_e12(c1)*1e12:.0f} pF）")
    print(f"C2 = {c2*1e12:.1f} pF（E12: {nearest_e12(c2)*1e12:.0f} pF）")
    zchk = z_in(c1, c2, c0, la, r_tot, w)
    print(f"検算 Z_in = {zchk.real:.2f} {zchk.imag:+.2f}j ohm（目標 {R_MATCH} ohm）")
    print("\n※ C1/C2 は並列2パッド構成にして、実測で値を足し引きできるようにする")


if __name__ == "__main__":
    main()
