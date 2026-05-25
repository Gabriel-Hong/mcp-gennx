"""Expose feature/usage documentation as MCP resources.

Long-form ``usage`` text used to be embedded in every POST/PUT tool
description, which inflated the LLM's tool-list context to ~40K tokens.
That data now lives behind a template resource so the LLM only pays the
token cost when it actively reads the doc.

URI pattern: ``gennx://feature/{endpoint_slug}`` where ``endpoint_slug`` is
the endpoint with ``/`` replaced by ``_`` and lowercased (matches the
file-naming convention used in ``schemas/raw/``).
"""

from __future__ import annotations

from fastmcp import FastMCP

from ..schemas.registry import SchemaRegistry

URI_TEMPLATE = "gennx://feature/{endpoint_slug}"


def endpoint_to_slug(endpoint: str) -> str:
    """Convert ``db/NODE`` -> ``db_node`` (matches raw/*.json filename stem)."""
    return endpoint.replace("/", "_").replace("-", "_").lower()


def resource_uri_for(endpoint: str) -> str:
    return f"gennx://feature/{endpoint_to_slug(endpoint)}"


def _render(endpoint: str, schema) -> str:
    """Render an ApiSchema's feature docs as Markdown."""
    lines: list[str] = [f"# {schema.title} (`{endpoint}`)", ""]
    if schema.description:
        lines += [schema.description, ""]
    if schema.feature_name:
        lines.append(f"**GUI feature**: {schema.feature_name}")
    if schema.menu_path:
        lines.append(f"**Menu path**: {schema.menu_path}")
    if schema.feature_name or schema.menu_path:
        lines.append("")
    if schema.usage:
        lines += ["## Usage", "", schema.usage, ""]
    return "\n".join(lines).rstrip() + "\n"


def register_feature_resources(server: FastMCP, registry: SchemaRegistry) -> None:
    """Mount the feature-doc template resource on the given server."""
    slug_to_endpoint = {
        endpoint_to_slug(ep): ep for ep in registry.list_endpoints()
    }

    @server.resource(
        URI_TEMPLATE,
        name="gennx_feature_docs",
        title="GEN NX feature documentation",
        description=(
            "Full GUI feature description, menu path and usage notes for an "
            "API endpoint. Slug is `<group>_<name>` lowercased "
            "(e.g. `db_node`, `doc_new`, `view_capture`)."
        ),
        mime_type="text/markdown",
        tags={"docs"},
    )
    def feature_docs(endpoint_slug: str) -> str:
        endpoint = slug_to_endpoint.get(endpoint_slug.lower())
        if endpoint is None:
            available = ", ".join(sorted(slug_to_endpoint)[:10])
            return (
                f"# Unknown endpoint slug: `{endpoint_slug}`\n\n"
                f"Available slugs include: {available}, ...\n"
            )
        schema = registry.get_schema(endpoint)
        if schema is None:
            return f"# No schema registered for `{endpoint}`\n"
        return _render(endpoint, schema)
