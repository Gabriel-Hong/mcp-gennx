"""Load and index GEN NX API schemas from JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ApiSchema


def _extract_api_path(data: dict) -> str:
    """Extract the actual API path from input_uri field."""
    input_uri = data.get("input_uri", "")
    # Format: "{base url} + db/LCOM-GEN"
    if " + " in input_uri:
        return input_uri.split(" + ", 1)[1].strip()
    return data.get("endpoint", "")


class SchemaRegistry:
    """Loads raw/*.json schema files and indexes them by endpoint.

    For endpoints with sub-typed URIs (e.g., db/LCOM-GEN, db/LCOM-CONC),
    each sub-type is registered separately with its actual API path.
    For endpoints sharing a single URI (e.g., db/SECT), schemas are merged.
    """

    def __init__(self, schema_dir: Path):
        self._schemas: dict[str, ApiSchema] = {}
        self._load_all(schema_dir)

    def _load_all(self, schema_dir: Path) -> None:
        # Group files by endpoint to handle multi-file endpoints
        endpoint_files: dict[str, list[tuple[Path, dict]]] = {}
        for path in sorted(schema_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            endpoint = data.get("endpoint", "")
            if not endpoint:
                continue
            endpoint_files.setdefault(endpoint, []).append((path, data))

        for endpoint, items in endpoint_files.items():
            if len(items) == 1:
                self._load_single(items[0][1])
            else:
                self._load_multi(endpoint, items)

    def _load_single(self, data: dict) -> None:
        endpoint = data["endpoint"]
        api_path = _extract_api_path(data)
        self._schemas[endpoint] = ApiSchema(
            endpoint=endpoint,
            api_path=api_path,
            title=data.get("title", endpoint),
            active_methods=data.get("active_methods", []),
            json_schema=data.get("json_schema", {}),
            examples=data.get("examples", {}),
            tables=data.get("tables", []),
            description=data.get("description", ""),
            feature_name=data.get("feature_name", ""),
            menu_path=data.get("menu_path", ""),
            usage=data.get("usage", ""),
        )

    def _load_multi(self, endpoint: str, items: list[tuple[Path, dict]]) -> None:
        """Handle multi-file endpoints.

        If sub-types have different API paths (like LCOM-GEN, LCOM-CONC),
        register each as a separate schema entry.
        If they share the same path (like SECT), merge into one.
        """
        # Check if sub-types have different API paths
        api_paths = set()
        for _, data in items:
            api_paths.add(_extract_api_path(data))

        if len(api_paths) > 1:
            # Different URI per sub-type (e.g., LCOM) -> register each separately
            self._load_multi_separate(endpoint, items)
        else:
            # Same URI (e.g., SECT, THIK) -> merge into one schema
            self._load_multi_merged(endpoint, items)

    def _load_multi_separate(
        self, base_endpoint: str, items: list[tuple[Path, dict]]
    ) -> None:
        """Register each sub-type as a separate schema (e.g., db/LCOM-GEN)."""
        for _, data in items:
            api_path = _extract_api_path(data)
            self._schemas[api_path] = ApiSchema(
                endpoint=base_endpoint,
                api_path=api_path,
                title=data.get("title", base_endpoint),
                active_methods=data.get("active_methods", []),
                json_schema=data.get("json_schema", {}),
                examples=data.get("examples", {}),
                tables=data.get("tables", []),
                description=data.get("description", ""),
                feature_name=data.get("feature_name", ""),
                menu_path=data.get("menu_path", ""),
                usage=data.get("usage", ""),
            )

    def _load_multi_merged(
        self, endpoint: str, items: list[tuple[Path, dict]]
    ) -> None:
        """Merge sub-type schemas sharing the same URI (e.g., SECT)."""
        all_schemas: dict[str, dict] = {}
        all_examples: dict[str, dict] = {}
        all_tables: list = []
        methods: list[str] = []
        title = ""
        api_path = ""
        feature_name = ""
        menu_path = ""
        descriptions: list[str] = []
        usages: list[str] = []
        seen_descriptions: set[str] = set()

        for _, data in items:
            if not title:
                title = data.get("title", endpoint)
            if not methods:
                methods = data.get("active_methods", [])
            if not api_path:
                api_path = _extract_api_path(data)
            if not feature_name:
                feature_name = data.get("feature_name", "")
            if not menu_path:
                menu_path = data.get("menu_path", "")

            sub_desc = (data.get("description") or "").strip()
            if sub_desc and sub_desc not in seen_descriptions:
                descriptions.append(sub_desc)
                seen_descriptions.add(sub_desc)

            sub_usage = (data.get("usage") or "").strip()
            if sub_usage:
                sub_title_for_usage = data.get("title", "").strip()
                if sub_title_for_usage:
                    usages.append(f"[{sub_title_for_usage}] {sub_usage}")
                else:
                    usages.append(sub_usage)

            raw_schema = data.get("json_schema", {})
            all_schemas.update(raw_schema)

            sub_title = data.get("title", "")
            for ex_name, ex_data in data.get("examples", {}).items():
                key = f"{sub_title} - {ex_name}" if sub_title else ex_name
                all_examples[key] = ex_data

            all_tables.extend(data.get("tables", []))

        if " - " in title:
            title = title.split(" - ")[0].strip()

        merged_description = "\n- ".join(descriptions) if descriptions else ""
        if len(descriptions) > 1:
            merged_description = "- " + merged_description
        merged_usage = "\n\n".join(usages)

        self._schemas[endpoint] = ApiSchema(
            endpoint=endpoint,
            api_path=api_path,
            title=title,
            active_methods=methods,
            json_schema=all_schemas,
            examples=all_examples,
            tables=all_tables,
            description=merged_description,
            feature_name=feature_name,
            menu_path=menu_path,
            usage=merged_usage,
        )

    def get_schema(self, endpoint: str) -> ApiSchema | None:
        return self._schemas.get(endpoint)

    def list_endpoints(self) -> list[str]:
        return list(self._schemas.keys())
