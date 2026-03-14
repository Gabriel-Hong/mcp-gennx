"""Main GEN NX MCP server assembly."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastmcp import FastMCP

from .client.gennx_client import GennxApiClient
from .config import GennxSettings
from .schemas.registry import SchemaRegistry
from .servers import (
    create_analysis_server,
    create_boundary_server,
    create_loads_server,
    create_modeling_server,
    create_project_server,
)
from .tools.factory import ToolFactory

logger = logging.getLogger(__name__)

INSTRUCTIONS = """\
GEN NX MCP Server - Structural Engineering Analysis

This server provides tools for interacting with GEN NX, a structural engineering \
analysis software. You can create and manage structural models, apply loads and \
boundary conditions, and run analyses.

Typical workflow:
1. Create nodes (post_db_node) to define geometry
2. Create elements (post_db_elem) to connect nodes
3. Define materials (post_db_matl) and sections (post_db_sect)
4. Apply boundary conditions (post_db_cons)
5. Define load cases (post_db_stld) and apply loads (post_db_cnld, post_db_bmld)
6. Run analysis (post_doc_anal)

Use GET tools to query existing data, PUT to update, DELETE to remove.
"""

# Toolset definitions
TOOLSET_DEFINITIONS: dict[str, list[str]] = {
    "default": [
        "modeling_core",
        "boundary_core",
        "loads_core",
        "analysis_core",
        "project",
    ],
    "all": [
        "modeling_core",
        "modeling_advanced",
        "boundary_core",
        "boundary_advanced",
        "loads_core",
        "loads_advanced",
        "analysis_core",
        "analysis_advanced",
        "project",
    ],
}

# All domain tags used across sub-servers
DOMAIN_TAGS = {"modeling", "boundary", "loads", "analysis", "project"}


@asynccontextmanager
async def app_lifespan(server: FastMCP):
    settings = GennxSettings()
    client = GennxApiClient(
        settings.gennx_api_base_url, settings.gennx_api_timeout
    )
    try:
        yield {"api_client": client, "settings": settings}
    finally:
        await client.close()


def create_server() -> FastMCP:
    settings = GennxSettings()

    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    # 1. Main server with lifespan
    main = FastMCP("gennx", instructions=INSTRUCTIONS, lifespan=app_lifespan)

    # 2. Load schemas
    schema_dir = Path(__file__).parent / "schemas" / "raw"
    registry = SchemaRegistry(schema_dir)
    factory = ToolFactory()

    logger.info(
        "Loaded %d endpoint schemas: %s",
        len(registry.list_endpoints()),
        registry.list_endpoints(),
    )

    # 3. Create and mount sub-servers (no namespace = flat tool names)
    main.mount(create_modeling_server(registry, factory))
    main.mount(create_boundary_server(registry, factory))
    main.mount(create_loads_server(registry, factory))
    main.mount(create_analysis_server(registry, factory))
    main.mount(create_project_server(registry, factory))

    # 4. Apply toolset filtering
    if settings.toolsets != "all":
        _apply_toolset_filter(main, settings.toolsets)

    # 5. Read-only mode: hide all write tools
    if settings.read_only:
        main.disable(tags={"write"}, components={"tool"})

    return main


def _apply_toolset_filter(server: FastMCP, toolsets_config: str) -> None:
    """Apply toolset filtering using FastMCP enable/disable."""
    # Resolve which toolsets are active
    enabled_toolsets = _resolve_toolsets(toolsets_config)
    enabled_tags = {f"toolset:{ts}" for ts in enabled_toolsets}

    # Disable all domain tools first
    for tag in DOMAIN_TAGS:
        server.disable(tags={tag}, components={"tool"})

    # Re-enable the active toolsets
    for tag in enabled_tags:
        server.enable(tags={tag}, components={"tool"})


def _resolve_toolsets(toolsets_config: str) -> list[str]:
    """Resolve toolset config string to list of toolset names."""
    parts = [p.strip() for p in toolsets_config.split(",")]
    result = []
    for part in parts:
        if part in TOOLSET_DEFINITIONS:
            result.extend(TOOLSET_DEFINITIONS[part])
        else:
            # Treat as individual toolset name
            result.append(part)
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for ts in result:
        if ts not in seen:
            seen.add(ts)
            deduped.append(ts)
    return deduped
