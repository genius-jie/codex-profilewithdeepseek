---
name: research-report
description: Summarize deep research results into markdown report, cover all fields, skip uncertain values.
---

# Research Report - Summary Report

## Trigger
`/research-report`

## Workflow

### Step 1: Locate Results Directory
Find `*/outline.yaml` in current working directory, read topic and output_dir config.

### Step 2: Scan Optional Summary Fields
Read all JSON results, extract fields suitable for TOC display (numeric, short metrics), e.g.:
- github_stars
- google_scholar_cites
- swe_bench_score
- user_scale
- valuation
- release_date

Use request_user_input to ask user:
- Which fields to display in TOC besides item name?
- Provide dynamic options list (based on actual fields in JSON)

### Step 3: Report Generation Logic (reference spec)
A repo-shipped `generate_report.py` implements the core of the contract below (flat+nested JSON, category grouping, skip uncertain/empty/null, collect extra fields, TOC with unique anchors). Some optional display niceties (long-list wrapping, long-text `<br>`, TOC display labels) remain TODO; Step 4 calls the shipped script directly:
- Read all JSON from output_dir
- Read fields.yaml to get field structure
- Cover all field values from each JSON
- Skip fields with values containing [uncertain]
- Skip fields listed in uncertain array
- Generate markdown report format: Table of contents (with anchor links + user-selected summary fields) + Detailed content (by field category)
- Save to `{topic}/report.md`

**TOC Format Requirements**:
- Must include every item
- Each item displays: number, name (anchor link), user-selected summary fields
- Example: `1. [GitHub Copilot](#github-copilot) - Stars: 10k | Score: 85%`

#### Script Technical Requirements (Must Follow)

**1. JSON Structure Compatibility**
Support two JSON structures:
- Flat structure: Fields directly at top level `{"name": "xxx", "release_date": "xxx"}`
- Nested structure: Fields in category sub-dict `{"basic_info": {"name": "xxx"}, "technical_features": {...}}`

Field lookup order: Top level -> category mapping key -> Traverse all nested dicts

**2. Category Multi-language Mapping**
fields.yaml category names and JSON keys can be any combination (CN-CN, CN-EN, EN-CN, EN-EN). Must establish bidirectional mapping:
```python
CATEGORY_MAPPING = {
    "Basic Info": ["basic_info", "Basic Info"],
    "Technical Features": ["technical_features", "technical_characteristics", "Technical Features"],
    "Performance Metrics": ["performance_metrics", "performance", "Performance Metrics"],
    "Milestone Significance": ["milestone_significance", "milestones", "Milestone Significance"],
    "Business Info": ["business_info", "commercial_info", "Business Info"],
    "Competition & Ecosystem": ["competition_ecosystem", "competition", "Competition & Ecosystem"],
    "History": ["history", "History"],
    "Market Positioning": ["market_positioning", "market", "Market Positioning"],
}
```

**3. Complex Value Formatting**
- list of dicts (e.g., key_events, funding_history): Format each dict as one line, separate kv with ` | `
- Normal list: Short lists joined with comma, long lists displayed with line breaks
- Nested dict: Recursive formatting, display with semicolon or line breaks
- Long text strings (over 100 chars): Add line breaks `<br>` or use blockquote format for readability

**4. Extra Fields Collection**
Collect fields that exist in JSON but not defined in fields.yaml, put in "Other Info" category. Note to filter:
- Internal fields: `_source_file`, `uncertain`
- Nested structure top-level keys: `basic_info`, `technical_features` etc.
- `uncertain` array: Display each field name on separate line, don't compress into one line

**5. Uncertain Value Skipping**
Skip conditions:
- Field value contains `[uncertain]` string
- Field name is in `uncertain` array
- Field value is None or empty string

### Step 4: Execute Script
Run the shipped generator (do not hand-write one):
`python ~/.codex/skills/research-report/generate_report.py -f {topic}/fields.yaml -d {output_dir} -o {topic}/report.md --outline {topic}/outline.yaml --title "{topic}" --toc <user-selected summary fields>`
- Writes atomically and refuses to overwrite an existing report; to refresh the same report re-run with `--force`, or pass a new `--out` path to keep the old one.
- Exit codes: 0 clean; 2 bad args / validator-or-fields unavailable; 3 report exists without --force; 4 report produced but has needs-review/invalid/missing items (surface those lists to the user); 1 nothing valid. Never report success on exit 4.

## Output
- `{topic}/report.md` - Summary report (rendered by the shipped `~/.codex/skills/research-report/generate_report.py`; no script is written into `{topic}/`)
