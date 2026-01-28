# routrace-data

[![Test](https://github.com/ponkotuy/routrace-data/actions/workflows/test.yml/badge.svg)](https://github.com/ponkotuy/routrace-data/actions/workflows/test.yml)
[![Deploy](https://github.com/ponkotuy/routrace-data/actions/workflows/deploy.yml/badge.svg)](https://github.com/ponkotuy/routrace-data/actions/workflows/deploy.yml)

routrace用の地図データ（高速道路・海岸線）を生成するスクリプト群。

OpenStreetMapのデータからGeoJSONを生成し、GitHub Pagesで配信します。

## 必要なもの

### Python依存関係

- Python 3.10以上
- uv（推奨）または pip

### システム依存関係

**osmium-tool** が必要です（PBFファイルの事前フィルタリングに使用）。

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
# リポジトリをクローン
git clone https://github.com/<username>/routrace-data.git
cd routrace-data

# 依存関係をインストール（uvを使用）
uv sync

# または pip を使用
pip install -e .
```

## 使い方

```bash
# 全データを生成
uv run poe generate

# 海岸線のみ生成
uv run poe coastline

# 高速道路のみ生成
uv run poe highways

# 直接実行する場合
uv run python scripts/main.py --verbose

# 特定の高速道路のみ生成
uv run python scripts/main.py --highway-id tomei --highway-id meishin
```

## 出力

生成されたデータは `data/` ディレクトリに出力されます。

```
data/
├── metadata.json      # メタデータ
├── coastline.json     # 海岸線データ
└── highways/          # 高速道路データ
    ├── index.json     # 高速道路一覧
    ├── tomei.json
    ├── meishin.json
    └── ...
```

## ライセンス

生成されるデータは [OpenStreetMap](https://www.openstreetmap.org/) に基づいており、[ODbL](https://opendatacommons.org/licenses/odbl/) ライセンスの下で提供されます。

© OpenStreetMap contributors
