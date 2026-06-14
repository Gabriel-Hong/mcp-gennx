"""Shared test fixtures and helpers."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

SCHEMA_DIR = Path(__file__).parent.parent / "src" / "mcp_gennx" / "schemas" / "raw"


def _api_path(data: dict) -> str:
    """Mirror ``SchemaRegistry._extract_api_path`` independently (test cross-check)."""
    input_uri = data.get("input_uri", "")
    if " + " in input_uri:
        return input_uri.split(" + ", 1)[1].strip()
    return data.get("endpoint", "")


def expected_endpoint_count(schema_dir: Path = SCHEMA_DIR) -> int:
    """Number of endpoints the registry should expose, derived from raw/*.json.

    Reproduces the registry's grouping rule WITHOUT calling the registry, so
    endpoint-count assertions track the schema set automatically instead of a
    hardcoded number. Group files by their ``endpoint`` field, then count the
    distinct API paths within each group:

      - single file               -> 1            (e.g. db/NODE)
      - many files, 1 API path     -> 1 (merged)   (e.g. db/SECT, db/THIK)
      - many files, N API paths    -> N (separate) (e.g. db/LCOM-*)

    A divergence between this and ``SchemaRegistry.list_endpoints()`` signals a
    grouping regression (a dropped/duplicated schema or a broken merge/split).
    """
    groups: dict[str, set[str]] = defaultdict(set)
    for path in schema_dir.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        endpoint = data.get("endpoint", "")
        if not endpoint:
            continue
        groups[endpoint].add(_api_path(data))
    return sum(len(api_paths) for api_paths in groups.values())
