"""Loads sub-server: load cases, body forces, nodal loads, beam loads, combinations.

Includes LCOM sub-types (db/LCOM-GEN, db/LCOM-CONC, ...), which the registry
keys by their distinct API paths; the endpoint map routes each one here.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ..schemas.registry import SchemaRegistry
from ..tools.factory import ToolFactory
from ._common import register_routed_tools


def create_loads_server(
    registry: SchemaRegistry, factory: ToolFactory
) -> FastMCP:
    server = FastMCP("loads")
    register_routed_tools(server, registry, factory, "loads")
    return server
