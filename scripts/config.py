"""設定・高速道路定義"""

HIGHWAYS = [
    # NEXCO東日本
    {"id": "tomei", "name": "東名高速道路", "name_en": "Tomei Expressway",
     "query_name": "東名高速", "color": "#1e88e5"},
    {"id": "shin-tomei", "name": "新東名高速道路", "name_en": "Shin-Tomei Expressway",
     "query_name": "新東名高速", "color": "#1565c0"},
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
     "query_name": "名神高速", "color": "#43a047"},
    {"id": "shin-meishin", "name": "新名神高速道路", "name_en": "Shin-Meishin Expressway",
     "query_name": "新名神高速", "color": "#2e7d32"},
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
