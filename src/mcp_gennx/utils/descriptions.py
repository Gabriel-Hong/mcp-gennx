"""Auto-generate tool descriptions from API schemas."""

from __future__ import annotations

from ..schemas.models import ApiSchema

METHOD_VERBS = {
    "POST": "Create",
    "GET": "Get all",
    "PUT": "Update",
    "DELETE": "Delete",
}

# Korean feature names for richer descriptions
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
}


def generate_description(schema: ApiSchema, method: str) -> str:
    """Generate a tool description for an API method."""
    verb = METHOD_VERBS.get(method, method)
    # Try api_path first (for sub-typed endpoints like LCOM-GEN), then endpoint
    feature = (
        FEATURE_DESCRIPTIONS.get(schema.api_path)
        or FEATURE_DESCRIPTIONS.get(schema.endpoint, schema.title)
    )

    desc = f"{verb} {feature} in GEN NX."

    if method == "GET":
        desc += " Returns all existing data."
    elif method == "POST":
        desc += " Provide data in the Assign parameter."
    elif method == "PUT":
        desc += " Provide updated data in the Assign parameter."
    elif method == "DELETE":
        desc += " Provide a list of IDs to delete in the Assign parameter."

    # Add example if available
    if schema.examples and method in ("POST", "PUT"):
        example_keys = list(schema.examples.keys())
        if example_keys:
            desc += f" See schema for parameter details."

    return desc
