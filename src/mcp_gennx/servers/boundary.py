"""Boundary sub-server: constraints, springs, links, releases, offsets."""

from __future__ import annotations

from fastmcp import FastMCP

from ..schemas.registry import SchemaRegistry
from ..tools.factory import ToolFactory
from ._common import register_routed_tools


def create_boundary_server(
    registry: SchemaRegistry, factory: ToolFactory
) -> FastMCP:
    server = FastMCP("boundary")
    register_routed_tools(server, registry, factory, "boundary")
    return server
