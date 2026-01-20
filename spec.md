# routrace データ生成スクリプト仕様書

## 1. 概要

OpenStreetMapから日本の高速道路および海岸線データを取得し、GitHub Pages配信用のGeoJSONファイルを生成するPythonスクリプト群。

### プロジェクト構成
| リポジトリ | 用途 | 公開URL |
|-----------|------|---------|
| `routrace` | フロントエンド | `https://<username>.github.io/routrace/` |
| `routrace-data` | データ配信 | `https://<username>.github.io/routrace-data/` |

## 2. 技術スタック

- **言語**: Python 3.10+
- **主要ライブラリ**:
  - `requests`: HTTP通信
  - `shapely`: ジオメトリ処理・簡略化
  - `geojson`: GeoJSON生成
- **オプション**:
  - `tqdm`: プログレスバー表示

### requirements.txt
```
requests>=2.28.0
shapely>=2.0.0
geojson>=3.0.0
tqdm>=4.65.0
```

## 3. ディレクトリ構成

```
routrace-data/
├── scripts/                        # スクリプト群
│   ├── main.py                     # エントリーポイント
│   ├── config.py                   # 設定・高速道路定義
│   ├── overpass.py                 # Overpass API クライアント
│   ├── coastline.py                # 海岸線データ処理
│   ├── highway.py                  # 高速道路データ処理
│   ├── simplify.py                 # ジオメトリ簡略化
│   └── requirements.txt
│
├── data/                           # ← 生成されるデータ（GitHub Pages配信）
│   ├── metadata.json               # メタデータ
│   ├── coastline.json              # 海岸線データ
│   └── highways/                   # 高速道路データ
│        ├── index.json             # 高速道路一覧
│        ├── tomei.json
│        ├── shin-tomei.json
│        ├── meishin.json
│        └── ...
│
└── README.md
```

### GitHub Pages配信URL
```
https://<username>.github.io/routrace-data/data/metadata.json
https://<username>.github.io/routrace-data/data/coastline.json
https://<username>.github.io/routrace-data/data/highways/index.json
https://<username>.github.io/routrace-data/data/highways/tomei.json
```

## 4. 出力ファイル仕様

### 4.1 data/metadata.json

```json
{
  "version": "1.0.0",
  "generatedAt": "2025-01-20T12:00:00Z",
  "source": "OpenStreetMap",
  "license": "ODbL",
  "attribution": "© OpenStreetMap contributors"
}
```

### 4.2 data/highways/index.json

```json
{
  "highways": [
    {
      "id": "tomei",
      "name": "東名高速道路",
      "nameEn": "Tomei Expressway",
      "color": "#1e88e5",
      "fileSize": 245000,
      "updatedAt": "2025-01-20T12:00:00Z"
    },
    {
      "id": "meishin",
      "name": "名神高速道路",
      "nameEn": "Meishin Expressway",
      "color": "#43a047",
      "fileSize": 189000,
      "updatedAt": "2025-01-20T12:00:00Z"
    }
  ]
}
```

### 4.3 data/highways/{id}.json

GeoJSON FeatureCollection形式:

```json
{
  "type": "FeatureCollection",
  "properties": {
    "id": "tomei",
    "name": "東名高速道路",
    "nameEn": "Tomei Expressway"
  },
  "features": [
    {
      "type": "Feature",
      "properties": {
        "name": "東名高速道路",
        "ref": "E1",
        "highway": "motorway"
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [[139.0, 35.0], [139.1, 35.1], ...]
      }
    }
  ]
}
```

### 4.4 data/coastline.json

GeoJSON FeatureCollection形式（簡略化済み）:

```json
{
  "type": "FeatureCollection",
  "properties": {
    "name": "Japan Coastline",
    "simplified": true,
    "tolerance": 0.001
  },
  "features": [
    {
      "type": "Feature",
      "properties": {},
      "geometry": {
        "type": "MultiLineString",
        "coordinates": [[[139.0, 35.0], [139.1, 35.1], ...], ...]
      }
    }
  ]
}
```

## 5. 高速道路定義 (config.py)

```python
HIGHWAYS = [
    # NEXCO東日本
    {"id": "tomei", "name": "東名高速道路", "name_en": "Tomei Expressway", 
     "query_name": "東名高速道路", "color": "#1e88e5"},
    {"id": "shin-tomei", "name": "新東名高速道路", "name_en": "Shin-Tomei Expressway",
     "query_name": "新東名高速道路", "color": "#1565c0"},
    {"id": "chuo", "name": "中央自動車道", "name_en": "Chuo Expressway",
     "query_name": "中央自動車道", "color": "#8e24aa"},
    {"id": "kanetsu", "name": "関越自動車道", "name_en": "Kan-Etsu Expressway",
     "query_name": "関越自動車道", "color": "#00897b"},
    {"id": "tohoku", "name": "東北自動車道", "name_en": "Tohoku Expressway",
     "query_name": "東北自動車道", "color": "#e53935"},
    {"id": "joban", "name": "常磐自動車道", "name_en": "Joban Expressway",
     "query_name": "常磐自動車道", "color": "#fb8c00"},
    
    # NEXCO中日本
    {"id": "meishin", "name": "名神高速道路", "name_en": "Meishin Expressway",
     "query_name": "名神高速道路", "color": "#43a047"},
    {"id": "shin-meishin", "name": "新名神高速道路", "name_en": "Shin-Meishin Expressway",
     "query_name": "新名神高速道路", "color": "#2e7d32"},
    {"id": "hokuriku", "name": "北陸自動車道", "name_en": "Hokuriku Expressway",
     "query_name": "北陸自動車道", "color": "#5e35b1"},
    
    # NEXCO西日本
    {"id": "sanyo", "name": "山陽自動車道", "name_en": "Sanyo Expressway",
     "query_name": "山陽自動車道", "color": "#d81b60"},
    {"id": "chugoku", "name": "中国自動車道", "name_en": "Chugoku Expressway",
     "query_name": "中国自動車道", "color": "#f4511e"},
    {"id": "kyushu", "name": "九州自動車道", "name_en": "Kyushu Expressway",
     "query_name": "九州自動車道", "color": "#6d4c41"},
    
    # 都市高速
    {"id": "shutoko", "name": "首都高速道路", "name_en": "Shuto Expressway",
     "query_name": "首都高速", "color": "#546e7a"},
    {"id": "hanshin", "name": "阪神高速道路", "name_en": "Hanshin Expressway",
     "query_name": "阪神高速", "color": "#78909c"},
    
    # 北海道
    {"id": "doo", "name": "道央自動車道", "name_en": "Do-o Expressway",
     "query_name": "道央自動車道", "color": "#0288d1"},
]

# Overpass API設定
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 120

# 日本の範囲 (bbox: 南緯, 西経, 北緯, 東経)
JAPAN_BBOX = (24.0, 122.0, 46.0, 154.0)

# 簡略化の許容誤差（度単位、約100m）
SIMPLIFY_TOLERANCE = 0.001

# 出力ディレクトリ名
DATA_DIR = "data"
HIGHWAYS_DIR = "highways"
```

## 6. モジュール詳細仕様

### 6.1 overpass.py

```python
"""Overpass API クライアント"""

def query_overpass(query: str, timeout: int = 120) -> dict:
    """
    Overpass APIにクエリを送信してJSONレスポンスを取得
    
    Args:
        query: Overpass QL クエリ文字列
        timeout: タイムアウト秒数
    
    Returns:
        Overpass APIのJSONレスポンス (dict)
    
    Raises:
        requests.RequestException: 通信エラー
        ValueError: レスポンスのパースエラー
    """
    pass

def build_highway_query(name: str) -> str:
    """
    高速道路取得用のOverpass QLクエリを生成
    
    Args:
        name: 高速道路名（例: "東名高速道路"）
    
    Returns:
        Overpass QLクエリ文字列
    
    生成されるクエリ例:
        [out:json][timeout:120];
        area["name"="日本"]["admin_level"="2"]->.japan;
        (
          way["highway"="motorway"]["name"~"東名高速道路"](area.japan);
          way["highway"="motorway_link"]["name"~"東名"](area.japan);
        );
        out geom;
    """
    pass

def build_coastline_query(bbox: tuple[float, float, float, float]) -> str:
    """
    海岸線取得用のOverpass QLクエリを生成
    
    Args:
        bbox: (南緯, 西経, 北緯, 東経)
    
    Returns:
        Overpass QLクエリ文字列
    """
    pass
```

### 6.2 highway.py

```python
"""高速道路データ処理"""

def fetch_highway(highway_config: dict) -> dict:
    """
    指定された高速道路のデータを取得
    
    Args:
        highway_config: config.pyのHIGHWAYS要素
    
    Returns:
        GeoJSON FeatureCollection (dict)
    """
    pass

def overpass_to_geojson(overpass_response: dict) -> dict:
    """
    Overpass APIレスポンスをGeoJSON形式に変換
    
    Args:
        overpass_response: Overpass APIのJSONレスポンス
    
    Returns:
        GeoJSON FeatureCollection (dict)
    
    Note:
        - wayのgeometry座標をGeoJSONのLineStringに変換
        - name, ref, highway タグをpropertiesに含める
    """
    pass

def save_highway(highway_id: str, geojson: dict, output_dir: Path) -> int:
    """
    高速道路GeoJSONをファイルに保存
    
    Args:
        highway_id: 高速道路ID（例: "tomei"）
        geojson: GeoJSON FeatureCollection
        output_dir: 出力ディレクトリ (data/highways/)
    
    Returns:
        保存したファイルのバイト数
    """
    pass
```

### 6.3 coastline.py

```python
"""海岸線データ処理"""

def fetch_coastline(bbox: tuple[float, float, float, float]) -> dict:
    """
    指定範囲の海岸線データを取得
    
    Args:
        bbox: (南緯, 西経, 北緯, 東経)
    
    Returns:
        GeoJSON FeatureCollection (dict)
    """
    pass

def save_coastline(geojson: dict, output_path: Path) -> int:
    """
    海岸線GeoJSONをファイルに保存
    
    Args:
        geojson: GeoJSON FeatureCollection
        output_path: 出力ファイルパス (data/coastline.json)
    
    Returns:
        保存したファイルのバイト数
    """
    pass
```

### 6.4 simplify.py

```python
"""ジオメトリ簡略化"""

from shapely.geometry import shape, mapping
from shapely.ops import transform

def simplify_geojson(geojson: dict, tolerance: float = 0.001) -> dict:
    """
    GeoJSONのジオメトリを簡略化
    
    Args:
        geojson: GeoJSON FeatureCollection
        tolerance: 簡略化の許容誤差（度単位）
    
    Returns:
        簡略化されたGeoJSON FeatureCollection
    
    Note:
        - Shapely の simplify() を使用
        - preserve_topology=True で位相関係を保持
    """
    pass

def get_coordinate_count(geojson: dict) -> int:
    """
    GeoJSON内の総座標数をカウント
    
    Args:
        geojson: GeoJSON FeatureCollection
    
    Returns:
        座標点の総数
    """
    pass
```

### 6.5 main.py

```python
"""エントリーポイント"""

import argparse
from pathlib import Path

def main():
    """
    コマンドライン引数:
        --output-dir: 出力ベースディレクトリ（デフォルト: リポジトリルート）
                      data/ディレクトリはこの下に自動作成される
        --highways-only: 高速道路のみ生成
        --coastline-only: 海岸線のみ生成
        --highway-id: 特定の高速道路のみ生成（複数指定可）
        --dry-run: 実際には保存しない
        --verbose: 詳細ログ出力
    
    実行例:
        # 全データ生成（リポジトリルートから実行）
        python scripts/main.py
        
        # 出力先を明示的に指定
        python scripts/main.py --output-dir ./
        
        # 高速道路のみ
        python scripts/main.py --highways-only
        
        # 特定の高速道路のみ
        python scripts/main.py --highway-id tomei --highway-id meishin
        
        # ドライラン
        python scripts/main.py --dry-run --verbose
    """
    pass

def generate_all(output_dir: Path, dry_run: bool = False) -> None:
    """
    全データを生成
    
    出力先:
        output_dir/data/metadata.json
        output_dir/data/coastline.json
        output_dir/data/highways/index.json
        output_dir/data/highways/{id}.json
    """
    pass

def generate_highways(
    output_dir: Path, 
    highway_ids: list[str] | None = None,
    dry_run: bool = False
) -> None:
    """高速道路データを生成"""
    pass

def generate_coastline(output_dir: Path, dry_run: bool = False) -> None:
    """海岸線データを生成"""
    pass

def generate_metadata(output_dir: Path) -> None:
    """data/metadata.jsonを生成"""
    pass

def generate_index(output_dir: Path, highways_info: list[dict]) -> None:
    """data/highways/index.jsonを生成"""
    pass

if __name__ == "__main__":
    main()
```

## 7. エラーハンドリング

| エラー種別 | 対応 |
|-----------|------|
| Overpass API接続エラー | 3回リトライ（5秒間隔）、失敗時は例外 |
| Overpass API タイムアウト | タイムアウト値を増やして1回リトライ |
| データなし（0件） | 警告ログ出力、空のFeatureCollectionを生成 |
| JSON書き込みエラー | 例外を上位に伝播 |

## 8. ログ出力

```
2025-01-20 12:00:00 INFO  開始: 全データ生成
2025-01-20 12:00:00 INFO  出力先: /path/to/routrace-data/data/
2025-01-20 12:00:01 INFO  海岸線データ取得中...
2025-01-20 12:00:30 INFO  海岸線データ取得完了: 15234 features
2025-01-20 12:00:31 INFO  海岸線データ簡略化: 152340 coords → 45678 coords
2025-01-20 12:00:32 INFO  保存: data/coastline.json (2.3 MB)
2025-01-20 12:00:33 INFO  高速道路データ取得中: 東名高速道路
2025-01-20 12:00:45 INFO  保存: data/highways/tomei.json (245 KB)
...
2025-01-20 12:05:00 INFO  完了: 15ファイル生成、合計 12.5 MB
```

## 9. 実行手順

```bash
# 1. リポジトリをクローン
git clone https://github.com/<username>/routrace-data.git
cd routrace-data

# 2. 仮想環境作成・依存インストール
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r scripts/requirements.txt

# 3. 全データ生成（リポジトリルートから実行）
python scripts/main.py --verbose

# 4. 確認
ls -la data/
ls -la data/highways/

# 5. コミット・プッシュ
git add data/
git commit -m "Update map data"
git push origin main
```

## 10. 注意事項

- Overpass APIには利用制限があるため、連続実行時は適切な間隔（1秒以上）を空ける
- 海岸線データは取得に時間がかかる（1-2分程度）
- 生成されたJSONはUTF-8、インデントなし（ファイルサイズ削減のため）
- OpenStreetMapのライセンス（ODbL）に従い、attributionを含める
- data/ディレクトリは自動作成される（存在しない場合）
