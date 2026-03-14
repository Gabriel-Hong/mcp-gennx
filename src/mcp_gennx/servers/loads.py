"""Loads sub-server: load cases, body forces, nodal loads, beam loads, combinations."""

from __future__ import annotations

from fastmcp import FastMCP

from ..schemas.registry import SchemaRegistry
from ..tools.factory import ToolFactory

ENDPOINTS = {
    "db/STLD": {"tier": 1, "toolset": "loads_core"},
    "db/BODF": {"tier": 1, "toolset": "loads_core"},
    "db/CNLD": {"tier": 1, "toolset": "loads_core"},
    "db/BMLD": {"tier": 1, "toolset": "loads_core"},
    "db/PRES": {"tier": 2, "toolset": "loads_advanced"},
    "db/PSLT": {"tier": 2, "toolset": "loads_advanced"},
    "db/ETMP": {"tier": 2, "toolset": "loads_advanced"},
    "db/GTMP": {"tier": 2, "toolset": "loads_advanced"},
}

# LCOM has sub-typed URIs (db/LCOM-GEN, db/LCOM-CONC, etc.)
LCOM_SUBTYPES = {
    "db/LCOM-GEN": {"tier": 1, "toolset": "loads_core"},
    "db/LCOM-CONC": {"tier": 1, "toolset": "loads_core"},
    "db/LCOM-STEEL": {"tier": 1, "toolset": "loads_core"},
    "db/LCOM-SRC": {"tier": 1, "toolset": "loads_core"},
    "db/LCOM-STLCOMP": {"tier": 1, "toolset": "loads_core"},
    "db/LCOM-SEISMIC": {"tier": 1, "toolset": "loads_core"},
}


def create_loads_server(
    registry: SchemaRegistry, factory: ToolFactory
) -> FastMCP:
    server = FastMCP("loads")

    # Standard endpoints
    for endpoint, meta in ENDPOINTS.items():
        schema = registry.get_schema(endpoint)
        if schema:
            factory.register_tools(
                server, schema, "loads", meta["toolset"]
            )

    # LCOM sub-types (each has a different API path)
    for api_path, meta in LCOM_SUBTYPES.items():
        schema = registry.get_schema(api_path)
        if schema:
            factory.register_tools(
                server, schema, "loads", meta["toolset"]
            )

    return server
