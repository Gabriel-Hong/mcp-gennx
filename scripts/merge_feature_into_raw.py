"""Merge GEN NX Feature documentation into mcp-gennx raw/*.json schemas.

Reads external sources:
  - <api-data-dir>/api_to_feature_mapping_v3.json  (endpoint -> feature_label)
  - <api-data-dir>/GENNX_Feature/_index.json       ("<label> ↗" -> article_id)
  - <api-data-dir>/GENNX_Feature/<article_id>.json (Feature content)

For each base raw/*.json in mcp-gennx, injects 4 new fields:
  - description    : Korean fallback from descriptions.py, else Feature.sections.function
  - feature_name   : Feature.feature_name (with trailing " ↗" stripped)
  - menu_path      : parsed from Feature.sections.call (bracketed tokens joined by " > ")
  - usage          : Feature.sections.input + optional Note block

Writes outputs to:
  - <api-data-dir>/raw/<filename>.json       (SSOT copy outside repo)
  - <mcp-gennx>/src/mcp_gennx/schemas/raw/    (in-place update for runtime)
  - unmapped_report.md in both raw dirs

This is a one-time migration tool; rerun is safe (idempotent).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

# Korean-annotated feature descriptions for the original 40 endpoints.
# Vendored here so this migration tool is self-contained and can be re-run
# without depending on internal mcp_gennx modules.
FEATURE_DESCRIPTIONS: dict[str, str] = {
    "db/NODE": "nodes (절점) - define geometry points in 3D space",
    "db/ELEM": "elements (요소) - connect nodes to form structural members",
    "db/MATL": "material properties (재료) - define material behavior",
    "db/SECT": "section properties (단면) - define cross-section geometry",
    "db/THIK": "thickness (두께) - define plate/shell thickness",
    "db/CONS": "boundary conditions (지점조건) - define supports and constraints",
    "db/NSPR": "nodal springs (절점스프링) - define spring supports at nodes",
    "db/STLD": "static load cases (정적하중 케이스) - define load case names",
    "db/BODF": "body forces / self-weight (자중) - define gravity loads",
    "db/CNLD": "concentrated nodal loads (절점하중) - apply forces at nodes",
    "db/BMLD": "beam loads (보하중) - apply distributed loads on beams",
    "db/SPLC": "response spectrum load cases (응답스펙트럼 하중 케이스) - define response spectrum load cases for seismic/dynamic analysis",
    "db/LCOM": "load combinations (하중조합) - combine load cases with factors",
    "db/LCOM-GEN": "general load combinations (일반 하중조합) - combine load cases for general analysis",
    "db/LCOM-CONC": "concrete design load combinations (콘크리트 설계 하중조합)",
    "db/LCOM-STEEL": "steel design load combinations (강재 설계 하중조합)",
    "db/LCOM-SRC": "SRC design load combinations (SRC 설계 하중조합)",
    "db/LCOM-STLCOMP": "composite steel girder design load combinations (합성거더 설계 하중조합)",
    "db/LCOM-SEISMIC": "seismic design load combinations (내진 설계 하중조합)",
    "db/EIGV": "eigenvalue analysis parameters (고유치해석) - set modal analysis options",
    "db/NMAS": "nodal masses (절점질량) - assign masses at nodes",
    "db/GRUP": "structure groups (구조그룹) - organize elements into groups",
    "db/BNGR": "boundary groups (경계그룹) - organize boundary conditions",
    "db/SKEW": "skew coordinate systems (경사좌표계) - define local coordinate systems",
    "db/STOR": "story data (층 정보) - define building stories",
    "db/GSPR": "general springs (일반스프링) - define spring elements",
    "db/ELNK": "elastic links (탄성링크) - define elastic link elements",
    "db/RIGD": "rigid links (강체링크) - define rigid link constraints",
    "db/FRLS": "beam end releases (보 단부 해제) - release beam end forces",
    "db/OFFS": "beam offsets (보 오프셋) - define beam axis offsets",
    "db/MCON": "linear constraints (선형구속) - define multi-point constraints",
    "db/PRES": "pressure loads (압력하중) - apply pressure on surfaces",
    "db/PSLT": "pressure load types (압력하중 타입) - define pressure load types",
    "db/ETMP": "element temperatures (요소온도) - assign temperature to elements",
    "db/GTMP": "temperature gradients (온도경사) - define temperature gradients",
    "db/ACTL": "analysis control (해석 제어) - set analysis control parameters",
    "db/BUCK": "buckling analysis (좌굴해석) - set buckling analysis options",
    "db/PDEL": "P-Delta analysis (P-Delta) - set P-Delta analysis options",
    "db/NLCT": "nonlinear analysis (비선형해석) - set nonlinear analysis options",
    "db/UNIT": "unit system (단위계) - get/set the unit system",
    "db/STYP": "structure type (구조물 타입) - get/set the structure type",
    "doc/ANAL": "perform structural analysis (구조해석 수행) - run analysis on the current model",
}


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API_DATA_DIR = Path(
    r"C:\Users\hjm0830\OneDrive - MIDAS\바탕 화면\MIDAS\01_Study\PyTorch\API_Data"
)
DEFAULT_BASE_RAW = REPO_ROOT / "src" / "mcp_gennx" / "schemas" / "raw"

# Preferred order of keys in output JSON
OUTPUT_KEY_ORDER = [
    "endpoint",
    "api_path",
    "title",
    "url",
    "input_uri",
    "active_methods",
    "description",
    "feature_name",
    "menu_path",
    "usage",
    "json_schema",
    "examples",
    "tables",
    "menu_name",
]

ARROW_SUFFIX = " ↗"


# ---------------------------------------------------------------------------
# Field extraction helpers
# ---------------------------------------------------------------------------

_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


def parse_menu_path(call_text: str) -> str:
    """Extract menu path from Feature.sections.call.

    Examples:
        "From the Main Menu select [Node/Element] tab > [General] group > [Create] > [Create Node]"
        -> "[Node/Element] > [General] > [Create] > [Create Node]"

        "From the Main Menu select [File] > [New Project] OR Click the New Button..."
        -> "[File] > [New Project]"  (only first path before OR)
    """
    if not call_text:
        return ""
    first_path = re.split(r"\s+OR\s+", call_text, maxsplit=1)[0]
    tokens = _BRACKET_RE.findall(first_path)
    if not tokens:
        return ""
    return " > ".join(f"[{t.strip()}]" for t in tokens)


def build_usage(sections: dict) -> str:
    """Combine input + note sections into a single usage string."""
    parts: list[str] = []
    input_text = (sections.get("input") or "").strip()
    note_text = (sections.get("note") or "").strip()
    if input_text:
        parts.append(input_text)
    if note_text:
        parts.append(f"Note: {note_text}")
    return "\n\n".join(parts)


def strip_arrow(label: str) -> str:
    """Remove trailing ' ↗' from a Feature label."""
    if not label:
        return ""
    return label[: -len(ARROW_SUFFIX)] if label.endswith(ARROW_SUFFIX) else label


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

class MergeContext:
    """Holds loaded indices and lookups."""

    def __init__(self, api_data_dir: Path):
        self.api_data_dir = api_data_dir

        mapping_path = api_data_dir / "api_to_feature_mapping_v3.json"
        if not mapping_path.exists():
            raise FileNotFoundError(f"Mapping file not found: {mapping_path}")
        self.mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

        feature_index_path = api_data_dir / "GENNX_Feature" / "_index.json"
        if not feature_index_path.exists():
            raise FileNotFoundError(
                f"Feature index not found: {feature_index_path}"
            )
        feature_index = json.loads(feature_index_path.read_text(encoding="utf-8"))
        # Normalize "Create Nodes ↗" -> "Create Nodes" for lookup
        self.label_to_article: dict[str, str] = {
            strip_arrow(label): article_id
            for label, article_id in feature_index.items()
        }

        self.feature_dir = api_data_dir / "GENNX_Feature"
        self._feature_cache: dict[str, dict | None] = {}

    def load_feature(self, article_id: str) -> dict | None:
        if article_id in self._feature_cache:
            return self._feature_cache[article_id]
        path = self.feature_dir / f"{article_id}.json"
        if not path.exists():
            self._feature_cache[article_id] = None
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._feature_cache[article_id] = data
            return data
        except json.JSONDecodeError:
            self._feature_cache[article_id] = None
            return None


def _resolve_feature(endpoint: str, ctx: MergeContext) -> tuple[dict | None, str]:
    """Return (feature_data, failure_reason). feature_data is None on failure."""
    feature_label = ctx.mapping.get(endpoint)
    if not feature_label:
        return None, f"endpoint not in api_to_feature_mapping_v3.json"

    article_id = ctx.label_to_article.get(feature_label)
    if not article_id:
        return None, f"feature label '{feature_label}' not in Feature/_index.json"

    feature_data = ctx.load_feature(article_id)
    if feature_data is None:
        return None, f"Feature/{article_id}.json missing or invalid"

    return feature_data, ""


def merge_one(base_data: dict, ctx: MergeContext) -> tuple[dict, str | None]:
    """Inject 4 fields into base_data. Returns (merged_data, failure_reason)."""
    endpoint = base_data.get("endpoint", "")

    # Resolve via mapping
    feature_data, failure = _resolve_feature(endpoint, ctx)

    # description: Korean fallback wins, otherwise Feature.sections.function
    korean_desc = FEATURE_DESCRIPTIONS.get(endpoint, "")
    sub_path = base_data.get("api_path") or ""
    if not korean_desc and sub_path:
        korean_desc = FEATURE_DESCRIPTIONS.get(sub_path, "")

    if feature_data:
        sections = feature_data.get("sections", {}) or {}
        feature_name = strip_arrow(feature_data.get("feature_name", ""))
        menu_path = parse_menu_path(sections.get("call", "") or "")
        usage = build_usage(sections)
        description = korean_desc or (sections.get("function") or "").strip()
    else:
        feature_name = ""
        menu_path = ""
        usage = ""
        description = korean_desc

    # Inject fields
    base_data["description"] = description
    base_data["feature_name"] = feature_name
    base_data["menu_path"] = menu_path
    base_data["usage"] = usage

    return base_data, failure


def reorder_keys(data: dict) -> "OrderedDict[str, object]":
    """Reorder dict keys to OUTPUT_KEY_ORDER, then append unknowns."""
    out: OrderedDict[str, object] = OrderedDict()
    for key in OUTPUT_KEY_ORDER:
        if key in data:
            out[key] = data[key]
    for key, value in data.items():
        if key not in out:
            out[key] = value
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(
    api_data_dir: Path,
    base_raw_dir: Path,
    out_api_data_raw: Path,
    out_mcp_raw: Path | None,
    dry_run: bool,
) -> int:
    ctx = MergeContext(api_data_dir)

    base_files = sorted(base_raw_dir.glob("*.json"))
    if not base_files:
        print(f"ERROR: no JSON files found under {base_raw_dir}", file=sys.stderr)
        return 1

    if not dry_run:
        out_api_data_raw.mkdir(parents=True, exist_ok=True)
        if out_mcp_raw is not None:
            out_mcp_raw.mkdir(parents=True, exist_ok=True)

    success_count = 0
    failure_records: list[dict[str, str]] = []
    empty_desc_records: list[dict[str, str]] = []

    for base_file in base_files:
        try:
            base_data = json.loads(base_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failure_records.append({
                "endpoint": "(parse error)",
                "file": base_file.name,
                "reason": f"base JSON parse failed: {exc}",
            })
            continue

        endpoint = base_data.get("endpoint", "")
        merged, failure = merge_one(base_data, ctx)
        ordered = reorder_keys(merged)

        if failure:
            failure_records.append({
                "endpoint": endpoint,
                "file": base_file.name,
                "reason": failure,
            })
        else:
            success_count += 1

        if not merged["description"]:
            empty_desc_records.append({
                "endpoint": endpoint,
                "file": base_file.name,
            })

        if not dry_run:
            payload = json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"
            (out_api_data_raw / base_file.name).write_text(payload, encoding="utf-8")
            if out_mcp_raw is not None:
                (out_mcp_raw / base_file.name).write_text(payload, encoding="utf-8")

    # Reports
    total = len(base_files)
    print(f"Processed {total} files")
    print(f"  - mapped successfully : {success_count}")
    print(f"  - mapping failures    : {len(failure_records)}")
    print(f"  - empty description   : {len(empty_desc_records)}")

    report_lines = [
        "# Unmapped / Incomplete raw schemas",
        "",
        f"- Total files processed: **{total}**",
        f"- Mapped successfully  : **{success_count}**",
        f"- Mapping failures     : **{len(failure_records)}**",
        f"- Empty description    : **{len(empty_desc_records)}**",
        "",
        "## Mapping failures (no Feature content injected)",
        "",
    ]
    if failure_records:
        report_lines.append("| endpoint | file | reason |")
        report_lines.append("|---|---|---|")
        for rec in failure_records:
            report_lines.append(
                f"| `{rec['endpoint']}` | `{rec['file']}` | {rec['reason']} |"
            )
    else:
        report_lines.append("_(none)_")
    report_lines.append("")
    report_lines.append("## Empty description (no Korean fallback nor Feature.function)")
    report_lines.append("")
    if empty_desc_records:
        report_lines.append("| endpoint | file |")
        report_lines.append("|---|---|")
        for rec in empty_desc_records:
            report_lines.append(f"| `{rec['endpoint']}` | `{rec['file']}` |")
    else:
        report_lines.append("_(none)_")
    report_lines.append("")
    report_lines.append("## Suggested next steps")
    report_lines.append("")
    report_lines.append(
        "- Add missing endpoint mappings to `api_to_feature_mapping_v3.json`."
    )
    report_lines.append(
        "- For multi-merged endpoints (db/SECT, db/THIK), sub-variant features can be "
        "wired via `GENNX_API_Schema/_index.json` nested entries."
    )

    report_text = "\n".join(report_lines) + "\n"

    if not dry_run:
        (out_api_data_raw / "unmapped_report.md").write_text(
            report_text, encoding="utf-8"
        )
        if out_mcp_raw is not None:
            (out_mcp_raw / "unmapped_report.md").write_text(
                report_text, encoding="utf-8"
            )
        print(f"\nReport written to {out_api_data_raw / 'unmapped_report.md'}")
        if out_mcp_raw is not None:
            print(f"Report written to {out_mcp_raw / 'unmapped_report.md'}")
    else:
        print("\n--- unmapped_report.md (dry-run) ---")
        print(report_text)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-data-dir",
        type=Path,
        default=DEFAULT_API_DATA_DIR,
        help="Root of GENNX_API_Schema/GENNX_Feature/api_to_feature_mapping_v3.json",
    )
    parser.add_argument(
        "--base-raw-dir",
        type=Path,
        default=DEFAULT_BASE_RAW,
        help="mcp-gennx base raw/*.json directory",
    )
    parser.add_argument(
        "--out-api-data-raw",
        type=Path,
        default=None,
        help="Output dir under API_Data (default: <api-data-dir>/raw)",
    )
    parser.add_argument(
        "--out-mcp-raw",
        type=Path,
        default=DEFAULT_BASE_RAW,
        help="Output dir in mcp-gennx (default: in-place overwrite of base-raw-dir)",
    )
    parser.add_argument(
        "--no-write-mcp",
        action="store_true",
        help="Skip writing to mcp-gennx raw dir (only update API_Data)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files; print mapping summary only",
    )
    args = parser.parse_args(argv)

    out_api_data_raw = args.out_api_data_raw or (args.api_data_dir / "raw")
    out_mcp_raw = None if args.no_write_mcp else args.out_mcp_raw

    return run(
        api_data_dir=args.api_data_dir,
        base_raw_dir=args.base_raw_dir,
        out_api_data_raw=out_api_data_raw,
        out_mcp_raw=out_mcp_raw,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
