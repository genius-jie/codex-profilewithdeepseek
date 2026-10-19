#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render deep-research JSON results into a Markdown report.

The report uses the SAME field validation as validate_json.py so the body, the
table of contents and the summary counts all agree:

  * an item is a "valid" success only if it passes the validator (so ``{}``,
    ``null`` or a missing required field are listed as incomplete, not rendered
    as a completed item);
  * honest ``[uncertain]`` / uncertain-array fields are hidden from BOTH the body
    and the TOC summary, and the item is marked "needs review" instead of
    quietly counted as done;
  * ``--outline`` cross-checks the expected item list against available results
    and lists any gaps;
  * the report is written atomically and will not overwrite an existing file
    without ``--force``.

Exit codes: 0 clean report; 4 report produced but has gaps (needs-review /
invalid / missing items); 1 no valid items; 2 argument/tool error (from argparse);
3 output exists without --force.
"""

import argparse
import json
import os
import re
import sys
from importlib import util as _importlib_util
from pathlib import Path

import yaml


def _load_validator(path):
    p = Path(path)
    if not p.exists():
        print(f"[ERROR] validator not found: {p}")
        sys.exit(2)
    spec = _importlib_util.spec_from_file_location("deep_validate_json", str(p))
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for fn in ("load_fields_yaml", "validate_json", "_has_value"):
        if not hasattr(module, fn):
            print(f"[ERROR] validator {p} is missing required function '{fn}'")
            sys.exit(2)
    return module


def _default_validator():
    # At install time this script lives in research-report/, next to research/.
    return Path(__file__).resolve().parent.parent / "research" / "validate_json.py"


def fmt_value(v):
    if isinstance(v, dict):
        return "; ".join(f"{k}: {fmt_value(x)}" for k, x in v.items())
    if isinstance(v, list):
        if v and all(isinstance(x, dict) for x in v):
            return "\n" + "\n".join(
                "    - " + " | ".join(f"{a}: {fmt_value(b)}" for a, b in x.items()) for x in v
            )
        return ", ".join(fmt_value(x) for x in v)
    return str(v)


def slugify(text):
    # Canonical, lossy slug shared by outline items and result filenames so the
    # two sides match the same way deep names its {item_name_slug}.json files.
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "_", str(text).strip().lower()).strip("_")


def github_slug(text):
    s = str(text).lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s.strip()) or "item"


def load_categories(fields_path):
    data = yaml.safe_load(fields_path.read_text(encoding="utf-8")) or {}
    categories = []
    field_meta = {}
    for cat in data.get("field_categories", []) or []:
        cname = cat.get("category")
        fields = cat.get("fields", []) or []
        categories.append((cname, [f.get("name") for f in fields if f.get("name")]))
        for f in fields:
            if f.get("name"):
                field_meta[f["name"]] = cname
    return categories, field_meta


def load_outline_items(outline_path):
    data = yaml.safe_load(outline_path.read_text(encoding="utf-8")) or {}
    names = []
    for it in data.get("items", []) or []:
        if isinstance(it, dict):
            n = it.get("name") or it.get("item") or it.get("id")
            if n:
                names.append(str(n))
        elif isinstance(it, str):
            names.append(it)
    return names


def flatten(data, category_keys):
    values = {}
    uncertain = set()

    def handle(obj):
        for k, v in obj.items():
            if k in ("_source_file", "uncertain"):
                if k == "uncertain" and isinstance(v, list):
                    uncertain.update(x for x in v if isinstance(x, str))
                continue
            if k in category_keys and isinstance(v, dict):
                handle(v)
                continue
            values.setdefault(k, v)

    if isinstance(data, dict):
        handle(data)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                handle(item)
    return values, uncertain


def build_report(vmod, categories, field_meta, rendered, invalid, missing, title, toc_fields):
    lines = [f"# {title}", ""]
    n_complete = sum(1 for _rf, _v, _u, st in rendered if st == "complete")
    n_review = sum(1 for _rf, _v, _u, st in rendered if st == "needs_review")
    lines += [
        "## Summary",
        f"- Rendered: {len(rendered)} (complete: {n_complete}, needs-review: {n_review})",
        f"- Invalid / unreadable: {len(invalid)}",
        f"- Missing (vs outline): {len(missing)}",
        "",
        "## Table of Contents",
        "",
    ]
    for i, (rf, values, uncertain, status) in enumerate(rendered, 1):
        nm = _item_name(values, rf, uncertain, vmod)
        extras = [
            f"{tf}: {fmt_value(values[tf])}"
            for tf in toc_fields
            if tf in values and tf not in uncertain and vmod._has_value(values.get(tf))
        ]
        suffix = (" - " + " | ".join(extras)) if extras else ""
        mark = "  ⚠ needs review" if status == "needs_review" else ""
        lines.append(f"{i}. [{nm}](#{github_slug(str(i) + '. ' + nm)}){suffix}{mark}")
    lines.append("")

    for i, (rf, values, uncertain, status) in enumerate(rendered, 1):
        nm = _item_name(values, rf, uncertain, vmod)
        lines.append(f"## {i}. {nm}")
        lines.append(f"_Source file: {rf.name}_  |  _Status: {status}_")
        lines.append("")
        for cname, fnames in categories:
            rows = [
                (fn, values[fn])
                for fn in fnames
                if fn in values and fn not in uncertain and vmod._has_value(values.get(fn))
            ]
            if rows:
                lines.append(f"### {cname}")
                for fn, v in rows:
                    lines.append(f"- **{fn}**: {fmt_value(v)}")
                lines.append("")
        other = [
            (k, v)
            for k, v in values.items()
            if k not in field_meta and k not in uncertain and vmod._has_value(v)
        ]
        if other:
            lines.append("### Other Info")
            for k, v in other:
                lines.append(f"- **{k}**: {fmt_value(v)}")
            lines.append("")
        if uncertain:
            lines.append(f"> Needs review — {len(uncertain)} uncertain field(s):")
            for u in sorted(uncertain):
                lines.append(f"> - {u}")
            lines.append("")

    if invalid:
        lines.append("## Incomplete / failed items (NOT counted as done)")
        for name, reason in invalid:
            lines.append(f"- `{name}`: {reason}")
        lines.append("")
    if missing:
        lines.append("## Missing expected items (from outline)")
        for name in missing:
            lines.append(f"- {name}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n", n_complete, n_review


def _item_name(values, rf, uncertain, vmod):
    n = values.get("name")
    if isinstance(n, str) and "name" not in uncertain and vmod._has_value(n):
        return n.strip()
    return rf.stem.replace("_", " ")


def main():
    ap = argparse.ArgumentParser(description="Render deep-research JSON results into a Markdown report")
    ap.add_argument("-f", "--fields", default="fields.yaml", help="Path to fields.yaml")
    ap.add_argument("-d", "--dir", default="results", help="Directory containing results/*.json")
    ap.add_argument("-o", "--out", default="report.md", help="Output report path")
    ap.add_argument("--title", default="Research Report", help="Report title")
    ap.add_argument("--toc", default="", help="Comma-separated fields to show in the table of contents")
    ap.add_argument("--outline", help="Optional outline.yaml to cross-check expected items")
    ap.add_argument("--validator", help="Path to validate_json.py (defaults to sibling research/ dir)")
    ap.add_argument("--force", action="store_true", help="Overwrite the output report if it already exists")
    a = ap.parse_args()

    vmod = _load_validator(Path(a.validator).expanduser() if a.validator else _default_validator())

    fields_path = Path(a.fields).expanduser()
    if not fields_path.exists():
        print(f"[ERROR] fields.yaml not found: {fields_path}")
        sys.exit(1)
    try:
        all_fields, required_fields, field_categories, category_keys = vmod.load_fields_yaml(fields_path)
    except (ValueError, KeyError, TypeError, AttributeError, OSError, yaml.YAMLError) as e:
        print(f"[ERROR] Failed to parse fields.yaml: {e}")
        sys.exit(1)

    categories, field_meta = load_categories(fields_path)
    result_files = sorted(Path(a.dir).expanduser().glob("*.json"))
    if not result_files:
        print(f"[ERROR] No JSON results found in {a.dir}")
        sys.exit(1)

    rendered = []
    invalid = []
    for rf in result_files:
        try:
            res = vmod.validate_json(rf, all_fields, required_fields, field_categories, category_keys, mode="all")
        except (json.JSONDecodeError, ValueError, OSError) as e:
            invalid.append((rf.name, f"unreadable/not-json: {e}"))
            continue
        if res["status"] == "invalid":
            reason = ("missing required: " + ", ".join(res["missing_required"])) if res["missing_required"] else "coverage gap"
            invalid.append((rf.name, reason))
            continue
        data = json.loads(rf.read_text(encoding="utf-8"))
        values, uncertain = flatten(data, category_keys)
        rendered.append((rf, values, uncertain, res["status"]))

    if not rendered:
        print(f"[ERROR] No valid items to render ({len(invalid)} invalid/unreadable)")
        sys.exit(1)

    missing = []
    outline_expected = 0
    if a.outline:
        outline_path = Path(a.outline).expanduser()
        if not outline_path.exists():
            print(f"[ERROR] --outline given but file not found: {outline_path}")
            sys.exit(1)
        try:
            expected_items = load_outline_items(outline_path)
        except (yaml.YAMLError, OSError, ValueError) as e:
            print(f"[ERROR] --outline could not be parsed: {e}")
            sys.exit(1)
        outline_expected = len(expected_items)
        present = {slugify(rf.stem) for rf in result_files}
        present |= {slugify(v.get("name")) for _rf, v, _u, _s in rendered if v.get("name")}
        missing = [n for n in expected_items if slugify(n) not in present]

    toc = [t.strip() for t in a.toc.split(",") if t.strip()]
    md, n_complete, n_review = build_report(vmod, categories, field_meta, rendered, invalid, missing, a.title, toc)

    out_path = Path(a.out).expanduser()
    if out_path.exists() and not a.force:
        print(f"[ERROR] {out_path} already exists; pass --force to overwrite")
        sys.exit(3)
    if out_path.parent and not out_path.parent.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    tmp.write_text(md, encoding="utf-8")
    os.replace(tmp, out_path)
    print(f"Wrote {out_path} (rendered {len(rendered)}, complete {n_complete}, needs-review {n_review}, invalid {len(invalid)}, missing {len(missing)})")
    if a.outline and outline_expected == 0:
        print("[WARN] --outline contains no valid items; report cannot be declared complete")
    clean = (not invalid) and (not missing) and n_review == 0 and (not a.outline or outline_expected > 0)
    sys.exit(0 if clean else 4)


if __name__ == "__main__":
    main()
