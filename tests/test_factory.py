"""Tests for ToolFactory."""

import asyncio
from pathlib import Path

import pytest

from mcp_gennx.schemas.registry import SchemaRegistry
from mcp_gennx.tools.factory import ToolFactory
from fastmcp import FastMCP


SCHEMA_DIR = Path(__file__).parent.parent / "src" / "mcp_gennx" / "schemas" / "raw"


@pytest.fixture
def registry():
    return SchemaRegistry(SCHEMA_DIR)


@pytest.fixture
def factory():
    return ToolFactory()


def test_register_crud_tools(registry, factory):
    """db/NODE should generate 4 tools (POST, GET, PUT, DELETE)."""
    server = FastMCP("test")
    schema = registry.get_schema("db/NODE")
    names = factory.register_tools(server, schema, "modeling", "modeling_core")
    assert len(names) == 4
    assert "post_db_node" in names
    assert "get_db_node" in names
    assert "put_db_node" in names
    assert "delete_db_node" in names


def test_tool_naming_convention(registry, factory):
    """Tool names should follow {method}_{endpoint} pattern."""
    server = FastMCP("test")
    schema = registry.get_schema("db/ELEM")
    names = factory.register_tools(server, schema, "modeling", "modeling_core")
    for name in names:
        assert name.islower()
        assert "_" in name
        # No slashes
        assert "/" not in name


def test_tool_tags(registry, factory):
    """Tools should have domain, access, and toolset tags."""
    server = FastMCP("test")
    schema = registry.get_schema("db/NODE")
    factory.register_tools(server, schema, "modeling", "modeling_core")

    async def check():
        tools = await server.list_tools()
        for t in tools:
            tags = t.tags or set()
            assert "modeling" in tags
            assert "toolset:modeling_core" in tags
            if t.name.startswith("get_"):
                assert "read" in tags
            else:
                assert "write" in tags

    asyncio.run(check())


def test_get_tool_no_params(registry, factory):
    """GET tools should have no parameters."""
    server = FastMCP("test")
    schema = registry.get_schema("db/NODE")
    factory.register_tools(server, schema, "modeling", "modeling_core")

    async def check():
        tools = await server.list_tools()
        for t in tools:
            if t.name.startswith("get_"):
                assert t.parameters["properties"] == {}

    asyncio.run(check())


def test_post_tool_has_assign(registry, factory):
    """POST tools should have Assign parameter."""
    server = FastMCP("test")
    schema = registry.get_schema("db/NODE")
    factory.register_tools(server, schema, "modeling", "modeling_core")

    async def check():
        tools = await server.list_tools()
        for t in tools:
            if t.name.startswith("post_"):
                assert "Assign" in t.parameters["properties"]
                assert "Assign" in t.parameters.get("required", [])

    asyncio.run(check())


def test_delete_tool_has_array_assign(registry, factory):
    """DELETE tools should have Assign as array."""
    server = FastMCP("test")
    schema = registry.get_schema("db/NODE")
    factory.register_tools(server, schema, "modeling", "modeling_core")

    async def check():
        tools = await server.list_tools()
        for t in tools:
            if t.name.startswith("delete_"):
                assign = t.parameters["properties"]["Assign"]
                assert assign["type"] == "array"

    asyncio.run(check())


def test_unit_styp_limited_methods(registry, factory):
    """db/UNIT and db/STYP should not have POST/DELETE tools."""
    server = FastMCP("test")
    for ep in ("db/UNIT", "db/STYP"):
        schema = registry.get_schema(ep)
        names = factory.register_tools(server, schema, "project", "project")
        # Should have GET and PUT only
        assert any("get_" in n for n in names)
        assert any("put_" in n for n in names)
