"""Auto-generate tool descriptions from API schemas.

Descriptions, feature names, menu paths and usage notes live in the
raw/*.json files (single source of truth). This module composes the final
LLM-facing description string from those fields.

Long-form ``usage`` text is NOT inlined into descriptions; it is exposed as
an MCP resource (see ``servers/feature_docs.py``) so the LLM only pays its
token cost when actively reading it.
"""

from __future__ import annotations

from ..schemas.models import ApiSchema
from ..servers.feature_docs import resource_uri_for

METHOD_VERBS = {
    "POST": "Create",
    "GET": "Get all",
    "PUT": "Update",
    "DELETE": "Delete",
}


def generate_description(schema: ApiSchema, method: str) -> str:
    """Generate a tool description for an API method.

    Layout::

        {verb} {feature} in GEN NX. [(GUI: "<name>") Menu: <path>.]
        {method-specific suffix}
        [See schema for parameter details.]
        [Docs: gennx://feature/<slug>]   (POST/PUT only, when usage exists)
    """
    verb = METHOD_VERBS.get(method, method)
    feature = schema.description or schema.title
    desc = f"{verb} {feature} in GEN NX."

    if method in ("POST", "PUT"):
        if schema.feature_name:
            desc += f' (GUI: "{schema.feature_name}")'
        if schema.menu_path:
            desc += f" Menu: {schema.menu_path}."

    if method == "GET":
        desc += " Returns all existing data."
    elif method == "POST":
        desc += " Provide data in the Assign parameter."
    elif method == "PUT":
        desc += " Provide updated data in the Assign parameter."
    elif method == "DELETE":
        desc += " Provide a list of IDs to delete in the Assign parameter."

    if schema.examples and method in ("POST", "PUT"):
        desc += " See schema for parameter details."

    endpoint = schema.api_path or schema.endpoint
    if schema.usage and method in ("POST", "PUT"):
        desc += f" Docs: {resource_uri_for(endpoint)}"

    return desc
