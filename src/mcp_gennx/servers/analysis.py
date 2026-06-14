"""Analysis sub-server: eigenvalue, masses, analysis control, buckling, P-Delta, nonlinear."""

from __future__ import annotations

from fastmcp import FastMCP

from ..schemas.registry import SchemaRegistry
from ..tools.factory import ToolFactory
from ._common import register_routed_tools


def create_analysis_server(
    registry: SchemaRegistry, factory: ToolFactory
) -> FastMCP:
    server = FastMCP("analysis")
    register_routed_tools(server, registry, factory, "analysis")
    return server
