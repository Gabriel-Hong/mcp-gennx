from __future__ import annotations

from pydantic import BaseModel, Field


class ApiSchema(BaseModel):
    """Represents a loaded GEN NX API schema from JSON."""

    endpoint: str  # e.g. "db/NODE"
    api_path: str = ""  # Actual API path (may differ from endpoint for sub-types, e.g. "db/LCOM-GEN")
    title: str  # e.g. "Node"
    active_methods: list[str]  # e.g. ["POST", "GET", "PUT", "DELETE"]
    json_schema: dict = Field(default_factory=dict)  # JSON Schema for properties
    examples: dict = Field(default_factory=dict)  # Example payloads
    tables: list = Field(default_factory=list)  # Parameter table metadata


class ToolDef(BaseModel):
    """Intermediate representation before creating a FunctionTool."""

    tool_name: str  # e.g. "post_db_node"
    endpoint: str  # e.g. "db/NODE"
    method: str  # e.g. "POST"
    title: str  # e.g. "Create Nodes"
    description: str
    tags: set[str]  # e.g. {"modeling", "write", "toolset:modeling_core"}
    annotations: dict  # e.g. {"readOnlyHint": False}
    parameters_schema: dict  # JSON Schema for LLM input
    tier: int = 1
