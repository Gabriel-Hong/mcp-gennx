"""Static server-assembly config, loaded from packaged JSON.

Two pieces of wiring used to be duplicated as hardcoded Python dicts:

* which sub-server / toolset / tier each endpoint belongs to
  (was an ``ENDPOINTS`` dict in every ``servers/*.py``), and
* which toolsets the ``default`` / ``all`` presets expand to
  (was ``TOOLSET_DEFINITIONS`` in ``server.py``).

Both now live in ``data/*.json`` shipped inside the package and are the single
source of truth. To add an endpoint: drop its schema in ``schemas/raw/`` and add
one line to ``endpoint_subserver_map.json`` — no Python edit needed.

The JSON lives under the package (not the repo-root ``data/``) so it is bundled
into the wheel and resolvable regardless of the working directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
ENDPOINT_MAP_PATH = DATA_DIR / "endpoint_subserver_map.json"
TOOLSET_DEFS_PATH = DATA_DIR / "toolset_definitions.json"


@dataclass(frozen=True)
class EndpointRoute:
    """Where one endpoint's tools should be registered.

    ``manual`` marks endpoints whose tools have bespoke signatures (doc/* and
    view/CAPTURE) and are registered by hand in ``servers/project.py`` rather
    than by the generic ``ToolFactory`` loop.
    """

    endpoint: str
    sub_server: str
    toolset: str
    tier: int
    manual: bool = False


@lru_cache(maxsize=None)
def _load_routes(map_path: Path) -> tuple[EndpointRoute, ...]:
    data = json.loads(map_path.read_text(encoding="utf-8"))
    return tuple(
        EndpointRoute(
            endpoint=endpoint,
            sub_server=meta["sub_server"],
            toolset=meta["toolset"],
            tier=int(meta["tier"]),
            manual=bool(meta.get("manual", False)),
        )
        for endpoint, meta in data.items()
    )


def all_routes(map_path: Path = ENDPOINT_MAP_PATH) -> tuple[EndpointRoute, ...]:
    """Every endpoint route from the map (cached)."""
    return _load_routes(map_path)


def routes_for(
    sub_server: str,
    *,
    include_manual: bool = False,
    map_path: Path = ENDPOINT_MAP_PATH,
) -> list[EndpointRoute]:
    """Routes belonging to ``sub_server``.

    ``manual`` routes are excluded by default so the generic factory loop does
    not double-register tools that ``project.py`` builds by hand.
    """
    return [
        route
        for route in all_routes(map_path)
        if route.sub_server == sub_server
        and (include_manual or not route.manual)
    ]


@lru_cache(maxsize=None)
def load_toolset_definitions(
    defs_path: Path = TOOLSET_DEFS_PATH,
) -> dict[str, list[str]]:
    """Toolset presets (e.g. ``default`` -> list of toolset tags)."""
    return json.loads(defs_path.read_text(encoding="utf-8"))
