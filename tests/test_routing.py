"""Routing map <-> schema registry consistency.

These guards are what make ``endpoint_subserver_map.json`` a safe single source
of truth: if a schema is added under ``raw/`` without a map entry (or a map
entry has no schema), the server would silently drop or fail to register tools.
Catch that here instead.
"""

from mcp_gennx.routing import all_routes, load_toolset_definitions, routes_for
from mcp_gennx.schemas.registry import SchemaRegistry

from conftest import SCHEMA_DIR

SUB_SERVERS = ("modeling", "boundary", "loads", "analysis", "project")


def test_map_matches_registry_endpoints():
    """Every routed endpoint has a schema, and every schema is routed."""
    registry = SchemaRegistry(SCHEMA_DIR)
    routed = {route.endpoint for route in all_routes()}
    loaded = set(registry.list_endpoints())
    assert routed == loaded, (
        f"map-only (no schema): {sorted(routed - loaded)}; "
        f"registry-only (unrouted): {sorted(loaded - routed)}"
    )


def test_every_subserver_has_routes():
    for name in SUB_SERVERS:
        assert routes_for(name), f"no routes resolved for sub-server {name!r}"


def test_manual_routes_are_doc_and_view():
    """`manual` flags exactly the bespoke-signature tools project.py hand-builds."""
    manual = {route.endpoint for route in all_routes() if route.manual}
    assert manual == {
        "doc/ANAL",
        "doc/NEW",
        "doc/OPEN",
        "doc/SAVE",
        "doc/SAVEAS",
        "doc/CLOSE",
        "view/CAPTURE",
    }


def test_toolset_definitions_reference_known_toolsets():
    """Every toolset named in a preset is actually routed to some endpoint."""
    known = {route.toolset for route in all_routes()}
    for preset, toolsets in load_toolset_definitions().items():
        for toolset in toolsets:
            assert toolset in known, (
                f"preset {preset!r} references unknown toolset {toolset!r}"
            )
