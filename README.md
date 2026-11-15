# NFCリーダー基板（PN532 + ESP32-C3）

> 作成：2026-11-15 ／ 目的：NTAG215タグを読み書きする自作NFCリーダー基板の設計資料

## 1. 何を作るか

- NTAG215（ISO14443A / NFC Forum Type 2、504バイト）のシールタグを **かざすと読み取り、Wi-Fi/BLEで何かを動かす** 単体リーダー
- 基板上にアンテナを持つ1枚完結型。USB-Cで給電・書き込み
- 設計：KiCad 10 ／ 製造・実装：FusionPCB（Seeed Fusion）のPCBA

### 非ゴール
- 長距離読み取り（目標は 3〜5cm。これ以上を狙うとアンテナと電源の作り込みが大きくなる）
- 電池駆動（今回はUSB給電のみ。将来の拡張候補）

## 2. 構成（ブロック図）

```
USB-C ──┬─ ESD(USBLC6) ── D+/D- ──────────────┐
        └─ 5V ── LDO(AP2112K-3.3) ── 3.3V ─┐   │
                                          │   │
          ┌───────────────────────────────┴───┴──┐
          │ ESP32-C3-WROOM-02 (Wi-Fi/BLE,USB内蔵)│
          │  GPIO4=SDA GPIO5=SCL GPIO6=IRQ        │
          │  GPIO7=RSTPDN GPIO10=LED GPIO3=BUZ    │
          │  GPIO9=BOOTボタン  EN=リセットボタン      │
          └──────────────┬────────────────────────┘
                         │ I2C(4.7kプルアップ)
          ┌──────────────┴──────────┐   TX1/TX2   ┌──────────┐
          │ PN532 (HVQFN40)         ├─ EMC ─ 整合 ─┤ パターン  │
          │ I0=L, I1=H → I2Cモード   │   RX ← 分圧 ─┤ アンテナ  │
          │ 27.12MHz 水晶            │             └──────────┘
          └─────────────────────────┘
```

## 3. 回路の要点

| ブロック | 内容 | メモ |
|---|---|---|
| 電源 | USB-C 5V → AP2112K-3.3（600mA） | ESP32送信時ピーク約350mA＋PN532約150mA。入出力に10µF |
| USB | USB-C 受け（CC1/CC2に5.1kΩプルダウン）→ USBLC6-2SC6 → ESP32-C3の GPIO18/19 | C3はUSBシリアル内蔵なのでUSB-UART変換ICは不要 |
| PN532 電源 | VBAT・PVDD に3.3V。内蔵LDOの出力 DVDD(39) を AVDD(8)・TVDD(5) に配線 | デカップリング：VBAT/TVDD に 4.7µF+100nF、DVDD・AVDD・PVDD に各100nF（データシート Fig.19/51） |
| PN532 モード | **I0=GND、I1=3.3V → I2C**（Selif=10b、データシート Table 72）。アドレス 0x24 | IRQ(P70_IRQ, 25) と RSTPD_N(38) を ESP32 の GPIO へ。TESTEN(18) は GND |
| 未使用ピン | SVDD(37)・SIGOUT(35)・AUX1/2・P3x・RSTOUT_N は未接続、SIGIN(36) は GND、LOADMOD(2) は未接続 | |
| 水晶 | 27.12MHz、3225サイズ、CL=10pF（データシート Table 298）→ 負荷コンデンサ 15pF×2 | Fig.51 は 22pF。水晶のCLに合わせて決める |
| アンテナ整合 | 差動。EMCフィルタ L0/C0 → 直列C1 → 並列C2 → ダンピング抵抗Rq → コイル | 値は §4 |
| RX | フィルタ出力（L0とC1の間）→ R2 2.7kΩ → CRx 1nF → RX(10)、RX → R1 1kΩ → VMID(9)、VMID → Cvmid 100nF → GND | 値は Fig.51。つなぎ方は Fig.37/51 からの読み取りなので、実機で RX 波形を確認する |
| UI | LED（GPIO10）、電磁ブザー CUI CMT-8504（GPIO3→NPNトランジスタ駆動＋還流ダイオード） | |
| ボタン | EN（リセット）、GPIO9（BOOT） | GPIO8 は起動時にHigh固定（10kでプルアップ） |

## 4. アンテナ（`antenna_calc.py` の計算結果）

| 項目 | 値 |
|---|---|
| コイル | 外形 45×35mm、4巻、線幅/線間 0.6/0.6mm、1oz銅 |
| インダクタンス La | 約 1.34µH（素のQ ≈ 127） |
| ダンピング抵抗 Rq | 片側 1.5Ω（Q≈30 に落とす） |
| EMCフィルタ | L0 = 560nH、C0 = 220pF（fc ≈ 14.3MHz、データシート Fig.51 の値） |
| 整合 | C1 = 33pF、C2 = 180pF（片側。左右対称に2組ずつ。データシートの範囲 10〜300pF に入る） |

- 計算値はあくまで出発点。**C1/C2 は並列2パッド**にして、実測しながら値を足し引きできるようにする
- 実測には NanoVNA（約1万円の簡易ネットワークアナライザ）があると早い。ない場合は「読み取り距離が最大になる組み合わせ」を総当たりで探す
- 寸法を変えたら `python antenna_calc.py` を再実行して値を出し直す

## 5. 基板レイアウト方針

- **サイズ**：100×60mm（ESP32-C3-WROOM-02 のアンテナ禁止領域が大きく、85×55mm から拡大）、2層、1.6mm、1oz、表面処理はHASL(鉛フリー)
- **配置**：左側にNFCアンテナ、右側にESP32-C3モジュール（モジュールのアンテナは基板の外へはみ出す向き）
- **NFCコイルの内側と真下には銅箔を置かない**（GNDベタを抜く）。ベタがあると渦電流でインダクタンスもQも落ちる
- 整合部品は PN532 とコイルの間に **左右対称** に並べる
- ESP32 のアンテナの周りにも 15mm 程度は銅箔を置かない領域をとる
- 部品はすべて表面（片面実装）にする → PCBAが安くなる
- 四隅に M3 の取付穴

## 6. 製造（FusionPCB）

- 入稿するもの：ガーバー（RS-274X）＋ドリル（Excellon）を zip、BOM（Fusion のテンプレート、型番入り）、CPL（部品の座標・回転・面）
- KiCad の `.pos` 出力を Fusion の列名に合わせて直す。**回転角のずれ** はプレビューで必ず確認する
- PN532 と ESP32-C3-WROOM-02 は Fusion が型番で調達する。在庫・価格は見積もりの時点で確認する

## 7. ファームウェア（概要）

- Arduino-ESP32 + Adafruit_PN532（I2C）でUIDとNTAG215のページを読み書き
- 読み取り → ブザー音とLEDで知らせる → Wi-Fi経由でWebhook/MQTTを送信（送り先は後で決める）

## 8. ファイルと作り直し方

| ファイル | 内容 |
|---|---|
| `README.md` | 本書（設計資料） |
| `design.py` | **部品と接続の唯一の定義**。回路を変えるときはここを編集する |
| `antenna_calc.py` | アンテナ・整合回路の計算（寸法はここが基準） |
| `gen_coil.py` | コイルのフットプリントとライブラリ表を生成 |
| `gen_sch.py` | `design.py` から回路図を生成 |
| `gen_pcb.py` | 基板の外形・部品配置・設計ルール・固定配線（TX2・コイル橋）を生成 |
| `route.py` | Freerouting で自動配線し、両面にGNDベタを張る |
| `plot_routes.py` | 配線確認用の図（routes.png）を描く |
| `kicad_lib.py` | KiCadライブラリを読む補助モジュール |
| `kicad/` | KiCadプロジェクト（回路図、自作フットプリント、ERC結果、KiCad出力のBOM） |
| `bom.csv` | 初期の部品表下書き（最新は `kicad/bom_kicad.csv`） |
| `TODO.md` / `glossary.md` | 残作業 / 用語集 |

```powershell
python antenna_calc.py   # 定数の確認
python gen_coil.py       # コイル生成
python gen_sch.py        # 回路図生成
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" gen_pcb.py   # 基板生成（配線は消える）
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\python.exe" route.py --passes 100   # 自動配線＋GNDベタ
& "$env:LOCALAPPDATA\Programs\KiCad\10.0\bin\kicad-cli.exe" sch erc kicad\nfc_reader.kicad_sch   # 接続チェック
```

### 設計変更の記録
- ESP32-C3-MINI-1 → **ESP32-C3-WROOM-02**（KiCad標準ライブラリにシンボル・フットプリントがあり、自作ミスのリスクを避けるため）
- ブザー MLT-8530 → **CUI CMT-8504**（同じく標準フットプリントがあるため）
- PN532 の I2C 設定を **I0=L, I1=H** に訂正（データシート Table 72）
- EMCフィルタ C0 を 150pF → **220pF**（データシート Fig.51）。それに伴い整合 C1 は 27pF → **33pF**
