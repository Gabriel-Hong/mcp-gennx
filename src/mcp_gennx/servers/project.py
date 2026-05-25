"""Project sub-server: doc/* operations, view/CAPTURE, db/UNIT, db/STYP."""

from __future__ import annotations

import json

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from ..schemas.registry import SchemaRegistry
from ..tools.factory import ToolFactory
from .feature_docs import resource_uri_for

# db/* endpoints handled by ToolFactory (GET/PUT only)
DB_ENDPOINTS = {
    "db/UNIT": {"tier": 2, "toolset": "project"},
    "db/STYP": {"tier": 2, "toolset": "project"},
}


def _desc(registry: SchemaRegistry, endpoint: str, fallback: str) -> str:
    """Resolve description from the raw schema, falling back to a hardcoded string.

    Long-form ``usage`` is NOT inlined — it lives behind an MCP resource.
    Tools that have usage docs get a `Docs:` pointer at the end so the LLM
    can fetch them on demand.
    """
    schema = registry.get_schema(endpoint)
    if schema is None or not schema.description:
        return fallback
    text = schema.description
    if schema.feature_name:
        text += f' (GUI: "{schema.feature_name}")'
    if schema.menu_path:
        text += f" Menu: {schema.menu_path}."
    if schema.usage:
        text += f" Docs: {resource_uri_for(endpoint)}"
    return text


def create_project_server(
    registry: SchemaRegistry, factory: ToolFactory
) -> FastMCP:
    server = FastMCP("project")

    # Register db/UNIT and db/STYP via factory
    for endpoint, meta in DB_ENDPOINTS.items():
        schema = registry.get_schema(endpoint)
        if schema:
            factory.register_tools(
                server, schema, "project", meta["toolset"]
            )

    # Manually register doc/* and view/CAPTURE tools
    _register_doc_tools(server, registry)
    _register_capture_tool(server, registry)

    return server


def _register_doc_tools(server: FastMCP, registry: SchemaRegistry) -> None:
    """Register doc/* tools manually (they don't follow the Assign pattern)."""

    @server.tool(
        name="post_doc_anal",
        title="Perform Analysis",
        description=_desc(
            registry,
            "doc/ANAL",
            (
                "Run structural analysis in GEN NX. "
                "Call with no arguments for standard analysis, "
                'or pass Argument={"TYPE": "Pushover"} for pushover analysis.'
            ),
        ),
        tags={"project", "write", "toolset:project"},
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def post_doc_anal(
        Argument: dict | None = None, *, ctx: Context
    ) -> str:
        client = ctx.lifespan_context["api_client"]
        payload = {"Argument": Argument} if Argument else {}
        result = await client.post("doc/ANAL", payload)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @server.tool(
        name="post_doc_new",
        title="New Project",
        description=_desc(
            registry, "doc/NEW", "Create a new empty project in GEN NX."
        ),
        tags={"project", "write", "toolset:project"},
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=True
        ),
    )
    async def post_doc_new(*, ctx: Context) -> str:
        client = ctx.lifespan_context["api_client"]
        result = await client.post("doc/NEW", {"Argument": {}})
        return json.dumps(result, ensure_ascii=False, indent=2)

    @server.tool(
        name="post_doc_open",
        title="Open Project",
        description=_desc(
            registry,
            "doc/OPEN",
            (
                "Open a project file in GEN NX. "
                'Provide the file path, e.g. "C:\\\\Projects\\\\model.mcb".'
            ),
        ),
        tags={"project", "write", "toolset:project"},
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=True
        ),
    )
    async def post_doc_open(file_path: str, *, ctx: Context) -> str:
        client = ctx.lifespan_context["api_client"]
        result = await client.post("doc/OPEN", {"Argument": file_path})
        return json.dumps(result, ensure_ascii=False, indent=2)

    @server.tool(
        name="post_doc_save",
        title="Save Project",
        description=_desc(
            registry, "doc/SAVE", "Save the current project in GEN NX."
        ),
        tags={"project", "write", "toolset:project"},
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=False, idempotentHint=True
        ),
    )
    async def post_doc_save(*, ctx: Context) -> str:
        client = ctx.lifespan_context["api_client"]
        result = await client.post("doc/SAVE", {"Argument": {}})
        return json.dumps(result, ensure_ascii=False, indent=2)

    @server.tool(
        name="post_doc_saveas",
        title="Save Project As",
        description=_desc(
            registry,
            "doc/SAVEAS",
            (
                "Save the current project to a new file path in GEN NX. "
                'Provide the target path, e.g. "C:\\\\Projects\\\\model_v2.mcb".'
            ),
        ),
        tags={"project", "write", "toolset:project"},
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=False
        ),
    )
    async def post_doc_saveas(file_path: str, *, ctx: Context) -> str:
        client = ctx.lifespan_context["api_client"]
        result = await client.post("doc/SAVEAS", {"Argument": file_path})
        return json.dumps(result, ensure_ascii=False, indent=2)

    @server.tool(
        name="post_doc_close",
        title="Close Project",
        description=_desc(
            registry, "doc/CLOSE", "Close the current project in GEN NX."
        ),
        tags={"project", "write", "toolset:project"},
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=True
        ),
    )
    async def post_doc_close(*, ctx: Context) -> str:
        client = ctx.lifespan_context["api_client"]
        result = await client.post("doc/CLOSE", {"Argument": {}})
        return json.dumps(result, ensure_ascii=False, indent=2)


def _register_capture_tool(server: FastMCP, registry: SchemaRegistry) -> None:
    """Register view/CAPTURE tool manually."""

    @server.tool(
        name="post_view_capture",
        title="Capture View",
        description=_desc(
            registry,
            "view/CAPTURE",
            (
                "Capture the current view as an image in GEN NX. "
                "Provide Argument with EXPORT_PATH (required), and optional: "
                "WIDTH, HEIGHT (pixels), SET_MODE ('pre'/'post'), "
                "ANGLE ({HORIZONTAL, VERTICAL}), SET_HIDDEN (bool)."
            ),
        ),
        tags={"project", "write", "toolset:project"},
        annotations=ToolAnnotations(
            readOnlyHint=True, destructiveHint=False
        ),
    )
    async def post_view_capture(
        Argument: dict, *, ctx: Context
    ) -> str:
        client = ctx.lifespan_context["api_client"]
        result = await client.post("view/CAPTURE", {"Argument": Argument})
        return json.dumps(result, ensure_ascii=False, indent=2)
