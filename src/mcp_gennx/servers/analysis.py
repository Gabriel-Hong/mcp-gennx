"""Analysis sub-server: eigenvalue, masses, analysis control, buckling, P-Delta, nonlinear."""

from __future__ import annotations

from fastmcp import FastMCP

from ..schemas.registry import SchemaRegistry
from ..tools.factory import ToolFactory

ENDPOINTS = {
    "db/EIGV": {"tier": 1, "toolset": "analysis_core"},
    "db/NMAS": {"tier": 1, "toolset": "analysis_core"},
    "db/ACTL": {"tier": 2, "toolset": "analysis_advanced"},
    "db/BUCK": {"tier": 2, "toolset": "analysis_advanced"},
    "db/PDEL": {"tier": 2, "toolset": "analysis_advanced"},
    "db/NLCT": {"tier": 2, "toolset": "analysis_advanced"},
}


def create_analysis_server(
    registry: SchemaRegistry, factory: ToolFactory
) -> FastMCP:
    server = FastMCP("analysis")
    for endpoint, meta in ENDPOINTS.items():
        schema = registry.get_schema(endpoint)
        if schema:
            factory.register_tools(
                server, schema, "analysis", meta["toolset"]
            )
    return server
