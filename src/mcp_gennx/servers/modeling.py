"""Modeling sub-server: nodes, elements, materials, sections, thickness, groups."""

from __future__ import annotations

from fastmcp import FastMCP

from ..schemas.registry import SchemaRegistry
from ..tools.factory import ToolFactory

ENDPOINTS = {
    "db/NODE": {"tier": 1, "toolset": "modeling_core"},
    "db/ELEM": {"tier": 1, "toolset": "modeling_core"},
    "db/MATL": {"tier": 1, "toolset": "modeling_core"},
    "db/SECT": {"tier": 1, "toolset": "modeling_core"},
    "db/THIK": {"tier": 1, "toolset": "modeling_core"},
    "db/GRUP": {"tier": 2, "toolset": "modeling_advanced"},
    "db/BNGR": {"tier": 2, "toolset": "modeling_advanced"},
    "db/SKEW": {"tier": 2, "toolset": "modeling_advanced"},
    "db/STOR": {"tier": 2, "toolset": "modeling_advanced"},
}


def create_modeling_server(
    registry: SchemaRegistry, factory: ToolFactory
) -> FastMCP:
    server = FastMCP("modeling")
    for endpoint, meta in ENDPOINTS.items():
        schema = registry.get_schema(endpoint)
        if schema:
            factory.register_tools(
                server, schema, "modeling", meta["toolset"]
            )
    return server
