"""Boundary sub-server: constraints, springs, links, releases, offsets."""

from __future__ import annotations

from fastmcp import FastMCP

from ..schemas.registry import SchemaRegistry
from ..tools.factory import ToolFactory

ENDPOINTS = {
    "db/CONS": {"tier": 1, "toolset": "boundary_core"},
    "db/NSPR": {"tier": 1, "toolset": "boundary_core"},
    "db/GSPR": {"tier": 2, "toolset": "boundary_advanced"},
    "db/ELNK": {"tier": 2, "toolset": "boundary_advanced"},
    "db/RIGD": {"tier": 2, "toolset": "boundary_advanced"},
    "db/FRLS": {"tier": 2, "toolset": "boundary_advanced"},
    "db/OFFS": {"tier": 2, "toolset": "boundary_advanced"},
    "db/MCON": {"tier": 2, "toolset": "boundary_advanced"},
}


def create_boundary_server(
    registry: SchemaRegistry, factory: ToolFactory
) -> FastMCP:
    server = FastMCP("boundary")
    for endpoint, meta in ENDPOINTS.items():
        schema = registry.get_schema(endpoint)
        if schema:
            factory.register_tools(
                server, schema, "boundary", meta["toolset"]
            )
    return server
