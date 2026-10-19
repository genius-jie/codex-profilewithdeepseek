#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

CATEGORY_MAPPING = {
    "basic_info": ["basic_info", "Basic Info"],
    "technical_features": ["technical_features", "technical_characteristics", "Technical Features"],
    "performance_metrics": ["performance_metrics", "performance", "Performance Metrics"],
    "milestone_significance": ["milestone_significance", "milestones", "Milestone Significance"],
    "business_info": ["business_info", "commercial_info", "Business Info"],
    "competition_ecosystem": ["competition_ecosystem", "competition", "Competition Ecosystem"],
    "history": ["history", "History"],
    "market_positioning": ["market_positioning", "market", "Market Positioning"],
}

_SKIP_KEYS = {"_source_file", "uncertain"}
_EMPTY_MARKERS = {"", "[uncertain]", "[不确定]", "n/a", "na", "n.a", "none", "null", "nil", "unknown", "tbd", "to be determined", "-"}


def _has_value(v):
    if v is None:
        return False
    if isinstance(v, str):
        s = v.strip()
        if not s or s.lower() in _EMPTY_MARKERS or s.startswith("[uncertain]") or s.startswith("[不确定]"):
            return False
        return True
    if isinstance(v, (list, tuple, set)):
        return any(_has_value(x) for x in v)
    if isinstance(v, dict):
        return any(_has_value(x) for x in v.values())
    return True


def _get_uncertain_declared(data):
    """Collect field names listed in any 'uncertain' array across nesting levels."""
    declared = set()

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "uncertain" and isinstance(v, list):
                    declared.update(str(x) for x in v if isinstance(x, str))
                elif isinstance(v, dict):
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    walk(item)

    walk(data)
    return declared


def load_fields_yaml(fields_path):
    with fields_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("fields.yaml must be a mapping with a field_categories list")
    items = [
        (field["name"], category["category"], field.get("required", False))
        for category in data.get("field_categories", [])
        for field in category.get("fields", [])
    ]
    all_fields = {name for name, _, _ in items}
    required_fields = {name for name, _, required in items if required}
    field_categories = {name: category for name, category, _ in items}
    cat_names = {c.get("category") for c in data.get("field_categories", []) if c.get("category")}
    alias_keys = set(CATEGORY_MAPPING) | {k for v in CATEGORY_MAPPING.values() for k in v}
    # An alias is only treated as a nested container when it is NOT a defined field,
    # so a dict-valued field that shares a name with an alias (e.g. "performance")
    # is counted as a field instead of being descended into as a category.
    category_keys = cat_names | (alias_keys - all_fields)
    if not all_fields:
        raise ValueError("fields.yaml defines zero fields; check the field_categories structure")
    return all_fields, required_fields, field_categories, category_keys


def extract_json_fields(data, category_keys=None):
    if category_keys is None:
        category_keys = set(CATEGORY_MAPPING) | {k for v in CATEGORY_MAPPING.values() for k in v}
    fields = set()
    stack = [(data, True)]
    while stack:
        obj, is_category_level = stack.pop()
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in _SKIP_KEYS:
                    continue
                if is_category_level and k in category_keys and isinstance(v, dict):
                    stack.append((v, True))
                    continue
                if _has_value(v):
                    fields.add(k)
        elif isinstance(obj, list):
            stack.extend((item, is_category_level) for item in obj if isinstance(item, dict))
    return fields


def validate_json(json_path, all_fields, required_fields, field_categories, category_keys=None, mode="all", min_coverage=100.0):
    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)
    uncertain_declared = _get_uncertain_declared(data)
    json_fields = extract_json_fields(data, category_keys)
    covered = all_fields & json_fields
    optional_fields = all_fields - required_fields
    uncertain_optional = optional_fields & uncertain_declared
    uncertain_required = required_fields & uncertain_declared
    # A required field is satisfied only by a real value; listing it in `uncertain`
    # does NOT exempt it (closes the "stuff required fields into uncertain" abuse).
    missing_required = required_fields - covered
    # For the gate, an honestly-uncertain OPTIONAL field is not counted as missing.
    missing = (all_fields - covered) - uncertain_optional
    extra = json_fields - all_fields
    missing_by_category = defaultdict(list)
    for field in missing:
        missing_by_category[field_categories.get(field, "Unknown")].append(field)
    coverage_rate = len(covered) / len(all_fields) * 100 if all_fields else 100.0
    if missing_required:
        status, exit_code = "invalid", 1
    elif mode == "all" and missing:
        status, exit_code = "invalid", 1
    elif mode == "coverage" and coverage_rate < min_coverage:
        status, exit_code = "invalid", 1
    elif uncertain_optional or uncertain_required:
        status, exit_code = "needs_review", 0
    else:
        status, exit_code = "complete", 0
    return {
        "file": json_path.name,
        "status": status,
        "exit_code": exit_code,
        "total_defined": len(all_fields),
        "covered": len(covered),
        "missing": len(missing),
        "extra": len(extra),
        "coverage_rate": coverage_rate,
        "missing_required": sorted(missing_required),
        "missing_optional": sorted(missing - required_fields),
        "uncertain_optional": sorted(uncertain_optional),
        "uncertain_required": sorted(uncertain_required),
        "missing_by_category": {k: sorted(v) for k, v in missing_by_category.items()},
        "extra_fields": sorted(extra),
        "valid": status == "complete",
    }


def print_result(result, verbose=True):
    status = {"complete": "PASS", "needs_review": "REVIEW", "invalid": "FAIL"}.get(result.get("status"), "FAIL")
    line = "=" * 60
    print(f"\n{line}")
    print(f"[{status}] {result['file']}")
    print(line)
    print(f"Coverage: {result['coverage_rate']:.1f}% ({result['covered']}/{result['total_defined']})")
    if result["missing_required"]:
        print(f"\n[ERROR] Missing required fields ({len(result['missing_required'])}):")
        print("\n".join(f"  - {f}" for f in result["missing_required"]))
    if verbose and result["missing_optional"]:
        missing_required = set(result["missing_required"])
        print(f"\n[WARN] Missing optional fields ({len(result['missing_optional'])}):")
        for cat in sorted(result["missing_by_category"]):
            optional = [f for f in result["missing_by_category"][cat] if f not in missing_required]
            if optional:
                print(f"  [{cat}]: {', '.join(optional)}")
    if verbose and result["extra_fields"]:
        extra = result["extra_fields"]
        print(f"\n[INFO] Extra fields ({len(extra)}):")
        print(f"  {', '.join(extra[:10])}")
        if len(extra) > 10:
            print(f"  ... and {len(extra) - 10} more")
    if verbose and result.get("uncertain_optional"):
        ue = result["uncertain_optional"]
        print(f"\n[INFO] Uncertain-exempt fields ({len(ue)}): {', '.join(ue)}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate whether JSON files cover all fields defined in fields.yaml")
    parser.add_argument("--fields", "-f", type=str, help="Path to fields.yaml", default="fields.yaml")
    parser.add_argument("--json", "-j", type=str, nargs="*", help="JSON file paths to validate")
    parser.add_argument("--dir", "-d", type=str, help="Directory containing JSON files", default="results")
    parser.add_argument("--quiet", "-q", action="store_true", help="Show summary only")
    parser.add_argument("--mode", choices=["all", "required", "coverage"], default="all", help="all=cover every field; required=only required fields; coverage=reach --min-coverage")
    parser.add_argument("--min-coverage", type=float, default=100.0, help="Minimum coverage percent when --mode=coverage")
    parser.add_argument("--allow-empty", action="store_true", help="Do not fail when no JSON files are found (default: exit non-zero)")
    args = parser.parse_args()
    fields_path = Path(args.fields).expanduser()
    if not fields_path.exists():
        for p in (Path.cwd() / "fields.yaml", Path.cwd().parent / "fields.yaml"):
            if p.exists():
                fields_path = p
                break
    if not fields_path.exists():
        print(f"[ERROR] fields.yaml not found: {fields_path}")
        sys.exit(1)
    print(f"Field definition file: {fields_path}")
    try:
        all_fields, required_fields, field_categories, category_keys = load_fields_yaml(fields_path)
    except (ValueError, KeyError, TypeError, AttributeError, OSError, yaml.YAMLError) as e:
        print(f"[ERROR] Failed to parse fields.yaml: {e}")
        sys.exit(1)
    print(f"Total fields: {len(all_fields)} (required: {len(required_fields)}, optional: {len(all_fields) - len(required_fields)})")
    json_files = (
        [Path(p).expanduser() for p in args.json]
        if args.json
        else sorted(Path(args.dir).expanduser().glob("*.json")) if Path(args.dir).expanduser().exists() else []
    )
    if not json_files:
        if args.allow_empty:
            print("[WARN] No JSON files found (allowed by --allow-empty)")
            sys.exit(0)
        print("[ERROR] No JSON files found — nothing to validate")
        sys.exit(1)
    results = []
    for json_path in json_files:
        if not json_path.exists():
            print(f"[WARN] File not found: {json_path}")
            continue
        try:
            result = validate_json(json_path, all_fields, required_fields, field_categories, category_keys, args.mode, args.min_coverage)
        except (json.JSONDecodeError, ValueError, OSError) as e:
            print(f"[ERROR] {json_path.name}: {e}")
            continue
        results.append(result)
        print_result(result, verbose=not args.quiet)
    line = "=" * 60
    print(f"\n{line}")
    print("Summary")
    print(line)
    complete = sum(1 for r in results if r["status"] == "complete")
    review = sum(1 for r in results if r["status"] == "needs_review")
    invalid = sum(1 for r in results if r["status"] == "invalid")
    avg_coverage = sum(r["coverage_rate"] for r in results) / len(results) if results else 0
    print(f"Complete: {complete}  Needs-review: {review}  Invalid: {invalid}  (of {len(json_files)} requested)")
    print(f"Average coverage: {avg_coverage:.1f}%")
    # A requested file that was missing/unreadable cannot be claimed as done -> invalid.
    overall = "invalid" if (invalid or len(results) < len(json_files)) else ("needs_review" if review else "complete")
    receipt = {
        "overall": overall,
        "files": [
            {"file": r["file"], "status": r["status"],
             "missing_required": r["missing_required"],
             "uncertain_optional": r["uncertain_optional"],
             "uncertain_required": r["uncertain_required"]}
            for r in results
        ],
    }
    print("__VALIDATION_RESULT__ " + json.dumps(receipt, ensure_ascii=False))
    sys.exit(1 if overall == "invalid" else 0)


if __name__ == "__main__":
    main()
