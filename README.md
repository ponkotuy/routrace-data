# routrace-data

[![Test](https://github.com/ponkotuy/routrace-data/actions/workflows/test.yml/badge.svg)](https://github.com/ponkotuy/routrace-data/actions/workflows/test.yml)
[![Deploy](https://github.com/ponkotuy/routrace-data/actions/workflows/deploy.yml/badge.svg)](https://github.com/ponkotuy/routrace-data/actions/workflows/deploy.yml)

routrace用の地図データ（高速道路・海岸線）を生成するスクリプト群。

OpenStreetMapのデータからGeoJSONを生成し、GitHub Pagesで配信します。

## 必要なもの

- [mise](https://mise.jdx.dev/)
- osmium-tool

```bash
# Arch Linux
sudo pacman -S osmium-tool

# Ubuntu / Debian
sudo apt install osmium-tool

# macOS
brew install osmium-tool
```

## セットアップ

```bash
git clone https://github.com/ponkotuy/routrace-data.git
cd routrace-data
mise install
uv sync
```

## 使い方

```bash
# 全データを生成
uv run poe generate

# 海岸線のみ生成
uv run poe coastline

# 高速道路のみ生成
uv run poe highways

# 特定の高速道路のみ生成
uv run python scripts/main.py --highway-name "東名" --verbose
```

## 出力

生成されたデータは `data/` ディレクトリに出力されます。

```
data/
├── metadata.json      # メタデータ
├── coastline.json     # 海岸線データ
└── highways/          # 高速道路データ
    ├── index.json     # 高速道路一覧
    └── *.json         # 各高速道路のGeoJSON
```

## ライセンス

生成されるデータは [OpenStreetMap](https://www.openstreetmap.org/) に基づいており、[ODbL](https://opendatacommons.org/licenses/odbl/) ライセンスの下で提供されます。

© OpenStreetMap contributors
