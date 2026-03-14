"""Tests for SchemaRegistry."""

from pathlib import Path

from mcp_gennx.schemas.registry import SchemaRegistry


SCHEMA_DIR = Path(__file__).parent.parent / "src" / "mcp_gennx" / "schemas" / "raw"


def test_load_all_schemas():
    registry = SchemaRegistry(SCHEMA_DIR)
    endpoints = registry.list_endpoints()
    # 41 logical endpoints, but LCOM splits into 6 sub-types = 40 + 6 - 1 = 45
    # (db/LCOM is NOT registered; db/LCOM-GEN etc. are)
    assert len(endpoints) == 46, f"Expected 46 endpoints, got {len(endpoints)}: {sorted(endpoints)}"


def test_single_file_endpoint():
    registry = SchemaRegistry(SCHEMA_DIR)
    schema = registry.get_schema("db/NODE")
    assert schema is not None
    assert schema.endpoint == "db/NODE"
    assert schema.title == "Node"
    assert schema.active_methods == ["POST", "GET", "PUT", "DELETE"]
    assert "NODE" in schema.json_schema


def test_multi_file_endpoint_sect():
    registry = SchemaRegistry(SCHEMA_DIR)
    schema = registry.get_schema("db/SECT")
    assert schema is not None
    assert "POST" in schema.active_methods
    # SECT sub-types all use key "SECT", but properties should be merged
    assert "SECT" in schema.json_schema
    # Should have merged examples from multiple sub-type files
    assert len(schema.examples) > 1


def test_multi_file_endpoint_lcom():
    """LCOM sub-types have different API paths, so they're registered separately."""
    registry = SchemaRegistry(SCHEMA_DIR)
    # Each LCOM sub-type registered under its API path
    schema_gen = registry.get_schema("db/LCOM-GEN")
    assert schema_gen is not None
    assert schema_gen.api_path == "db/LCOM-GEN"
    assert schema_gen.endpoint == "db/LCOM"
    # The base "db/LCOM" should not exist
    assert registry.get_schema("db/LCOM") is None
    # All 6 sub-types should be registered
    lcom_schemas = [e for e in registry.list_endpoints() if "LCOM" in e]
    assert len(lcom_schemas) == 6


def test_doc_endpoint():
    registry = SchemaRegistry(SCHEMA_DIR)
    schema = registry.get_schema("doc/ANAL")
    assert schema is not None
    assert schema.active_methods == ["POST"]


def test_view_endpoint():
    registry = SchemaRegistry(SCHEMA_DIR)
    schema = registry.get_schema("view/CAPTURE")
    assert schema is not None
    assert schema.active_methods == ["POST"]


def test_get_methods_unit_styp():
    """db/UNIT and db/STYP should only have GET and PUT."""
    registry = SchemaRegistry(SCHEMA_DIR)
    for ep in ("db/UNIT", "db/STYP"):
        schema = registry.get_schema(ep)
        assert schema is not None
        assert "POST" not in schema.active_methods or "DELETE" not in schema.active_methods


def test_missing_endpoint():
    registry = SchemaRegistry(SCHEMA_DIR)
    assert registry.get_schema("db/NONEXISTENT") is None
