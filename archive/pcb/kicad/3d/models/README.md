# 3D モデルの出典

`export_3d.py` が、KiCad 標準ライブラリに 3D モデルが無い部品の代わりに使うモデル。

| ファイル | 出典 | ライセンス |
|---|---|---|
| `ESP32-S3-MINI-1.STEP` | Espressif Systems「[espressif/kicad-libraries](https://github.com/espressif/kicad-libraries)」の `3dmodels/espressif.3dshapes/ESP32-S3-MINI-1.STEP`（コミット `21b5927`、2026-11-16 取得。無改変） | [CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/legalcode)。このモデルを使って作った設計・生成ファイルには条件がかからない、という例外付き（[LICENSE.md](https://github.com/espressif/kicad-libraries/blob/main/LICENSE.md)） |
| `CMT-8504-100-SMT_box.step` | `export_3d.py` が生成した外形寸法だけの箱（8.5×8.5×約4mm）。下のブザー公式モデルが無いときに使う | このリポジトリと同じ |

## ブザー（CMT-8504-100-SMT-TR）の公式モデル（リポジトリには入れていない）

メーカー Same Sky（旧 CUI Devices）の規約（[CAD Model Terms](https://www.sameskydevices.com/cad-model-terms)）では、データは Same Sky の財産とされ、再配布の許可が明記されていない。そのためファイルは `.gitignore` で除外している。使うときは各自で取得して、このフォルダに置く。

1. [CMT-8504-100-SMT-TR の 3D Model ページ](https://www.sameskydevices.com/product/resource/3dmodel/cmt-8504-100-smt-tr) を開く
2. 形式に「STEP AP214 (.step)」を選び、規約に同意して Download
3. zip の中の `Same_Sky_CMT-8504-100-SMT-TR.step` をこのフォルダに置き、`export_3d.py` を実行する
