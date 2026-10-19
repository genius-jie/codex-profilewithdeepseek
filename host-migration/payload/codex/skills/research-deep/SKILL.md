---
name: research-deep
description: Read research outline, launch independent agent for each item for deep research. Disable task output.
---

# Research Deep - Deep Research

## Trigger
`/research-deep`

## Workflow

### Step 1: Auto-locate Outline
Find `*/outline.yaml` file in current working directory, read items list, execution config (including items_per_agent).

### Step 2: Resume Check
- Do NOT treat a file's existence as "done": re-validate existing results against the CURRENT fields.yaml, e.g. `python ~/.codex/skills/research/validate_json.py -f {fields_path} -d {output_dir} --mode all --allow-empty --quiet`
- Read each file's `__VALIDATION_RESULT__` per-file status: complete/needs_review -> skip; invalid (e.g. a newly-added required field) -> re-research, keeping the old file until a new result passes (persist never overwrites on failure)

### Step 3: Batch Execution
- Batch by batch_size (need user approval before next batch)
- Each agent handles items_per_agent items
- Launch web-search-agent (background parallel, disable task output)
- Each agent RETURNS JSON text only; the skill pipes it to `python ~/.codex/skills/research-deep/persist_agent_json.py -o {output_path} --validate --fields {fields_path} --validator ~/.codex/skills/research/validate_json.py --mode all` (strips ``` fences, writes, validates); optional fields honestly marked `[uncertain]` become needs_review (a required field marked uncertain fails as invalid), and on non-zero exit the item is re-researched up to 3 total attempts before being marked incomplete (the Codex researcher runs in a read-only sandbox and cannot write)

**Parameter Retrieval**:
- `{topic}`: topic field from outline.yaml
- `{item_name}`: item's name field
- `{item_related_info}`: item's complete yaml content (name + category + description etc.)
- `{output_dir}`: execution.output_dir from outline.yaml (default: ./results)
- `{fields_path}`: absolute path to {topic}/fields.yaml
- `{output_path}`: absolute path to {output_dir}/{item_name_slug}.json (slugify item_name: replace spaces with _, remove special chars)

**Hard Constraint**: The following prompt must be strictly reproduced, only replacing variables in {xxx}, do not modify structure or wording.

**Prompt Template**:
```python
prompt = f"""## Task
Research {item_related_info}. Return ONLY the structured JSON object as your final message. Do NOT write any file and do NOT run any script — the calling skill persists your JSON to {output_path} and validates it.

## Field Definitions
Read {fields_path} to get all field definitions

## Output Requirements
1. Output JSON according to fields defined in fields.yaml
2. Mark uncertain field values with [uncertain]
3. Add uncertain array at the end of JSON, listing all uncertain field names
4. All field values must be in English

## Output
Return the JSON inline only. The calling skill will save it to: {output_path}

## Caller Responsibility
The calling skill persists and validates your reply with one command: `python ~/.codex/skills/research-deep/persist_agent_json.py -o {output_path} --validate --fields {fields_path} --validator ~/.codex/skills/research/validate_json.py --mode all` (strips ``` fences, writes {output_path}, runs the gate). On non-zero exit it re-researches at most 2 more times (3 total), then keeps the last JSON and lists the item under "incomplete" in Step 5. Never strip a `[uncertain]` marker or invent a value to pass the gate; optional fields honestly listed in the JSON `uncertain` array become needs_review (not auto-pass), while required fields listed there are NOT exempt and fail as invalid. Do not write or validate inside this agent.
"""
```

**One-shot Example** (assuming researching GitHub Copilot):
```
## Task
Research name: GitHub Copilot
category: International Product
description: Developed by Microsoft/GitHub, first mainstream AI coding assistant, ~40% market share. Return the structured JSON inline; the calling skill saves it to {project_dir}/results/GitHub_Copilot.json

## Field Definitions
Read {project_dir}/fields.yaml to get all field definitions

## Output Requirements
1. Output JSON according to fields defined in fields.yaml
2. Mark uncertain field values with [uncertain]
3. Add uncertain array at the end of JSON, listing all uncertain field names
4. All field values must be in English

## Output
Return the JSON inline; the calling skill saves it to {project_dir}/results/GitHub_Copilot.json

## Caller Responsibility
The calling skill runs `python ~/.codex/skills/research-deep/persist_agent_json.py -o {project_dir}/results/GitHub_Copilot.json --validate --fields {project_dir}/fields.yaml --validator ~/.codex/skills/research/validate_json.py --mode all`; on non-zero exit it re-researches up to 3 total attempts, then keeps the last output and marks the item incomplete in Step 5 (never by removing `[uncertain]`).
```

### Step 4: Wait and Monitor
- Wait for current batch to complete
- Launch next batch
- Display progress

### Step 5: Summary Report
After all complete, output:
- Completion count
- Failed/uncertain marked items
- Output directory

## Agent Config
- Background execution: Yes
- Task Output: Disabled (agent returns JSON text; the skill persists and validates it)
- Resume support: Yes
