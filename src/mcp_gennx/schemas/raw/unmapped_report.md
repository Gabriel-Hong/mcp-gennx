# Unmapped / Incomplete raw schemas

- Total files processed: **65**
- Mapped successfully  : **60**
- Mapping failures     : **5**
- Empty description    : **0**

## Mapping failures (no Feature content injected)

| endpoint | file | reason |
|---|---|---|
| `db/BUCK` | `db_BUCK.json` | Feature/29488057553049.json missing or invalid |
| `db/EIGV` | `db_EIGV.json` | Feature/29488035391129.json missing or invalid |
| `db/NLCT` | `db_NLCT.json` | Feature/29488026346649.json missing or invalid |
| `db/PDEL` | `db_PDEL.json` | Feature/29488058050329.json missing or invalid |
| `doc/ANAL` | `doc_ANAL.json` | Feature/29502604755481.json missing or invalid |

## Empty description (no Korean fallback nor Feature.function)

_(none)_

## Suggested next steps

- Add missing endpoint mappings to `api_to_feature_mapping_v3.json`.
- For multi-merged endpoints (db/SECT, db/THIK), sub-variant features can be wired via `GENNX_API_Schema/_index.json` nested entries.
