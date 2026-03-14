"""Dynamic tool generation from API schemas."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.tools.tool import Tool
from fastmcp.tools.function_tool import FunctionTool
from mcp.types import ToolAnnotations

from ..schemas.models import ApiSchema, ToolDef
from ..utils.descriptions import generate_description

METHOD_VERBS = {
    "POST": "Create",
    "GET": "Get all",
    "PUT": "Update",
    "DELETE": "Delete",
}


class ToolFactory:
    """Generates FunctionTool instances from ApiSchema and registers them on a FastMCP server."""

    def register_tools(
        self,
        server: FastMCP,
        schema: ApiSchema,
        domain_tag: str,
        toolset_tag: str,
    ) -> list[str]:
        """Create tools for each active method and register on server.

        Returns list of registered tool names.
        """
        registered = []
        for method in schema.active_methods:
            tool_def = self._build_tool_def(schema, method, domain_tag, toolset_tag)
            fn = self._make_tool_fn(tool_def.endpoint, method)
            tool = FunctionTool.from_function(
                fn,
                name=tool_def.tool_name,
                title=tool_def.title,
                description=tool_def.description,
                tags=tool_def.tags,
                annotations=ToolAnnotations(
                    readOnlyHint=(method == "GET"),
                    destructiveHint=(method == "DELETE"),
                    idempotentHint=(method in ("GET", "PUT")),
                ),
            )
            # Override auto-generated parameters schema with our schema-based one
            tool.parameters = tool_def.parameters_schema
            server.add_tool(tool)
            registered.append(tool_def.tool_name)
        return registered

    def _build_tool_def(
        self,
        schema: ApiSchema,
        method: str,
        domain_tag: str,
        toolset_tag: str,
    ) -> ToolDef:
        access_tag = "read" if method == "GET" else "write"
        # Use api_path for tool name if it differs from endpoint (e.g., LCOM-GEN)
        name_source = schema.api_path or schema.endpoint
        tool_name = f"{method.lower()}_{name_source.replace('/', '_').replace('-', '_').lower()}"

        return ToolDef(
            tool_name=tool_name,
            endpoint=schema.api_path or schema.endpoint,
            method=method,
            title=f"{METHOD_VERBS.get(method, method)} {schema.title}",
            description=generate_description(schema, method),
            tags={domain_tag, access_tag, f"toolset:{toolset_tag}"},
            annotations={
                "readOnlyHint": method == "GET",
                "destructiveHint": method == "DELETE",
            },
            parameters_schema=self._build_params_schema(schema, method),
        )

    def _make_tool_fn(self, endpoint: str, method: str):
        """Create a closure function that calls the GEN NX API."""
        if method == "GET":

            async def tool_fn(*, ctx: Context) -> str:
                client = ctx.lifespan_context["api_client"]
                result = await client.get(endpoint)
                return json.dumps(result, ensure_ascii=False, indent=2)

        elif method == "DELETE":

            async def tool_fn(Assign: list, *, ctx: Context) -> str:
                client = ctx.lifespan_context["api_client"]
                result = await client.delete(endpoint, {"Assign": Assign})
                return json.dumps(result, ensure_ascii=False, indent=2)

        else:  # POST, PUT

            async def tool_fn(Assign: dict, *, ctx: Context) -> str:
                client = ctx.lifespan_context["api_client"]
                result = await client.request(
                    method, endpoint, {"Assign": Assign}
                )
                return json.dumps(result, ensure_ascii=False, indent=2)

        # Set a meaningful name for debugging
        tool_fn.__name__ = f"{method.lower()}_{endpoint.replace('/', '_').lower()}"
        tool_fn.__qualname__ = tool_fn.__name__
        return tool_fn

    def _build_params_schema(self, schema: ApiSchema, method: str) -> dict:
        """Build JSON Schema for tool parameters based on API schema and method."""
        if method == "GET":
            return {"type": "object", "properties": {}}

        if method == "DELETE":
            return {
                "type": "object",
                "properties": {
                    "Assign": {
                        "type": "array",
                        "items": _delete_item_type(schema),
                        "description": f"List of {schema.title} IDs to delete",
                    }
                },
                "required": ["Assign"],
            }

        # POST / PUT
        assign_schema = self._build_assign_schema(schema, method)
        return {
            "type": "object",
            "properties": {
                "Assign": assign_schema,
            },
            "required": ["Assign"],
        }

    def _build_assign_schema(self, schema: ApiSchema, method: str) -> dict:
        """Build the Assign parameter schema from the API's json_schema."""
        raw = schema.json_schema

        # If the schema has a single top-level key matching the endpoint suffix,
        # use its properties as the value schema for a dict keyed by ID
        endpoint_key = schema.endpoint.split("/")[-1]
        if endpoint_key in raw:
            inner = raw[endpoint_key]
            props = inner.get("properties", {})
            value_schema = _simplify_properties(props)
            desc = f"{schema.title} data keyed by ID."
            example = _get_first_example(schema.examples)
            if example:
                desc += f" Example: {json.dumps(example, ensure_ascii=False)}"
            return {
                "type": "object",
                "description": desc,
                "additionalProperties": value_schema,
            }

        # For schemas with multiple sub-type keys (SECT, THIK, LCOM),
        # describe available sub-types
        if len(raw) > 1:
            sub_types = [k for k in raw.keys() if not k.startswith("$")]
            desc = (
                f"{schema.title} data keyed by ID. "
                f"Available sub-types: {', '.join(sub_types)}. "
                f"See GEN NX documentation for sub-type specific fields."
            )
            # Use the first sub-type's properties as representative
            first_key = sub_types[0] if sub_types else None
            if first_key and "properties" in raw[first_key]:
                value_schema = _simplify_properties(raw[first_key]["properties"])
            else:
                value_schema = {"type": "object"}
            example = _get_first_example(schema.examples)
            if example:
                desc += f" Example: {json.dumps(example, ensure_ascii=False)}"
            return {
                "type": "object",
                "description": desc,
                "additionalProperties": value_schema,
            }

        # Fallback: raw schema as-is (for doc/* APIs that use Argument pattern)
        if "$schema" in raw:
            # Top-level schema (doc/* pattern)
            props = raw.get("properties", {})
            if "Argument" in props:
                return props["Argument"]
            return {"type": "object", "description": f"{schema.title} data"}

        # Single key that doesn't match endpoint
        keys = [k for k in raw.keys() if not k.startswith("$")]
        if keys:
            inner = raw[keys[0]]
            props = inner.get("properties", {})
            value_schema = _simplify_properties(props)
            return {
                "type": "object",
                "description": f"{schema.title} data keyed by ID.",
                "additionalProperties": value_schema,
            }

        return {"type": "object", "description": f"{schema.title} data"}


def _simplify_properties(props: dict) -> dict:
    """Convert a JSON Schema properties dict into a simplified value schema."""
    if not props:
        return {"type": "object"}
    simplified = {}
    for key, val in props.items():
        entry: dict[str, Any] = {"type": val.get("type", "string")}
        if "description" in val:
            entry["description"] = val["description"]
        if "properties" in val:
            entry["properties"] = {
                k: {"type": v.get("type", "string")}
                for k, v in val["properties"].items()
            }
            entry["type"] = "object"
        simplified[key] = entry
    return {"type": "object", "properties": simplified}


def _delete_item_type(schema: ApiSchema) -> dict:
    """Determine the type for DELETE array items (usually integer IDs or string keys)."""
    # Most db/* APIs use integer keys (node numbers, element numbers, etc.)
    # Check examples to determine
    for ex_data in schema.examples.values():
        assign = ex_data.get("Assign", {})
        if isinstance(assign, dict):
            for key in assign.keys():
                try:
                    int(key)
                    return {"type": "integer"}
                except (ValueError, TypeError):
                    return {"type": "string"}
    return {"type": "integer"}


def _get_first_example(examples: dict) -> dict | None:
    """Extract the first example's Assign value."""
    for ex_data in examples.values():
        if isinstance(ex_data, dict):
            assign = ex_data.get("Assign")
            if assign is not None:
                # Truncate large examples
                if isinstance(assign, dict) and len(assign) > 2:
                    keys = list(assign.keys())[:2]
                    return {k: assign[k] for k in keys}
                return assign
    return None
