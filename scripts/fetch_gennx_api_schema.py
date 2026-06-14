"""Fetch all MIDAS API 'JSON Manual' schemas from the Zendesk Help Center API
and save them as GENNX_API_Schema-format JSON files.

Source : https://support.midasuser.com  (Zendesk Help Center, public, no auth)
         Category "Online Help_MIDAS API" 30087455049881
         Section  "JSON Manual"          30087500371097  <- the API endpoint specs

Each API article is rendered as::

    {
      "endpoint": "db/SPLC",                # parsed from Input URI
      "title": "...",
      "url": "<article html_url>",
      "input_uri": "{base url} + db/SPLC",
      "active_methods": ["POST", "GET", "PUT", "DELETE"],
      "json_schema": {...},                 # the 'JSON Schema' copy-block, parsed
      "examples": { "<name>": {...}, ... },  # the 'Examples' copy-blocks, parsed
      "tables": [ [ {row}, ... ], ... ],     # the 'Specifications' table(s)
      "menu_name": "<title>"
    }

It also writes ``_index.json`` mapping ``endpoint -> article_id`` (rebuilt from
every file in the folder; for endpoints shared by many articles -- e.g. the
``post/TABLE`` result-table specs -- the last file wins, matching the existing
GENNX_API_Schema index).

Parsing was reverse-engineered against the existing GENNX_API_Schema dataset:
core fields (endpoint / input_uri / active_methods / json_schema / menu_name)
match ~95%+; the residual are articles whose old data was itself broken
(uppercase ``POST/TABLE`` variant template) where this output is the cleaner one.
``tables`` may differ cosmetically in Description-cell bullet rendering only.

Usage:
    python scripts/fetch_gennx_api_schema.py                # full run (en-us)
    python scripts/fetch_gennx_api_schema.py --limit 5      # smoke test
    python scripts/fetch_gennx_api_schema.py --locale ko --missing-only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import lxml.html

BASE = "https://support.midasuser.com"
API_CATEGORY = "30087455049881"
JSON_MANUAL_SECTION = "30087500371097"
DEFAULT_OUT = Path(
    r"C:\Users\hjm0830\OneDrive - MIDAS\바탕 화면\MIDAS\01_Study\MCP\Raw Data\API"
)


# --------------------------------------------------------------------------
# HTML -> schema parser  (validated against GENNX_API_Schema)
# --------------------------------------------------------------------------

def _cell_after_heading(root, heading: str) -> str:
    h = root.xpath(f'//h3[normalize-space(.)="{heading}"]')
    if not h:
        return ""
    tbl = h[0].xpath('following::table[1]')
    if not tbl:
        return ""
    return re.sub(r"\s+", " ", tbl[0].text_content()).strip()


def _classify_section(text: str) -> str | None:
    """Map a (short) header string to a canonical section, tolerant of casing
    and 'JSON Schema' vs 'Json Schema'. Returns None for non-section headers."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t or len(t) > 24:
        return None
    low = t.lower()
    if low.endswith("schema"):
        return "JSON Schema"
    if low.endswith(("examples", "example")):
        if low.startswith("request"):
            return "Request Examples"
        if low.startswith("response"):
            return "Response Examples"
        return "Examples"
    return None


def _section_of(block) -> str:
    """Nearest preceding section header for a JSON block. The header may be an
    <h2/h3/h4> OR a bold paragraph (<p><strong>Json Schema</strong></p>), which
    some articles (e.g. db/REBB) use instead of a heading."""
    cands = block.xpath(
        'preceding::h2 | preceding::h3 | preceding::h4 | preceding::p[.//strong]'
    )
    for el in reversed(cands):
        sec = _classify_section(el.text_content())
        if sec:
            return sec
    return ""


def _cell_text(td, column: str | None = None) -> str:
    """Render a spec-table cell. Multi-<p> cells follow the bullet rule
    ('prev' + '•\\ncontent'); the Key column has surrounding quotes stripped."""
    ps = td.xpath('./p')
    parts = [p.text_content() for p in ps] if ps else [td.text_content()]
    result = ""
    for raw in parts:
        s = re.sub(r"[ \t]+", " ", raw.replace("\xa0", " ")).strip()
        if not s:
            continue
        if s.startswith("•"):
            result += "•\n" + s[1:].strip()
        else:
            result += s
    if column == "Key" and len(result) >= 2 and result.startswith('"') and result.endswith('"'):
        result = result[1:-1]
    return result


def _parse_spec_table(tbl) -> list:
    trs = tbl.xpath('.//tr')
    if not trs:
        return []
    headers = [_cell_text(c) for c in trs[0].xpath('./th|./td')]
    rows = []
    for tr in trs[1:]:
        cells = tr.xpath('./th|./td')
        if len(cells) == 1 and len(headers) > 1:
            rows.append({"_condition": _cell_text(cells[0])})
            continue
        row = {}
        for i, h in enumerate(headers):
            row[h] = _cell_text(cells[i], h) if i < len(cells) else ""
        rows.append(row)
    return rows


def parse_article(art: dict) -> dict:
    # No global <br>->\n: copyTarget JSON parses fine without newlines (JSON
    # ignores whitespace) and spec cells must keep "Array[String]" joined.
    root = lxml.html.fromstring("<div>" + (art.get("body") or "") + "</div>")

    input_uri = _cell_after_heading(root, "Input URI")
    methods_cell = _cell_after_heading(root, "Active Methods")
    active_methods = [m.strip() for m in methods_cell.split(",") if m.strip()]

    endpoint = input_uri.split(" + ", 1)[1].strip() if " + " in input_uri else ""

    json_schema: dict = {}
    examples: dict[str, object] = {}
    # Old template: <div id="copyTargetN">; newer template: <... class="manual-json-pre">
    blocks = root.xpath(
        '//div[starts-with(@id,"copyTarget")] | //*[contains(@class,"manual-json-pre")]'
    )
    for ct in blocks:
        section = _section_of(ct)
        lbl_el = ct.xpath('preceding::p[contains(@class,"btn_dropdown")][1]')
        label = lbl_el[0].text_content().strip() if lbl_el else ""
        raw = ct.text_content().replace("\xa0", " ")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"__parse_error__": raw[:300]}
        if section.endswith("Examples"):
            base = label or f"Example {len(examples) + 1}"
            key = base if section == "Examples" else f"{section} {base}"
            if key in examples:
                key = f"{key} ({len(examples) + 1})"
            examples[key] = parsed
        else:
            # Any non-Examples JSON block is the schema: an explicit
            # "JSON Schema"/"Json Schema" header, OR an unlabeled block that
            # some articles (ope/*, certain post/TABLE) place with no header.
            if not json_schema:
                json_schema = parsed

    tables = []
    spec = root.xpath('//h3[normalize-space(.)="Specifications"]')
    if spec:
        for tbl in spec[0].xpath('following::table'):
            rows = _parse_spec_table(tbl)
            if rows:
                tables.append(rows)

    return {
        "endpoint": endpoint,
        "title": art.get("title", ""),
        "url": art.get("html_url", ""),
        "input_uri": input_uri,
        "active_methods": active_methods,
        "json_schema": json_schema,
        "examples": examples,
        "tables": tables,
        "menu_name": art.get("title", ""),
    }


# --------------------------------------------------------------------------
# Zendesk fetching
# --------------------------------------------------------------------------

def _get(url: str, retries: int = 5):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", "5")))
                continue
            if 500 <= e.code < 600:
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} attempts: {url} ({last})")


def fetch_section_articles(section: str, locale: str):
    page = 1
    while True:
        url = (f"{BASE}/api/v2/help_center/{locale}/sections/{section}"
               f"/articles.json?per_page=100&page={page}")
        data = _get(url)
        for art in data.get("articles", []):
            yield art
        if not data.get("next_page"):
            break
        page += 1
        time.sleep(0.3)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--section", default=JSON_MANUAL_SECTION)
    ap.add_argument("--locale", default="en-us")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--missing-only", action="store_true",
                    help="skip articles whose <id>.json already exists")
    args = ap.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {args.out_dir}")
    print(f"Fetching JSON Manual section {args.section} ({args.locale}) ...")

    written = skipped = no_endpoint = empty_schema = 0
    errors: list[str] = []

    for art in fetch_section_articles(args.section, args.locale):
        aid = str(art["id"])
        target = args.out_dir / f"{aid}.json"
        if args.missing_only and target.exists():
            skipped += 1
            continue
        try:
            rec = parse_article(art)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{aid}: {e}")
            continue
        if not rec["endpoint"]:
            no_endpoint += 1  # e.g. the landing "MIDAS API Online Manual" page
            continue
        if not rec["json_schema"]:
            empty_schema += 1
        target.write_text(
            json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        written += 1
        if written % 50 == 0:
            print(f"  ... {written} written")
        if args.limit and written >= args.limit:
            print(f"  (stopped at limit {args.limit})")
            break

    # Rebuild _index.json (endpoint -> article_id) from every file in the folder.
    index: dict[str, str] = {}
    shared: dict[str, int] = {}
    for f in sorted(args.out_dir.glob("*.json")):
        if f.name == "_index.json":
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        ep = rec.get("endpoint", "")
        if not ep:
            continue
        if ep in index:
            shared[ep] = shared.get(ep, 1) + 1
        index[ep] = f.stem
    (args.out_dir / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    total_files = sum(1 for f in args.out_dir.glob("*.json") if f.name != "_index.json")
    print("\n=== summary ===")
    print(f"  written this run        : {written}")
    if args.missing_only:
        print(f"  skipped (already present): {skipped}")
    print(f"  skipped (no endpoint)   : {no_endpoint}")
    print(f"  total schema files      : {total_files}")
    print(f"  unique endpoints (_index): {len(index)}")
    print(f"  empty json_schema       : {empty_schema}")
    print(f"  errors                  : {len(errors)}")
    multi = {k: v for k, v in shared.items() if v > 1}
    if multi:
        print(f"  endpoints shared by many files (last wins): {multi}")
    for e in errors[:15]:
        print(f"    error: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
