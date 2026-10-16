"""Pure composition diagnostics for explicitly supplied General method assets.

No discovery, file access, model/tool calls, persistence, adoption or routing.
The caller owns YAML loading (including duplicate-key rejection), approval,
resource binding, runtime capabilities and evidence verification. ``available``
is a caller assertion, not independent proof. Only ``selected`` is adopted;
dependency closure and justified candidates remain ``proposed``.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json

SCHEMA_VERSION = "method-composition.v1"
_DIMENSIONS = {"goal_source", "business_modeling", "experience_design", "internal_structure",
               "deployment_topology", "interaction", "contract", "verification", "collaboration",
               "execution_organization", "delivery", "cross_cutting_quality"}
_KINDS = {"method", "artifact", "evidence", "capability"}
_STAGES = {"design", "plan", "implement", "review", "verify", "deliver"}


def _key(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _version(value):
    return type(value) is int and value > 0 or _text(value) and not any(c.isspace() or c in "^~*<>=," for c in value)


def _fields(value, required, optional=()):
    return isinstance(value, dict) and set(required) <= value.keys() and value.keys() <= set(required) | set(optional)


def _condition(value):
    if not isinstance(value, dict):
        return False
    if set(value) in ({"all"}, {"any"}):
        parts = next(iter(value.values()))
        return isinstance(parts, list) and bool(parts) and all(_condition(p) for p in parts)
    if not _fields(value, {"fact", "op", "value"}, {"scope"}) or not _text(value["fact"]):
        return False
    if "scope" in value and not _text(value["scope"]):
        return False
    op = value["op"]
    return op == "eq" or op == "in" and isinstance(value["value"], list) and bool(value["value"]) or op == "exists" and type(value["value"]) is bool


def _ref(value, only_method=False):
    if not _fields(value, {"kind", "id"}, {"version", "scope", "when"}):
        return False
    if not _text(value["kind"]) or value["kind"] not in _KINDS or not _text(value["id"]):
        return False
    if only_method and value["kind"] != "method":
        return False
    if value["kind"] == "method" and ("version" not in value or not _version(value["version"])):
        return False
    if "version" in value and not _version(value["version"]):
        return False
    return ("scope" not in value or _text(value["scope"])) and ("when" not in value or _condition(value["when"]))


def _strings(value):
    return isinstance(value, list) and all(_text(v) for v in value)


def _method(value):
    optional = {"applies_when", "does_not_apply_when", "requires", "requires_any", "recommends",
                "conflicts", "supersedes", "stages", "acceptance", "host", "degradation"}
    if not _fields(value, {"id", "version", "dimensions"}, optional):
        return False
    if not _text(value["id"]) or not _version(value["version"]) or not _strings(value["dimensions"]):
        return False
    if not value["dimensions"] or not set(value["dimensions"]) <= _DIMENSIONS or len(set(value["dimensions"])) != len(value["dimensions"]):
        return False
    for field in ("applies_when", "does_not_apply_when"):
        if field in value and not _condition(value[field]):
            return False
    for field in ("requires", "recommends", "conflicts", "supersedes"):
        refs = value.get(field, [])
        if not isinstance(refs, list) or not all(_ref(r, field in {"conflicts", "supersedes"}) for r in refs):
            return False
    groups = value.get("requires_any", [])
    if not isinstance(groups, list):
        return False
    for group in groups:
        if not _fields(group, {"id", "options"}, {"when"}) or not _text(group["id"]):
            return False
        if not isinstance(group["options"], list) or not group["options"] or not all(_ref(r) for r in group["options"]):
            return False
        if "when" in group and not _condition(group["when"]):
            return False
    if len({g["id"] for g in groups}) != len(groups):
        return False
    stages = value.get("stages", {})
    if not isinstance(stages, dict) or not stages.keys() <= _STAGES:
        return False
    if not all(_fields(s, {"consumes", "produces"}) and _strings(s["consumes"]) and _strings(s["produces"]) for s in stages.values()):
        return False
    if "acceptance" in value:
        a = value["acceptance"]
        if not _fields(a, {"required_evidence"}) or not isinstance(a["required_evidence"], list):
            return False
        if not all(_ref(r) and r["kind"] == "evidence" for r in a["required_evidence"]):
            return False
    if "host" in value:
        host = value["host"]
        if not _fields(host, {"requires", "handoff"}) or not isinstance(host["requires"], list) or not _strings(host["handoff"]):
            return False
        if not all(_ref(r) and r["kind"] == "capability" for r in host["requires"]):
            return False
    if "degradation" in value:
        d = value["degradation"]
        if not _fields(d, {"retain", "withdraw"}) or not _strings(d["retain"]) or not _strings(d["withdraw"]):
            return False
    return True


def check_method_composition(payload: Mapping) -> dict:
    """Return stable ``valid/incomplete/invalid`` diagnostics; never adopt methods.

    Scopes are explicit boundary names. ``*`` means a project-wide assertion;
    other names match exactly. ``$scope`` in references means the owner's scope.
    Inferred/unknown facts produce unknown conditions. ``exists: false`` only
    succeeds for a confirmed fact with ``value: null`` (absence is unknown).
    ``stage`` optionally limits stage_requirements; acceptance obligations only
    apply at verify/deliver, and host obligations at implement/review/verify.
    An explicit stage also checks its consumes as scoped artifact/evidence
    inputs. Produces are future outputs and never prerequisites of that stage.
    """
    diagnostics = []
    selected, proposed, pruned, stage_requirements = [], [], [], []
    proposal_only = False

    def diagnostic(code, severity, scope="*", method=None, **detail):
        if proposal_only and severity in {"error", "gap"}:
            detail["proposal_severity"] = severity
            severity = "info"
        item = {"code": code, "severity": severity, "scope": scope, **detail}
        if method is not None:
            item["method"] = method
        diagnostics.append(item)

    def finish():
        unique = {_key(d): d for d in diagnostics}
        levels = {d["severity"] for d in unique.values()}
        status = "invalid" if "error" in levels else "incomplete" if "gap" in levels else "valid"
        return {"schema_version": SCHEMA_VERSION, "status": status,
                "selected": sorted(selected, key=_key), "proposed": sorted(proposed, key=_key),
                "pruned": sorted(pruned, key=_key), "diagnostics": [unique[k] for k in sorted(unique)],
                "stage_requirements": sorted(stage_requirements, key=_key)}

    # JSON is the wire value domain. Serialization is in memory, never to a file.
    try:
        data = json.loads(_key(dict(payload))) if isinstance(payload, Mapping) else None
    except (ValueError, TypeError, RecursionError):
        data = None
    if not _fields(data, {"schema_version", "methods", "selected"}, {"candidates", "facts", "available", "stage"}):
        diagnostic("invalid_input", "error", path=["input"])
        return finish()
    if data["schema_version"] != SCHEMA_VERSION or "stage" in data and (not _text(data["stage"]) or data["stage"] not in _STAGES):
        diagnostic("invalid_input", "error", path=["schema_version_or_stage"])
        return finish()
    for field in ("methods", "selected", "candidates", "facts", "available"):
        if not isinstance(data.get(field, []), list):
            diagnostic("invalid_input", "error", path=[field])
    if diagnostics:
        return finish()

    methods = {}
    for index, method in enumerate(data["methods"]):
        if not _method(method):
            diagnostic("invalid_declaration", "error", path=["methods", index])
            continue
        key = (method["id"], _key(method["version"]))
        if key in methods:
            diagnostic("duplicate_method", "error", method=method["id"], version=method["version"])
        methods[key] = method

    def identity(item):
        return item["id"], _key(item["version"]), item["scope"]

    def normalize_selections(field):
        values, seen = [], set()
        for item in data.get(field, []):
            if not _fields(item, {"id", "version", "scope"}, {"reason"}) or not _text(item["id"]) or not _version(item["version"]) or not _text(item["scope"]) or item["scope"] == "$scope":
                diagnostic("invalid_input", "error", path=[field])
                continue
            if "reason" in item and not _text(item["reason"]):
                diagnostic("invalid_input", "error", path=[field, "reason"])
                continue
            token = identity(item)
            if token in seen:
                diagnostic("duplicate_selection", "error", item["scope"], item["id"], field=field)
            seen.add(token)
            if token[:2] not in methods:
                diagnostic("dangling_method", "error", item["scope"], item["id"], version=item["version"])
            values.append(item)
        return sorted(values, key=_key)

    selected = normalize_selections("selected")
    candidates = normalize_selections("candidates")
    facts, available = {}, []
    for fact in data.get("facts", []):
        if not _fields(fact, {"id", "scope", "status"}, {"value", "source"}) or not _text(fact["id"]) or not _text(fact["scope"]) or not _text(fact["status"]) or fact["status"] not in {"confirmed", "inferred", "unknown"}:
            diagnostic("invalid_input", "error", path=["facts"])
            continue
        if fact["status"] != "unknown" and ("value" not in fact or not _text(fact.get("source"))):
            diagnostic("invalid_input", "error", path=["facts", "source_or_value"])
        key = fact["id"], fact["scope"]
        if key in facts:
            diagnostic("duplicate_fact", "error", fact["scope"], fact=fact["id"])
        facts[key] = fact
    for item in data.get("available", []):
        if not _fields(item, {"kind", "id", "scope", "source"}, {"version"}) or not _text(item["kind"]) or item["kind"] not in _KINDS - {"method"} or not all(_text(item[f]) for f in ("id", "scope", "source")) or "version" in item and not _version(item["version"]):
            diagnostic("invalid_input", "error", path=["available"])
        else:
            available.append(item)
    # Validate all supplied declarations, including unselected method references.
    for method in methods.values():
        refs = [r for field in ("requires", "recommends", "conflicts", "supersedes") for r in method.get(field, [])]
        refs += [r for g in method.get("requires_any", []) for r in g["options"]]
        for ref in refs:
            if ref["kind"] == "method" and (ref["id"], _key(ref["version"])) not in methods:
                diagnostic("dangling_method", "error", method=method["id"], target=ref["id"], version=ref["version"])
    if any(d["severity"] == "error" for d in diagnostics):
        return finish()

    def condition(expr, scope):
        if "all" in expr or "any" in expr:
            operator = "all" if "all" in expr else "any"
            values = [condition(p, scope) for p in expr[operator]]
            if operator == "all":
                return False if False in values else None if None in values else True
            return True if True in values else None if None in values else False
        target = expr.get("scope", "$scope")
        target = scope if target == "$scope" else target
        fact = facts.get((expr["fact"], target), facts.get((expr["fact"], "*")))
        if fact is None or fact["status"] != "confirmed":
            return None
        actual, expected = fact["value"], expr["value"]
        if expr["op"] == "exists":
            return (actual is not None) is expected
        if expr["op"] == "eq":
            return _key(actual) == _key(expected)
        return any(_key(actual) == _key(v) for v in expected)

    def applies(item):
        method = methods[identity(item)[:2]]
        positive = condition(method["applies_when"], item["scope"]) if "applies_when" in method else True
        negative = condition(method["does_not_apply_when"], item["scope"]) if "does_not_apply_when" in method else False
        return False if positive is False or negative is True else None if positive is None or negative is None else True

    def overlap(a, b):
        return a == b or a == "*" or b == "*"

    def target_scope(ref, scope):
        value = ref.get("scope", "$scope")
        return scope if value == "$scope" else value

    def enabled(ref, item):
        value = condition(ref["when"], item["scope"]) if "when" in ref else True
        if value is None:
            diagnostic("unknown_condition", "gap", item["scope"], item["id"], condition=ref["when"])
        return value is True

    def satisfied(ref, scope):
        scope = target_scope(ref, scope)
        if ref["kind"] == "method":
            return any(i["id"] == ref["id"] and _key(i["version"]) == _key(ref["version"]) and (i["scope"] == scope or i["scope"] == "*") and applies(i) is True for i in selected)
        return any(i["kind"] == ref["kind"] and i["id"] == ref["id"] and (i["scope"] == scope or i["scope"] == "*") and ("version" not in ref or _key(i.get("version")) == _key(ref["version"])) for i in available)

    def clashes(a, b, relation="conflicts"):
        for owner, other in ((a, b), (b, a)):
            method = methods[identity(owner)[:2]]
            for ref in method.get(relation, []):
                if ref["id"] == other["id"] and _key(ref["version"]) == _key(other["version"]) and overlap(target_scope(ref, owner["scope"]), other["scope"]) and enabled(ref, owner):
                    return True
        return False

    # Do not collapse selected and inferred dependencies into an active set.
    for item in selected:
        value = applies(item)
        if value is not True:
            diagnostic("not_applicable" if value is False else "unknown_condition", "error" if value is False else "gap", item["scope"], item["id"])
    for pos, item in enumerate(selected):
        for other in selected[pos + 1:]:
            if clashes(item, other):
                diagnostic("method_conflict", "error", item["scope"], item["id"], other=other)
            if clashes(item, other, "supersedes"):
                diagnostic("explicit_superseded", "gap", item["scope"], item["id"], other=other)

    proposed_map, visited = {}, set()
    required_edges, alternative_edges, dependency_items = {}, {}, {}

    def method_dependency(ref, scope):
        scope = target_scope(ref, scope)
        matches = [i for i in selected if i["id"] == ref["id"] and _key(i["version"]) == _key(ref["version"]) and (i["scope"] == scope or i["scope"] == "*") and applies(i) is True]
        if matches:
            return next((i for i in matches if i["scope"] == scope), matches[0])
        return {"id": ref["id"], "version": ref["version"], "scope": scope}

    def check_dependency_cycles():
        # A method can be grounded when every hard method prerequisite is
        # grounded and every method-only OR group has a grounded witness.
        # This avoids treating all alternatives as mandatory (a false cycle).
        nodes = set(dependency_items)
        grounded = set()
        while True:
            ready = {n for n in nodes - grounded if required_edges.get(n, set()) <= grounded and all(group & grounded for group in alternative_edges.get(n, []))}
            if not ready:
                break
            grounded.update(ready)
        remaining = nodes - grounded
        seen = set()

        def find_cycle(node, trail):
            if node in trail:
                return trail[trail.index(node):] + [node]
            if node in seen:
                return None
            seen.add(node)
            edges = required_edges.get(node, set()) | set().union(*alternative_edges.get(node, []))
            for target in sorted(edges & remaining):
                cycle = find_cycle(target, trail + [node])
                if cycle:
                    return cycle
            return None

        for token in sorted(remaining):
            cycle = find_cycle(token, [])
            if cycle:
                item = dependency_items[token]
                labels = [f"{dependency_items[t]['id']}@{dependency_items[t]['version']}[{dependency_items[t]['scope']}]" for t in cycle]
                diagnostic("dependency_cycle", "error", item["scope"], item["id"], path=labels)

    def propose(item, reason):
        if identity(item) not in {identity(i) for i in selected}:
            token = identity(item)
            entry = proposed_map.setdefault(token, {"id": item["id"], "version": item["version"], "scope": item["scope"], "reasons": []})
            if reason not in entry["reasons"]:
                entry["reasons"].append(reason)

    def walk(item, path):
        token = identity(item)
        dependency_items[token] = item
        label = f"{item['id']}@{item['version']}[{item['scope']}]"
        if token in [t for t, _ in path]:
            diagnostic("dependency_cycle", "error", item["scope"], item["id"], path=[p for _, p in path] + [label])
            return
        if token in visited:
            return
        visited.add(token)
        if applies(item) is not True:
            if token not in {identity(i) for i in selected}:
                diagnostic("dependency_not_applicable" if applies(item) is False else "unknown_condition", "error" if applies(item) is False else "gap", item["scope"], item["id"])
            return
        method = methods[token[:2]]
        stages = method.get("stages", {})
        if "stage" in data:
            stages = {k: v for k, v in stages.items() if k == data["stage"]}
        stage_requirements.append({"id": item["id"], "version": item["version"], "scope": item["scope"], "adopted": token in {identity(i) for i in selected}, "stages": deepcopy(stages)})
        if "stage" in data:
            for resource in sorted(method.get("stages", {}).get(data["stage"], {}).get("consumes", [])):
                present = any(a["kind"] in {"artifact", "evidence"} and a["id"] == resource and (a["scope"] == item["scope"] or a["scope"] == "*") for a in available)
                if not present:
                    diagnostic("artifact_missing", "gap", item["scope"], item["id"], obligation={"kind": "artifact", "id": resource}, stage=data["stage"], source="stages.consumes")
        refs = list(method.get("requires", []))
        if data.get("stage") in {"verify", "deliver"}:
            refs += method.get("acceptance", {}).get("required_evidence", [])
        if data.get("stage") in {"implement", "review", "verify"}:
            refs += method.get("host", {}).get("requires", [])
        for ref in sorted(refs, key=_key):
            if not enabled(ref, item):
                continue
            scope = target_scope(ref, item["scope"])
            is_satisfied = satisfied(ref, item["scope"])
            if not is_satisfied:
                code = "method_not_adopted" if ref["kind"] == "method" else f"{ref['kind']}_missing"
                diagnostic(code, "gap", scope, item["id"], obligation=ref)
            if ref["kind"] == "method":
                dependency = method_dependency(ref, item["scope"])
                if not is_satisfied:
                    propose(dependency, f"required_by:{label}")
                required_edges.setdefault(token, set()).add(identity(dependency))
                walk(dependency, path + [(token, label)])
        for group in sorted(method.get("requires_any", []), key=_key):
            if not enabled(group, item):
                continue
            conditions = [(r, condition(r["when"], item["scope"]) if "when" in r else True) for r in group["options"]]
            options = [r for r, state in conditions if state is True]
            # A confirmed satisfied branch discharges the group; unknown
            # alternatives are irrelevant and must not block the adopted scope.
            satisfied_options = [r for r in options if satisfied(r, item["scope"])]
            if not satisfied_options:
                for ref, state in conditions:
                    if state is None:
                        diagnostic("unknown_condition", "gap", item["scope"], item["id"], condition=ref["when"])
                diagnostic("requires_any_unsatisfied", "gap", item["scope"], item["id"], group=group["id"], options=sorted([r for r, state in conditions if state is not False], key=_key))
                # A single certain method alternative is a necessary proposal,
                # never an adoption. Multiple alternatives stay undecided.
                if len(options) == 1 and all(state is not None for _, state in conditions) and options[0]["kind"] == "method":
                    dependency = method_dependency(options[0], item["scope"])
                    propose(dependency, f"required_any_by:{label}:{group['id']}")
                    alternative_edges.setdefault(token, []).append({identity(dependency)})
                    walk(dependency, [])
            elif all(r["kind"] == "method" for r in satisfied_options):
                dependencies = [method_dependency(r, item["scope"]) for r in satisfied_options]
                alternative_edges.setdefault(token, []).append({identity(d) for d in dependencies})
                # Inspect each already approved option's obligations without
                # asserting that all OR branches are required at once.
                for dependency in sorted(dependencies, key=_key):
                    walk(dependency, [])
        for ref in sorted(method.get("recommends", []), key=_key):
            if enabled(ref, item) and not satisfied(ref, item["scope"]):
                diagnostic("recommendation", "info", target_scope(ref, item["scope"]), item["id"], obligation=ref)

    for item in selected:
        walk(item, [])
    check_dependency_cycles()
    required_proposals = set(proposed_map)
    # Evaluate caller candidates only after required closure is known.
    proposal_only = True
    for item in candidates:
        if identity(item) in {identity(i) for i in selected} or identity(item) in proposed_map:
            continue
        value = applies(item)
        reason = None
        if not item.get("reason"):
            reason = "no_current_reason"
        elif value is False:
            reason = "not_applicable"
        elif value is None:
            reason = "needs_facts"
        elif any(clashes(item, s) for s in selected):
            reason = "conflicts_with_selected"
        elif any(clashes(item, s, "supersedes") for s in selected):
            reason = "replacement_needs_decision"
        if reason:
            pruned.append({"id": item["id"], "version": item["version"], "scope": item["scope"], "reason": reason})
        else:
            propose(item, item["reason"])
            walk(item, [])
    check_dependency_cycles()
    proposed = list(proposed_map.values())
    for item in proposed:
        item["reasons"].sort()
        proposal_only = identity(item) not in required_proposals
        for adopted in selected:
            if clashes(item, adopted):
                diagnostic("dependency_conflict", "error", item["scope"], item["id"], other=adopted)
    proposal_only = False
    required_items = [item for item in proposed if identity(item) in required_proposals]
    for pos, item in enumerate(required_items):
        for other in required_items[pos + 1:]:
            if clashes(item, other):
                diagnostic("dependency_conflict", "error", item["scope"], item["id"], other=other)
    return finish()
