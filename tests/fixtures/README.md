# テストフィクスチャ

## gotemba-area.osm.pbf

御殿場IC周辺のOSMデータを切り出したPBFファイル。

### 切り出し情報

- **Bbox**: `138.92,35.28,138.96,35.31` (約4km x 3km)
- **抽出日**: 2026-02-07
- **抽出元**: japan-latest.osm.pbf

### 含まれるデータ

- 東名高速道路 (Tomei Expressway)
- 国道246号 (National Route 246)

### 切り出しコマンド

```bash
osmium extract --bbox 138.92,35.28,138.96,35.31 \
    cache/japan-latest.osm.pbf \
    -o tests/fixtures/gotemba-area.osm.pbf
```

### ライセンス

OpenStreetMap contributors, ODbL
