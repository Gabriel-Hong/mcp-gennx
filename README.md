# mcp-gennx

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP 3.x](https://img.shields.io/badge/FastMCP-3.x-green.svg)](https://github.com/jlowin/fastmcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Domain-driven MCP server that exposes GEN NX structural engineering REST APIs via the Model Context Protocol.

## Features

- **Dynamic Tool Generation** — Tools are generated at startup from JSON schema files. No code generation step; add a schema file, register the endpoint, and the tool appears.
- **Domain-Driven Sub-Servers** — 5 sub-servers (modeling, boundary, loads, analysis, project) keep tools organized by structural engineering domain.
- **Toolset Filtering** — Control which tools are exposed via environment variables: 87 tools (default), 159 tools (all), or GET-only (read-only mode).

## Architecture

```
Claude / GPT / Cursor
    │  MCP Protocol (stdio)
    ▼
Main FastMCP ("gennx")
    ├── modeling    (9 endpoints  · nodes, elements, materials, sections …)
    ├── boundary    (8 endpoints  · constraints, springs, rigid links …)
    ├── loads       (14 endpoints · load cases, nodal/beam loads, LCOM 6 sub-types …)
    ├── analysis    (6 endpoints  · eigenvalue, buckling, pushover …)
    └── project     (9 endpoints  · open/save/close, analysis run, view capture …)
              │
         GennxApiClient (httpx async)
              │
         GEN NX REST API (localhost:8080)
```

## Dynamic Tool Pipeline

```
schemas/raw/*.json
    → SchemaRegistry (load & merge 65 schema files → 46 endpoints)
    → ToolFactory (generate closure per method)
    → FunctionTool (name, description, JSON Schema params, annotations)
    → FastMCP.add_tool()
```

Each endpoint produces up to 4 tools — one per HTTP method:

| Method | Tool prefix | Example | Behavior |
|--------|-------------|---------|----------|
| POST | `post_` | `post_db_node` | Create records |
| GET | `get_` | `get_db_node` | Read all records |
| PUT | `put_` | `put_db_node` | Update records |
| DELETE | `delete_` | `delete_db_node` | Delete by ID list |

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Configure

Copy `.env.example` to `.env` and set `GENNX_API_BASE_URL` to your running GEN NX instance:

```bash
cp .env.example .env
# edit .env — default is http://localhost:8080
```

### 3. Register with Claude Code

```bash
claude mcp add gennx -- mcp-gennx
```

Or add manually to your MCP client config:

```json
{
  "mcpServers": {
    "gennx": {
      "command": "mcp-gennx",
      "args": [],
      "env": {
        "GENNX_API_BASE_URL": "http://localhost:8080"
      }
    }
  }
}
```

### 4. Use

```
You: Create a simple beam model with 3 nodes at (0,0,0), (5,0,0), (10,0,0)
AI:  [calls post_db_node with Assign: {"1": {"X":0,"Y":0,"Z":0}, "2": {"X":5,...}, ...}]
     Created 3 nodes successfully.

You: Connect them with beam elements
AI:  [calls post_db_elem with Assign: {"1": {"TYPE":"BEAM","MATL":1,"SECT":1,"NODE":[1,2]}, ...}]
     Created 2 beam elements.
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GENNX_API_BASE_URL` | `http://localhost:8080` | GEN NX REST API base URL |
| `GENNX_API_TIMEOUT` | `30.0` | API request timeout (seconds) |
| `TOOLSETS` | `default` | Toolset selection (see below) |
| `READ_ONLY` | `false` | When `true`, only GET tools are exposed |
| `LOG_LEVEL` | `INFO` | Logging level |

### Toolset Examples

```bash
TOOLSETS=default                  # 87 tools — core endpoints only
TOOLSETS=all                      # 159 tools — all endpoints
TOOLSETS=default,loads_advanced   # default + advanced load types
TOOLSETS=modeling_core            # only core modeling tools (20 tools)
READ_ONLY=true                   # expose only GET tools
```

## Project Structure

```
mcp-gennx/
├── pyproject.toml
├── .env.example
└── src/mcp_gennx/
    ├── __init__.py              # Entry point (main)
    ├── server.py                # Server assembly & toolset filtering
    ├── config.py                # GennxSettings (pydantic-settings)
    ├── client/
    │   └── gennx_client.py      # Async HTTP client for GEN NX API
    ├── schemas/
    │   ├── registry.py          # SchemaRegistry — loads & merges JSON schemas
    │   ├── models.py            # ApiSchema, ToolDef data models
    │   └── raw/                 # 65 JSON schema files
    ├── servers/
    │   ├── modeling.py          # Nodes, elements, materials, sections
    │   ├── boundary.py          # Constraints, springs, rigid links
    │   ├── loads.py             # Load cases, forces, combinations (LCOM)
    │   ├── analysis.py          # Eigenvalue, buckling, nonlinear
    │   └── project.py           # File ops, analysis run, view capture
    ├── tools/
    │   └── factory.py           # ToolFactory — dynamic tool generation
    └── utils/
        └── descriptions.py      # Auto-generated tool descriptions
```

## Supported APIs

### Tier 1 — Core (default toolset)

| Domain | Endpoint | Description |
|--------|----------|-------------|
| modeling | `db/NODE` | Nodes (절점) — geometry points |
| modeling | `db/ELEM` | Elements (요소) — beams, plates, solids |
| modeling | `db/MATL` | Materials (재료) |
| modeling | `db/SECT` | Sections (단면) — 11 sub-types |
| modeling | `db/THIK` | Thickness (두께) — plate thickness |
| boundary | `db/CONS` | Constraints (지점조건) — supports |
| boundary | `db/NSPR` | Nodal Springs (절점스프링) |
| loads | `db/STLD` | Static Load Cases (정적하중) |
| loads | `db/BODF` | Body Forces (자중) |
| loads | `db/CNLD` | Concentrated Nodal Loads (절점하중) |
| loads | `db/BMLD` | Beam Loads (보하중) |
| loads | `db/LCOM-*` | Load Combinations (하중조합) — 6 sub-types |
| analysis | `db/EIGV` | Eigenvalue Analysis (고유치해석) |
| analysis | `db/NMAS` | Nodal Masses (절점질량) |

### Tier 2 — Advanced

| Domain | Endpoint | Description |
|--------|----------|-------------|
| modeling | `db/GRUP` | Structure Groups (구조그룹) |
| modeling | `db/BNGR` | Boundary Groups |
| modeling | `db/SKEW` | Local Coordinates (경사좌표계) |
| modeling | `db/STOR` | Stories (층 정보) |
| boundary | `db/GSPR` | General Springs |
| boundary | `db/ELNK` | Elastic Links (탄성링크) |
| boundary | `db/RIGD` | Rigid Links (강체링크) |
| boundary | `db/FRLS` | Floor Releases |
| boundary | `db/OFFS` | Beam Offsets (보 오프셋) |
| boundary | `db/MCON` | Multi-point Constraints |
| loads | `db/PRES` | Pressure Loads (압력하중) |
| loads | `db/PSLT` | Prescribed Displacements |
| loads | `db/ETMP` | Element Temperatures |
| loads | `db/GTMP` | Gradient Temperatures |
| analysis | `db/ACTL` | Analysis Control (해석 제어) |
| analysis | `db/BUCK` | Buckling Analysis (좌굴해석) |
| analysis | `db/PDEL` | P-Delta Analysis |
| analysis | `db/NLCT` | Nonlinear Control |
| project | `db/UNIT` | Unit System |
| project | `db/STYP` | Structure Type |

### Project Operations (manually registered)

| Tool | Description |
|------|-------------|
| `post_doc_anal` | Run analysis (standard or pushover) |
| `post_doc_new` | Create new project |
| `post_doc_open` | Open project file |
| `post_doc_save` | Save project |
| `post_doc_saveas` | Save project as new file |
| `post_doc_close` | Close project |
| `post_view_capture` | Capture current view as image |

## Development

### Run Tests

```bash
pip install -e ".[dev]"
pytest
```

### Adding a New API

1. Place the JSON schema file in `src/mcp_gennx/schemas/raw/`
2. Add the endpoint to the appropriate sub-server's `ENDPOINTS` dict:
   ```python
   # src/mcp_gennx/servers/modeling.py
   ENDPOINTS = {
       ...
       "db/NEW_ENDPOINT": {"tier": 2, "toolset": "modeling_advanced"},
   }
   ```
3. Restart the server — tools are generated automatically.

## License

MIT
