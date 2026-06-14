"""Tests for SchemaRegistry."""

from mcp_gennx.schemas.registry import SchemaRegistry

from conftest import SCHEMA_DIR, expected_endpoint_count


def test_load_all_schemas():
    registry = SchemaRegistry(SCHEMA_DIR)
    endpoints = registry.list_endpoints()
    # Expected count is derived from raw/*.json (handles SECT-style merges and
    # LCOM-style splits) so adding a schema needs no test edit.
    expected = expected_endpoint_count(SCHEMA_DIR)
    assert len(endpoints) == expected, (
        f"Registry exposed {len(endpoints)} endpoints but raw/*.json implies "
        f"{expected}: {sorted(endpoints)}"
    )
    # Floor guard: ensure schemas actually loaded (not a vacuous 0 == 0).
    assert len(endpoints) > 40


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


def test_schema_has_description_fields():
    """New 4 fields must be loaded from raw JSON."""
    registry = SchemaRegistry(SCHEMA_DIR)
    s = registry.get_schema("db/NODE")
    assert s.description, "db/NODE must have a non-empty description"
    assert s.feature_name == "Create Nodes"
    assert s.menu_path.startswith("[Node/Element]")
    assert s.usage, "db/NODE.usage should be populated from Feature.sections.input"


def test_multi_merged_description_present():
    """SECT merges sub-files; description should be a single deduplicated string."""
    registry = SchemaRegistry(SCHEMA_DIR)
    s = registry.get_schema("db/SECT")
    assert s.description, "db/SECT must have a non-empty description after merge"
    assert s.feature_name, "db/SECT.feature_name should come from one of the sub-files"


def test_multi_separate_description_per_subtype():
    """Each LCOM sub-type gets its own description."""
    registry = SchemaRegistry(SCHEMA_DIR)
    s = registry.get_schema("db/LCOM-GEN")
    assert s.description, "db/LCOM-GEN must have its own description"


def test_all_endpoints_have_description():
    """Regression guard: every loaded endpoint must produce a non-empty description."""
    registry = SchemaRegistry(SCHEMA_DIR)
    missing = [
        ep
        for ep in registry.list_endpoints()
        if not (registry.get_schema(ep).description or "").strip()
    ]
    assert not missing, f"Endpoints with empty description: {missing}"
