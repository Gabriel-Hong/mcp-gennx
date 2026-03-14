"""Integration tests for the full server assembly."""

import asyncio
import os

import pytest

from mcp_gennx.server import create_server


def test_default_toolset_count():
    """Default toolset should expose a reasonable number of tools."""
    os.environ["TOOLSETS"] = "default"
    server = create_server()

    async def check():
        tools = await server.list_tools()
        # Tier 1 CRUD + project tools + LCOM 6 sub-types
        assert 70 <= len(tools) <= 100, f"Expected 70-100 tools, got {len(tools)}"
        return len(tools)

    count = asyncio.run(check())
    # Clean up
    os.environ.pop("TOOLSETS", None)


def test_all_toolset_count():
    """All toolset should expose all tools."""
    os.environ["TOOLSETS"] = "all"
    server = create_server()

    async def check():
        tools = await server.list_tools()
        # Should be around 137 (all 41 APIs * methods + project manuals)
        assert len(tools) > 100, f"Expected >100 tools, got {len(tools)}"
        return len(tools)

    count = asyncio.run(check())
    os.environ.pop("TOOLSETS", None)


def test_read_only_mode():
    """Read-only mode should only expose GET tools."""
    os.environ["READ_ONLY"] = "true"
    os.environ["TOOLSETS"] = "default"
    server = create_server()

    async def check():
        tools = await server.list_tools()
        for t in tools:
            assert t.name.startswith("get_"), f"Non-GET tool in read-only: {t.name}"
        return len(tools)

    count = asyncio.run(check())
    assert count > 0
    os.environ.pop("READ_ONLY", None)
    os.environ.pop("TOOLSETS", None)


def test_custom_toolset():
    """Custom toolset should include specified toolsets."""
    os.environ["TOOLSETS"] = "default,modeling_advanced"
    server = create_server()

    async def check():
        tools = await server.list_tools()
        names = {t.name for t in tools}
        # Should have default tools
        assert "post_db_node" in names
        # Should also have modeling_advanced tools
        assert "post_db_grup" in names or "get_db_grup" in names
        return len(tools)

    count = asyncio.run(check())
    os.environ.pop("TOOLSETS", None)


def test_tool_descriptions_not_empty():
    """All tools should have non-empty descriptions."""
    server = create_server()

    async def check():
        tools = await server.list_tools()
        for t in tools:
            assert t.description, f"Tool {t.name} has empty description"

    asyncio.run(check())


def test_all_endpoints_loaded():
    """SchemaRegistry should load all endpoints (LCOM splits into 6 sub-types)."""
    from mcp_gennx.schemas.registry import SchemaRegistry
    from pathlib import Path

    schema_dir = Path(__file__).parent.parent / "src" / "mcp_gennx" / "schemas" / "raw"
    registry = SchemaRegistry(schema_dir)
    # 41 logical APIs, but LCOM has 6 sub-types registered separately
    assert len(registry.list_endpoints()) == 46
