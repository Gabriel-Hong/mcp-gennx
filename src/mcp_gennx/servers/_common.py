"""Shared sub-server assembly helpers."""

from __future__ import annotations

from fastmcp import FastMCP

from ..routing import routes_for
from ..schemas.registry import SchemaRegistry
from ..tools.factory import ToolFactory


def register_routed_tools(
    server: FastMCP,
    registry: SchemaRegistry,
    factory: ToolFactory,
    sub_server: str,
) -> None:
    """Register factory-built tools for every endpoint routed to ``sub_server``.

    Endpoint -> (toolset, tier) routing comes from the endpoint map (see
    :mod:`mcp_gennx.routing`), not a hardcoded dict. ``manual`` endpoints are
    skipped here and registered by hand by their sub-server. Endpoints with no
    loaded schema are skipped (the registry load step logs the full set).
    """
    for route in routes_for(sub_server):
        schema = registry.get_schema(route.endpoint)
        if schema:
            factory.register_tools(server, schema, sub_server, route.toolset)
