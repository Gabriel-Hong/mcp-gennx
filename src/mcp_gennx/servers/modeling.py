"""Modeling sub-server: nodes, elements, materials, sections, thickness, groups."""

from __future__ import annotations

from fastmcp import FastMCP

from ..schemas.registry import SchemaRegistry
from ..tools.factory import ToolFactory
from ._common import register_routed_tools


def create_modeling_server(
    registry: SchemaRegistry, factory: ToolFactory
) -> FastMCP:
    server = FastMCP("modeling")
    register_routed_tools(server, registry, factory, "modeling")
    return server
