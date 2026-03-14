# GEN NX MCP Server 구축 계획

## Context

GEN NX의 AX(AI Experience) 적용을 위해, 상용 LLM(Claude, GPT 등)이 GEN NX의 270여 개 API를 MCP 프로토콜로 호출할 수 있는 서버를 구축한다. 이미 QLoRA로 fine-tuning된 Qwen2.5-1.5B 모델이 tool calling을 96.65% 정확도로 수행하므로, 이를 보조 라우터로 활용하는 구조도 포함한다.

**핵심 과제**: 234개 API × 평균 3개 HTTP 메서드 = ~700개 잠재 tool → LLM context window 관리가 핵심

**결정 사항**:
- 프로젝트 위치: `C:\MIDAS_Source\mcp-gennx` (별도 repo, 스키마 파일은 복사)
- GEN NX REST API: 이미 동작 중 → 즉시 통합 테스트 가능
- QLoRA 통합: Phase 4에서 별도 추가 (초기엔 MCP 서버 기본 구조에 집중)

---

## 1. 전체 아키텍처

```
Claude / GPT (Host LLM)
    ↓ MCP Protocol
Main MCP Server (FastMCP) — 게이트웨이 전용 (domain tool 없음)
    │
    │  [Phase 1: 전처리 + 해석 수행]  ← 지금 구현
    ├── modeling_mcp      (구조 모델링: NODE, ELEM, MATL, SECT, THIK 등)
    ├── boundary_mcp      (경계조건: CONS, NSPR, ELNK, RIGD 등)
    ├── loads_mcp          (하중: STLD, BODF, CNLD, BMLD, LCOM 등)
    ├── analysis_mcp       (해석제어: ACTL, ANAL, EIGV 등)
    └── project_mcp        (프로젝트: doc/NEW, OPEN, SAVE, UNIT 등)
    │
    │  [Phase 2+: 향후 확장] ← Python 모듈 미생성, 스키마만 보관
    │   moving_load, dynamic, construction, special,
    │   material, design, results, viz
    │
    + GennxApiClient       (GEN NX REST API HTTP 클라이언트)
    + SchemaRegistry       (필요한 스키마만 로딩)
```

### 설계 원칙: 필요한 것만 구현, 나머지는 확장 가능하게

1. **Phase 1에서 구현하는 sub-server: 5개** (전처리 ~ 해석 수행)
2. **Python 모듈 미생성**: results, viz, design 등 8개 sub-server는 아직 코드 없음
3. **스키마 파일도 선별 복사**: 40개 API 관련 스키마만 `raw/`에 포함
4. **확장 시**: 새 sub-server 모듈 추가 → `server.py`에 mount → 끝

### Phase 1 Sub-server 구성 (5개, 전처리+해석)

| Sub-server | Prefix | 주요 API | API 수 | Tool 수 | Tier |
|---|---|---|---|---|---|
| `modeling` | `modeling` | NODE, ELEM, MATL, SECT, THIK, GRUP, BNGR, SKEW, STOR | ~9 | ~27 | 1-2 |
| `boundary` | `boundary` | CONS, NSPR, GSPR, ELNK, RIGD, FRLS, OFFS, MCON | ~8 | ~24 | 1-2 |
| `loads` | `loads` | STLD, BODF, CNLD, BMLD, PRES, PSLT, ETMP, GTMP, LCOM | ~9 | ~27 | 1-2 |
| `analysis` | `analysis` | ACTL, ANAL, EIGV, BUCK, PDEL, NMAS, NLCT | ~7 | ~21 | 1-3 |
| `project` | `project` | doc/NEW, OPEN, SAVE, SAVEAS, CLOSE, UNIT, STYP | ~7 | ~21 | 2 |

**Phase 1 총합**: ~40 API, ~120 tools
**Toolset 기본 노출**: Tier-1 핵심 (~60 tools) → **모든 클라이언트에서 안전**

### 향후 확장 가능한 Sub-server (Phase 2+, 미구현)

| Sub-server | 시기 | 주요 API | API 수 |
|---|---|---|---|
| `moving_load` | 이동하중 필요 시 | LLAN*, MVHL*, MVLD*, MVCT* | ~23 |
| `dynamic` | 동적해석 필요 시 | THGC, THIS, SPFC, SPLC | ~13 |
| `construction` | 시공단계 필요 시 | STAG, CSCS, TDNT, ETFC~HHND | ~23 |
| `special` | 특수해석 필요 시 | POGD, SDVI, POSP | ~14 |
| `material` | 고급재료 필요 시 | FIMP, IMFM, EPMT, TDMT | ~10 |
| `design` | 설계 필요 시 | DCON, DSTL, MATD | ~10 |
| `results` | 후처리 필요 시 | post/TABLE, post/TEXT | ~5 |
| `viz` | 시각화 필요 시 | view/CAPTURE, DISPLAY, RESULTGRAPHIC | ~7 |

### Tool 수 관리: 클라이언트 제약 & Context Window 분석

**클라이언트별 하드 리밋 (조사 결과):**
| 클라이언트 | Tool 제한 | 비고 |
|---|---|---|
| Claude Desktop | ~100 | 초과 시 숨김 처리 |
| Cursor | 40 | 하드 리밋 |
| GitHub Copilot | 128 | 최대 활성화 수 |
| LLM 성능 저하 | 80~90 | 이 이상이면 tool 선택 정확도 하락 |

**실제 대규모 MCP 서버 사례:**
- Azure MCP: ~40 tools, Atlassian 공식: 25 tools, Composio: 100+ tools
- 단일 서버에 400+ tools를 직접 노출하는 사례는 없음

**Context Window 영향:**
| 시나리오 | 노출 Tool 수 | 스키마 토큰 (추정) | 적합 여부 |
|---|---|---|---|
| Default (Tier-1 + project) | ~60 | ~18K | 모든 클라이언트 OK |
| Default + 1-2 toolset 추가 | ~80 | ~24K | Claude/GPT OK, Cursor 초과 |
| 전체 (all) | ~451 | ~135K | **어떤 클라이언트에서도 불가** |
| **권장 운영 범위** | **40~80** | **12~24K** | **최적 (모든 클라이언트 호환)** |

### Tool 로딩 메커니즘 (FastMCP 동작 방식)

```
[서버 시작]
  └─ sub-server의 tool 함수가 Python 메모리에 등록 (가벼움, 문제없음)

[클라이언트가 tools/list 호출]
  └─ server.list_tools() 실행
       ├─ ① 등록된 tool 수집
       ├─ ② Visibility Transform 적용 (toolset 필터링)
       ├─ ③ Auth 필터링
       └─ ④ 활성 toolset의 tool만 반환 (예: 60개)
            → LLM은 이 60개만 인지, 나머지는 존재 자체를 모름

[LLM이 tool 호출]
  └─ 활성 tool만 호출 가능 (비활성 tool은 NotFoundError)
```

**핵심**: 서버는 등록된 tool을 메모리에 갖고 있지만, LLM에는 toolset 필터로 60~80개만 노출된다.
이것은 mcp-atlassian이 72+ tool을 갖고 있지만 `TOOLSETS=default`로 핵심 6개 toolset만 노출하는 것과 동일한 패턴이다.

**결론**:
- sub-server 분할은 **코드 조직화** 목적 (서버 안정성에 영향 없음)
- **tool 노출 수 제어**는 toolset 필터링이 담당 (서버가 아닌 LLM context가 병목)
- 기본 40~80개 이내로 운영하면 모든 클라이언트에서 안정적

---

## 2. Tool 설계 원칙

### 2.1 CRUD → 별도 Tool
각 HTTP 메서드를 별도 tool로 분리 (QLoRA 학습 데이터 형식과 일치):
- `post_db_node` (생성), `get_db_node` (조회), `put_db_node` (수정), `delete_db_node` (삭제)
- Tool 이름 규칙: `{method}_{endpoint_normalized}` (예: `post_db_elem`, `get_db_matl`)

### 2.2 Sub-type 처리 → 파라미터화
tool 수 폭발 방지를 위해 sub-type은 파라미터로 처리:
- `post_db_sect(sub_type="H", ...)` — 17개 단면 타입을 1개 tool로
- `post_results_table(table_type="DISPLACEMENT", ...)` — 91개 결과 타입을 1개 tool로
- `post_db_mvhl(code="default", ...)` — 국가별 차량 하중을 1개 tool로

### 2.3 Toolset 기반 Enable/Disable
mcp-atlassian 패턴을 따라 환경변수로 tool 그룹 제어:
```
TOOLSETS=default                    # Tier-1 + project (약 60개 tool)
TOOLSETS=default,advanced_moving    # + 이동하중
TOOLSETS=all                        # 전체 234 API
```

### 2.4 Default Toolset 전략
**LLM context window 부담 최소화**:
- 기본: Tier-1 (16 API, ~40 tools) + project (~20 tools) = **~60 tools만 노출**
- 필요 시 `list_available_toolsets` → `enable_toolset("moving_load")` 으로 확장
- 세션 단위로 활성 toolset 관리

---

## 3. 스키마 → Tool 자동 생성

### 핵심 컴포넌트

**SchemaRegistry** (`schemas/registry.py`):
- 서버 시작 시 Phase 1 API 스키마 (~40개) 로드
- endpoint별 인덱싱, sub-type 그룹핑
- `api_tier_assignment.json` 병합으로 tier 메타데이터 부착

**ToolFactory** (`tools/factory.py`):
- SchemaRegistry에서 각 `(endpoint, method)` 조합마다 tool 함수 생성
- JSON schema의 properties → Pydantic `Annotated[type, Field(description=...)]`로 변환
- 자동 생성된 docstring (title + properties + example)
- 함수 body: `GennxApiClient.{method}(endpoint, payload)` 위임

**생성 예시:**
```python
# ToolFactory가 db/NODE 스키마에서 자동 생성
@modeling_mcp.tool(
    tags={"modeling", "write", "toolset:modeling_core"},
    annotations={"title": "Create Nodes"}
)
async def post_db_node(
    assign: Annotated[dict, Field(
        description="Node data. Keys: node numbers, Values: {X, Y, Z} coordinates. "
                    "Example: {'1': {'X': 0, 'Y': 0, 'Z': 0}}"
    )],
    ctx: Context,
) -> str:
    """Create or add nodes to the structural model."""
    client = ctx.request_context.lifespan_context["api_client"]
    return await client.post("db/NODE", {"Assign": assign})
```

---

## 4. QLoRA 모델 통합 (Optional, Phase 4)

fine-tuning된 모델을 **"tool을 추천하는 tool"** 메타툴로 활용:

```python
@main_mcp.tool()
async def suggest_tools(query: str, ctx: Context) -> str:
    """자연어 설명을 받아 가장 적합한 GEN NX API tool을 추천합니다.
    구조공학 특화 fine-tuned 모델이 분류합니다."""
    qlora = ctx.request_context.lifespan_context["qlora_client"]
    return await qlora.classify(query)
```

- vLLM 서빙 (`scripts/07_serve_vllm.py`) 엔드포인트 연동
- 상용 LLM이 234개 중 어떤 API를 호출해야 할지 모를 때 보조적으로 사용
- `QLORA_ROUTER_ENABLED=true` 환경변수로 활성화

---

## 5. 프로젝트 구조

```
C:\MIDAS_Source\mcp-gennx\
├── pyproject.toml
├── .env.example
├── src/
│   └── mcp_gennx/
│       ├── __init__.py              # CLI entry point
│       ├── server.py                # Main server, sub-server mounting, lifespan
│       ├── config.py                # 환경변수, 설정
│       ├── client/
│       │   ├── gennx_client.py      # GEN NX REST API HTTP 클라이언트
│       │   └── qlora_client.py      # QLoRA vLLM 클라이언트 (optional)
│       ├── schemas/
│       │   ├── registry.py          # SchemaRegistry
│       │   ├── models.py            # ApiSchema, ToolDef Pydantic 모델
│       │   └── raw/                 # Phase 1 API 스키마 파일 (~40개)
│       ├── tools/
│       │   ├── factory.py           # ToolFactory (스키마→tool 자동생성)
│       │   ├── modeling.py          # 구조 모델링 sub-server (Phase 1)
│       │   ├── boundary.py          # 경계조건 (Phase 1)
│       │   ├── loads.py             # 하중 (Phase 1)
│       │   ├── analysis.py          # 해석제어 (Phase 1)
│       │   └── project.py           # 프로젝트 관리 (Phase 1)
│       │   # Phase 2+에서 필요 시 추가: moving_load.py, dynamic.py, ...
│       ├── toolsets/
│       │   └── definitions.py       # Toolset 정의 및 enable/disable 로직
│       └── utils/
│           ├── validators.py        # 스키마 검증
│           └── converters.py        # 스키마→tool 변환 유틸
├── tests/
├── scripts/
│   ├── generate_tools.py            # 스키마에서 tool 모듈 생성 스크립트
│   └── validate_schemas.py
└── data/
    ├── api_tier_assignment.json
    └── endpoint_to_subserver.json   # endpoint → sub-server 매핑
```

---

## 6. 핵심 설정

```env
# GEN NX 연결
GENNX_API_BASE_URL=http://localhost:8080
GENNX_API_TIMEOUT=30

# Toolset 제어
TOOLSETS=default          # default | all | default,moving_load,time_history,...

# QLoRA 라우터 (optional)
QLORA_ROUTER_ENABLED=false
QLORA_MODEL_ENDPOINT=http://localhost:8000/v1

# 접근 제어
READ_ONLY=false           # true면 GET만 허용
```

---

## 7. 구현 순서

### Phase 1: 기반 + 전처리/해석 Tool (지금 구현)
1. 프로젝트 초기화 (pyproject.toml, FastMCP 의존성)
2. `GennxApiClient` 구현 (httpx 기반, 에러 핸들링)
3. `SchemaRegistry` 구현 (~40개 API 스키마만 로드)
4. `ToolFactory` 구현 (스키마→tool 자동 생성)
5. 5개 sub-server 구현: modeling, boundary, loads, analysis, project
6. Main server + lifespan + sub-server mounting
7. GEN NX 실제 인스턴스 대상 통합 테스트
8. Claude Code에서 MCP 서버 연결하여 E2E 검증

### Phase 2: 고급 해석 확장 (필요 시)
- 이동하중, 동적해석, 시공단계 등 sub-server 모듈 추가
- 스키마 파일 추가 복사
- `server.py`에 mount 추가

### Phase 3: 후처리/설계 확장 (필요 시)
- results, viz, design sub-server 추가
- Sub-type 엔드포인트 처리 (post/TABLE 91종 등)

### Phase 4: QLoRA 통합 (필요 시)
- `suggest_tools` 메타툴 구현
- vLLM 서빙 엔드포인트 연동

---

## 8. 검증 방법

1. **Unit Test**: SchemaRegistry 로딩, ToolFactory 생성 로직
2. **Integration Test**: GEN NX REST API 실제 호출 (간단한 Node 생성/조회)
3. **E2E Test**: Claude Code에서 MCP 서버 연결 후 "노드 3개를 만들어줘" 같은 자연어 명령 실행
4. **Tool Count 검증**: `list_tools` 호출 시 default toolset에서 60개 이하인지 확인

---

## 9. 참고 파일

| 파일 | 용도 |
|---|---|
| `API_Data/api_tier_assignment.json` | 234 API tier 배정, tool 생성 우선순위 |
| `API_Data/GENNX_API_Schema/` (441 files) | MCP tool 자동 생성의 원본 스키마 |
| `data/samples/gennx_tool_schemas_tier1.json` | Tier-1 tool 스키마 참조 형식 |
| `scripts/07_serve_vllm.py` | QLoRA 모델 서빙, suggest_tools 연동 |
| `src/eval_metrics.py` | tool name 파싱 규칙 (`POST /db/node` 형식) |
