# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

routrace-data generates GeoJSON map data (Japanese expressways and coastlines) from OpenStreetMap for the routrace web application. Data is deployed via GitHub Pages.

## Commands

```bash
# Install dependencies
uv sync

# Generate all data (metadata, coastline, highways)
uv run poe generate

# Generate coastline only
uv run poe coastline

# Generate highways only
uv run poe highways

# Generate specific highway(s)
uv run python scripts/main.py --highway-name "東名" --verbose

# Run tests
uv run pytest tests/ -v
```

**System dependency:** `osmium-tool` must be installed (used for PBF pre-filtering).

## Architecture

### Data Pipeline

1. **Download**: Fetch full Japan OSM PBF file (~600MB, cached in `cache/`)
2. **Filter**: Use osmium-tool to extract only highway relations/ways
3. **Discover**: Scan filtered PBF for highway relations using `HighwayDiscoverer` (osmium handlers)
4. **Extract**: Load way geometries for each discovered highway
5. **Simplify**: Reduce coordinate density using Shapely (tolerance: 0.001 degrees ≈ 100m)
6. **Output**: Write GeoJSON files to `data/` directory

### Key Modules

| Module | Purpose |
|--------|---------|
| `scripts/main.py` | CLI entry point with argparse |
| `scripts/osm_downloader.py` | PBF download and osmium filtering |
| `scripts/osm_parser.py` | Highway discovery and way extraction using osmium |
| `scripts/highway.py` | GeoJSON conversion and file output |
| `scripts/coastline.py` | Coastline data fetching from external source |
| `scripts/simplify.py` | Geometry simplification with Shapely |

### Highway Grouping

Urban expressways (首都高速, 阪神高速, etc.) are grouped under umbrella names via `detect_group()` in `scripts/osm_parser.py`. This function identifies city expressways by prefix matching and returns the group name for the highway index.

### Output Structure

```
data/
├── metadata.json       # Version, timestamp, license info
├── coastline.json      # Simplified coastline GeoJSON
└── highways/
    ├── index.json      # Highway list with metadata (name, nameEn, ref, group, fileSize)
    └── {name}.json     # Individual highway GeoJSON files
```

## Notes

- The `overpass.py` module is legacy code (replaced by osmium/PBF approach)
- All generated data must comply with ODbL license (OpenStreetMap)
- Highway names use Japanese (e.g., "東名高速道路")
