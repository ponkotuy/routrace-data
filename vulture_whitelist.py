# Vulture whitelist - false positives

# osmium framework callbacks (called by the framework, not directly)
from scripts.osm_parser import (
    BulkWayCollector,
    HighwayDiscoverer,
    NationalRouteDiscoverer,
)

HighwayDiscoverer.relation  # Called by osmium.SimpleHandler.apply_file()
NationalRouteDiscoverer.relation  # Called by osmium.SimpleHandler.apply_file()
BulkWayCollector.way  # Called by osmium.SimpleHandler.apply_file()
