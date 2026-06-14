"""Fetch all GEN NX online-manual articles from the Zendesk Help Center API
and save them as GENNX_Feature-format JSON files.

Source : https://support.midasuser.com  (Zendesk Help Center, public, no auth)
         Category "Online Help_GEN NX" = 29648912400153

For every article in the category (all sub-sections, recursively) it writes
``<out-dir>/<article_id>.json`` with the same shape the existing GENNX_Feature
dataset uses::

    {
      "article_id": "...",
      "title": "...",
      "feature_name": "<title> ↗",
      "url": "https://support.midasuser.com/hc/<locale>/articles/<id>",
      "labels": [...],
      "sections": { "function": "...", "call": "...", "input": "...",
                    "note": "...", "description": "...", ... },
      "full_text": "..."
    }

It also writes ``<out-dir>/_index.json`` mapping ``"<title> ↗" -> "<id>"``.

The article body (HTML) is split into ``sections`` by the manual's section
headers (Function / Call / Input / Output / Note / Description / Overview /
Example / Parameters). Detection and segmentation were reverse-engineered and
validated against the existing GENNX_Feature dataset (>90% exact section parity;
the residual are old-parser artifacts where this output is the more faithful one).

Usage:
    python scripts/fetch_gennx_features.py                 # full run (en-us)
    python scripts/fetch_gennx_features.py --limit 5       # smoke test
    python scripts/fetch_gennx_features.py --locale ko --out-dir ...
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import lxml.html

BASE = "https://support.midasuser.com"
GEN_NX_CATEGORY = "29648912400153"
DEFAULT_OUT = Path(
    r"C:\Users\hjm0830\OneDrive - MIDAS\바탕 화면\MIDAS\01_Study\MCP\Raw Data\Feature"
)

# --------------------------------------------------------------------------
# HTML -> sections parser
# --------------------------------------------------------------------------

KEYS = ["function", "call", "input", "output", "note", "description",
        "overview", "example", "parameters"]
KEYSET = set(KEYS)

# Section-header aliases -> canonical English key. English headers map to
# themselves; Korean headers (ko-locale manual) map to the same English keys
# so ko articles produce the same section structure as en-us ones.
ALIASES: dict[str, str] = {k: k for k in KEYS}
ALIASES.update({
    "기능": "function",
    "호출": "call",
    "입력": "input",
    "출력": "output",
    "개요": "overview",
    "설명": "description",
    "상세설명": "description",
    "참고": "note",
    "주의": "note",
    "예제": "example",
    "예": "example",
    "매개변수": "parameters",
    "화면구성": "overview",
})


def _canon(raw: str):
    """Return the canonical English section key for a header string, or None."""
    s = (raw or "").strip().rstrip(" :")
    if not s:
        return None
    return ALIASES.get(s) or ALIASES.get(s.lower())

BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul",
              "ol", "table", "tbody", "thead", "tr", "blockquote", "pre"}
CONTAINER_TAGS = {"div", "section", "article", "main", "body", "span"}


def _clean(text: str) -> str:
    text = text.replace("\xa0", " ")
    lines = [ln.rstrip() for ln in text.split("\n")]
    out = "\n".join(lines)
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out.strip()


def _heading_marker(el):
    tag = el.tag
    if isinstance(tag, str) and tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return _canon(el.text_content() or "")
    return None


def _leading_text_marker(el):
    """A <p> whose first line is exactly a keyword -> (key, rest_text)."""
    if el.tag != "p":
        return None
    full = el.text_content() or ""
    first, _, tail = full.partition("\n")
    key = _canon(first)
    if key:
        return key, tail.strip()
    return None


def _iter_blocks(el):
    """Yield leaf block elements in document order, descending through
    containers at any depth."""
    for child in el:
        if not isinstance(child.tag, str):
            continue
        if child.tag in CONTAINER_TAGS:
            produced = False
            for sub in _iter_blocks(child):
                produced = True
                yield sub
            if not produced and (child.text_content() or "").strip():
                yield child
        else:
            yield child


def _render_block_text(el) -> str:
    block_children = [c for c in el if isinstance(c.tag, str) and c.tag in BLOCK_TAGS]
    if block_children:
        parts = []
        if el.text and el.text.strip():
            parts.append(el.text.strip())
        for c in el:
            if isinstance(c.tag, str) and c.tag in BLOCK_TAGS:
                parts.append(_render_block_text(c))
            else:
                txt = c.text_content() if hasattr(c, "text_content") else (c.text or "")
                if txt and txt.strip():
                    parts.append(txt.strip())
            if c.tail and c.tail.strip():
                parts.append(c.tail.strip())
        return "\n\n".join(p for p in parts if p)
    return (el.text_content() or "").strip()


def parse_body(body_html: str):
    """Return (sections: dict[str,str], full_text: str)."""
    import re
    body_html = re.sub(r"<br\s*/?>", "\n", body_html or "", flags=re.I)
    if not body_html.strip():
        return {}, ""
    root = lxml.html.fromstring("<div>" + body_html + "</div>")

    sections: dict[str, str] = {}
    full_parts: list[str] = []
    current_key = "overview"
    current_buf: list[str] = []

    def flush():
        text = _clean("\n\n".join(current_buf))
        if text:
            sections[current_key] = text  # repeated key -> last segment wins

    for el in _iter_blocks(root):
        m = _heading_marker(el)
        lt = _leading_text_marker(el) if m is None else None
        if m or lt:
            flush()
            if m:
                key = m
                header_text = (el.text_content() or "").strip()
                rest = ""
            else:
                key, rest = lt
                header_text = key.capitalize()
            full_parts.append(header_text)
            current_key = key
            current_buf = []
            if rest:
                full_parts.append(rest)
                current_buf.append(rest)
            continue
        txt = _render_block_text(el)
        if txt.strip():
            full_parts.append(txt)
            current_buf.append(txt)
    flush()

    return sections, _clean("\n\n".join(full_parts))


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
                wait = int(e.headers.get("Retry-After", "5"))
                time.sleep(wait)
                continue
            if 500 <= e.code < 600:
                time.sleep(2 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} attempts: {url} ({last})")


def fetch_category_articles(category: str, locale: str):
    """Yield every article object in the category (all sub-sections)."""
    page = 1
    while True:
        url = (f"{BASE}/api/v2/help_center/{locale}/categories/{category}"
               f"/articles.json?per_page=100&page={page}")
        data = _get(url)
        for art in data.get("articles", []):
            yield art
        if not data.get("next_page"):
            break
        page += 1
        time.sleep(0.3)


def build_record(art: dict, locale: str) -> dict:
    aid = str(art["id"])
    title = art.get("title") or art.get("name") or ""
    sections, full_text = parse_body(art.get("body", ""))
    return {
        "article_id": aid,
        "title": title,
        "feature_name": f"{title} ↗",
        "url": f"{BASE}/hc/{locale}/articles/{aid}",
        "labels": art.get("label_names", []) or [],
        "sections": sections,
        "full_text": full_text,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--category", default=GEN_NX_CATEGORY)
    ap.add_argument("--locale", default="en-us")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=0, help="stop after N articles (smoke test)")
    ap.add_argument("--missing-only", action="store_true",
                    help="skip articles whose <id>.json already exists (e.g. ko fill-in)")
    args = ap.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {args.out_dir}")
    print(f"Fetching category {args.category} ({args.locale}) ...")

    written = 0
    skipped = 0
    empty_sections = 0
    errors: list[str] = []

    for art in fetch_category_articles(args.category, args.locale):
        aid = str(art["id"])
        target = args.out_dir / f"{aid}.json"
        if args.missing_only and target.exists():
            skipped += 1
            continue
        try:
            rec = build_record(art, args.locale)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{aid}: {e}")
            continue

        target.write_text(
            json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        written += 1
        if not rec["sections"]:
            empty_sections += 1
        if written % 50 == 0:
            print(f"  ... {written} written")
        if args.limit and written >= args.limit:
            print(f"  (stopped at limit {args.limit})")
            break

    # Rebuild _index.json from ALL files in the folder (merges en-us + ko runs).
    index: dict[str, str] = {}
    dup_titles: dict[str, list[str]] = {}
    for f in sorted(args.out_dir.glob("*.json")):
        if f.name == "_index.json":
            continue
        rec = json.loads(f.read_text(encoding="utf-8"))
        fn = rec.get("feature_name", "")
        aid = rec.get("article_id", "")
        if fn in index and index[fn] != aid:
            dup_titles.setdefault(fn, [index[fn]]).append(aid)
        index[fn] = aid
    (args.out_dir / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    total_files = sum(1 for f in args.out_dir.glob("*.json") if f.name != "_index.json")
    print("\n=== summary ===")
    print(f"  articles written this run : {written}")
    if args.missing_only:
        print(f"  skipped (already present) : {skipped}")
    print(f"  total article files       : {total_files}")
    print(f"  _index entries            : {len(index)}")
    print(f"  empty sections (this run) : {empty_sections}")
    print(f"  duplicate titles          : {len(dup_titles)}")
    print(f"  fetch/parse errors        : {len(errors)}")
    for e in errors[:15]:
        print(f"    error: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
