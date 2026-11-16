# 3D モデルの出典

`export_3d.py` が、KiCad 標準ライブラリに 3D モデルが無い部品の代わりに使うモデル。

| ファイル | 出典 | ライセンス |
|---|---|---|
| `ESP32-S3-MINI-1.STEP` | Espressif Systems「[espressif/kicad-libraries](https://github.com/espressif/kicad-libraries)」の `3dmodels/espressif.3dshapes/ESP32-S3-MINI-1.STEP`（コミット `21b5927`、2026-11-16 取得。無改変） | [CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/legalcode)。このモデルを使って作った設計・生成ファイルには条件がかからない、という例外付き（[LICENSE.md](https://github.com/espressif/kicad-libraries/blob/main/LICENSE.md)） |
| `CMT-8504-100-SMT_box.step` | `export_3d.py` が生成した外形寸法だけの箱（8.5×8.5×約4mm） | このリポジトリと同じ |
