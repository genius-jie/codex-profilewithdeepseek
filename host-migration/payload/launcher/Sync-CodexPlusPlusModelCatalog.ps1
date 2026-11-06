#requires -Version 7.0
<#
.SYNOPSIS
    Guarantees that third-party models (qwen3.8-max, deepseek-v4-pro, kimi-k3,
    glm-5.2, glm-5.3, glm-5.3-flash)
    and custom configurations are never lost on Codex++ startup.
#>

param(
    [string]$ProfileRoot = "@@CODEXPP_HOME:win@@"
)

$ErrorActionPreference = "Stop"

$catalogPath = Join-Path $ProfileRoot "model_catalog.json"
$cachePath = Join-Path $ProfileRoot "models_cache.json"
$configPath = Join-Path $ProfileRoot "config.toml"
$authPath = Join-Path $ProfileRoot "auth.json"
$allowlistPath = Join-Path $ProfileRoot "gateway-model-allowlist.json"
# CodexManager 0.6.x keeps its model table in a SQLite database and no longer
# exports the per-profile gateway-models.json that older builds wrote, so the
# live gateway ingress is the only authoritative source for what is configured.
$gatewayPath = Join-Path $ProfileRoot "gateway-models.json"

$pythonScript = @"
import json, os, re, urllib.request

catalog_path = r'$catalogPath'
cache_path = r'$cachePath'
gateway_path = r'$gatewayPath'
config_path = r'$configPath'
auth_path = r'$authPath'
allowlist_path = r'$allowlistPath'

custom_models_def = [
    {
        "slug": "deepseek-v4-pro",
        "display_name": "DeepSeek-V4-Pro",
        "description": "DeepSeek V4 Pro (Unlocked 872k context)",
        "provider": "custom",
        "family": "deepseek",
        "category": "chat",
        "tags": ["custom", "fast", "unlocked"],
        "origin": "custom",
        "enabled": True,
        "supported_in_api": True,
        "visibility": "list",
        "sort_order": 50,
        "context_window": 872000,
        "max_context_window": 1000000,
        # CodexManager rejects requests above 1,048,576 characters. DeepSeek
        # tool histories reached 2MB before the old 900k-token threshold, so
        # compact this provider well before the gateway character ceiling.
        "auto_compact_token_limit": 160000,
        "default_reasoning_effort": "medium",
        "supported_reasoning_efforts": ["low", "medium", "high", "ultra"],
        "capabilities": {
            "supports_tools": True,
            "supports_streaming": True,
            "supports_multimodal": True
        }
    },
    {
        "slug": "qwen3.8-max",
        "display_name": "Qwen-3.8-Max",
        "description": "Qwen 3.8 Max (Unlocked 872k context)",
        "provider": "custom",
        "family": "qwen",
        "category": "chat",
        "tags": ["custom", "flagship", "unlocked"],
        "origin": "custom",
        "enabled": True,
        "supported_in_api": True,
        "visibility": "list",
        "sort_order": 60,
        "context_window": 872000,
        "max_context_window": 1000000,
        "auto_compact_token_limit": 900000,
        "default_reasoning_effort": "medium",
        "supported_reasoning_efforts": ["low", "medium", "high", "ultra"],
        "capabilities": {
            "supports_tools": True,
            "supports_streaming": True,
            "supports_multimodal": True
        }
    },
    {
        "slug": "kimi-k3",
        "display_name": "Kimi-K3",
        "description": "Kimi K3 (Unlocked 872k context)",
        "provider": "custom",
        "family": "kimi",
        "category": "chat",
        "tags": ["custom", "flagship", "unlocked"],
        "origin": "custom",
        "enabled": True,
        "supported_in_api": True,
        "visibility": "list",
        "sort_order": 70,
        "context_window": 872000,
        "max_context_window": 1000000,
        "auto_compact_token_limit": 900000,
        "default_reasoning_effort": "medium",
        "supported_reasoning_efforts": ["low", "medium", "high", "ultra"],
        "capabilities": {
            "supports_tools": True,
            "supports_streaming": True,
            "supports_multimodal": True
        }
    },
    {
        "slug": "deepseek-v4.1-flash",
        "display_name": "DeepSeek-V4.1-Flash",
        "description": "DeepSeek V4.1 Flash (200k context, image input)",
        "provider": "custom",
        "family": "deepseek",
        "category": "chat",
        "tags": ["custom", "fast", "vision"],
        "origin": "custom",
        "enabled": True,
        "supported_in_api": True,
        "visibility": "list",
        "sort_order": 66,
        "context_window": 200000,
        "max_context_window": 200000,
        # Same gateway ceiling as V4 Pro: CodexManager rejects requests above
        # 1,048,576 characters, and this model is the 15740 image reroute
        # target, so its history grows fastest.
        "auto_compact_token_limit": 160000,
        "default_reasoning_effort": "medium",
        "supported_reasoning_efforts": ["low", "medium", "high", "ultra"],
        "capabilities": {
            "supports_tools": True,
            "supports_streaming": True,
            "supports_multimodal": True
        }
    }
]

# GLM is supplied by the gateway catalog, but that catalog historically left
# reasoning levels empty. Keep the gateway's model metadata and patch only the
# shared third-party capability fields so the Codex++ picker and the existing
# Responses -> Chat adapter use the same reasoning contract as DeepSeek/Kimi.
glm_reasoning_levels = [
    {"effort": effort, "description": ""}
    for effort in ["low", "medium", "high", "xhigh", "max", "ultra"]
]
glm_slugs = {"glm-5.2", "glm-5.3", "glm-5.3-flash"}

# Every selectable model needs a non-empty ladder, and the picker renders the
# list in order, so the highest level (ultra) must sit last. Gateway-supplied
# models arrive with an empty list after a Codex update, which leaves the level
# control blank; fill and normalize them from this single source.
reasoning_ladder = [
    {"effort": effort, "description": ""}
    for effort in ["low", "medium", "high", "xhigh", "max", "ultra"]
]
ladder_order = [item["effort"] for item in reasoning_ladder]

# Image support is a consumer-facing capability contract. Keep it in this
# single sync source so the picker, cache, and gateway mirror cannot drift.
# The DeepSeek entries are covered by the existing 15740 content-aware route;
# Kimi K3, Qwen 3.8 Max/Flash, and GLM-5.3-Flash are confirmed Chat
# Completions vision models. Qwen must stay on the active A2Agent route; the
# retired omnimodel route rejects image input and is disabled separately.
image_input_modalities = {
    "deepseek-v4-pro": ["text", "image"],
    "deepseek-v4.1-flash": ["text", "image"],
    "deepseek-v4.1-flash-1017": ["text", "image"],
    "kimi-k3": ["text", "image"],
    "qwen3.8-max": ["text", "image"],
    "qwen3.8-flash": ["text", "image"],
    "glm-5.3-flash": ["text", "image"],
}

# The picker must expose exactly what CodexManager has configured. The gateway
# reports only id/display_name, so a gateway model missing from the catalog
# inherits its capability shape from the closest sibling entry; inventing a
# context window or tool mode would let the picker offer a model that Codex
# then misdrives.
family_templates = [
    ("deepseek-v4.1-flash", "deepseek-v4-pro"),
    ("deepseek-v4", "deepseek-v4-pro"),
    ("glm-", "glm-5.3"),
    ("MiniMax-", "MiniMax-M3"),
    ("kimi-", "kimi-k3"),
    ("qwen3.8", "qwen3.8-max"),
    ("gpt-6.1-", "gpt-6.1-sol"),
    ("gpt-6-", "gpt-6-astra"),
    ("gpt-5.6-", "gpt-5.6-sol"),
]
# Image generation endpoints are not chat models; Codex cannot drive them as a
# conversation backend, so they stay out of the picker even when configured.
excluded_prefixes = ("gpt-image-",)
# OpenAI models below this major.minor stay out of the picker even while the
# gateway still serves them, so an account pool change cannot re-expose them.
minimum_openai_model = (6, 0)

def below_openai_floor(slug):
    text = str(slug or '')
    if not text.startswith('gpt-'):
        return False
    parts = [p for p in re.split(r'[^0-9]+', text[4:]) if p]
    if not parts:
        return True
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    return (major, minor) < minimum_openai_model

def read_gateway_allowlist():
    """Ask the configured ingress what it actually serves."""
    try:
        config_text = open(config_path, encoding='utf-8-sig').read()
        auth = json.load(open(auth_path, encoding='utf-8-sig'))
    except Exception:
        return None
    base = ''
    inside_cm = False
    for line in config_text.splitlines():
        stripped = line.strip()
        if stripped.startswith('['):
            inside_cm = 'model_providers.cm' in stripped
            continue
        if inside_cm and stripped.startswith('base_url'):
            base = stripped.split('=', 1)[1].strip().strip('"').strip("'")
            break
    key = str(auth.get('OPENAI_API_KEY') or '')
    if not base or not key:
        return None
    try:
        request = urllib.request.Request(base.rstrip('/') + '/models',
                                         headers={'Authorization': 'Bearer ' + key})
        rows = json.load(urllib.request.urlopen(request, timeout=20)).get('data') or []
    except Exception:
        return None
    ids = sorted({str(row.get('id')) for row in rows if isinstance(row, dict) and row.get('id')})
    return ids or None

def load_saved_allowlist():
    try:
        rows = json.load(open(allowlist_path, encoding='utf-8')).get('ids') or []
    except Exception:
        return None
    return [str(x) for x in rows if x] or None

def save_allowlist(ids):
    try:
        with open(allowlist_path, 'w', encoding='utf-8') as f:
            json.dump({'schema_version': 'gateway-model-allowlist.v1', 'ids': ids}, f,
                      ensure_ascii=False, indent=2)
    except Exception:
        pass

def restrict_to_gateway(file_path, allowed):
    if not os.path.exists(file_path) or not allowed:
        return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return
    models = data.get('models', [])
    if not isinstance(models, list) or not models:
        return
    templates = {m.get('slug'): m for m in models if isinstance(m, dict)}
    present = set(templates)
    allowed_set = set(allowed)
    modified = False
    for slug in allowed:
        if slug in present or slug.startswith(excluded_prefixes) or below_openai_floor(slug):
            continue
        sibling = None
        # Prefer the catalog entry the new id is derived from: a dated variant
        # such as deepseek-v4.1-flash-1017 shares its real context ceiling with
        # deepseek-v4.1-flash, not with the 872k V4 Pro sibling.
        parents = sorted((s for s in templates if s and slug.startswith(s)), key=len, reverse=True)
        if parents:
            sibling = templates[parents[0]]
        else:
            for prefix, candidate in family_templates:
                if slug.startswith(prefix) and candidate in templates:
                    sibling = templates[candidate]
                    break
        if sibling is None:
            continue
        clone = json.loads(json.dumps(sibling))
        clone['slug'] = slug
        clone['display_name'] = slug
        clone['visibility'] = 'list'
        models.append(clone)
        templates[slug] = clone
        present.add(slug)
        modified = True
        print('Added gateway model from sibling shape: ' + slug)
    for model in models:
        if not isinstance(model, dict):
            continue
        slug = model.get('slug')
        wanted = 'list' if slug in allowed_set and not below_openai_floor(slug) else 'hide'
        if model.get('visibility') != wanted:
            model['visibility'] = wanted
            modified = True
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print('Restricted picker to gateway-configured models in: ' + file_path)

def ensure_models_in_file(file_path):
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return
    
    models = data.get('models', [])
    existing_slugs = {m.get('slug') for m in models}
    modified = False
    
    # Check and update or insert custom models
    for cm in custom_models_def:
        slug = cm['slug']
        found = False
        for i, m in enumerate(models):
            if m.get('slug') == slug:
                found = True
                # Update only the lifecycle budget fields. Preserve the
                # gateway's current capability, reasoning, and routing
                # metadata instead of replacing the whole model object when
                # a compaction threshold changes.
                for key in ('context_window', 'max_context_window', 'auto_compact_token_limit'):
                    if m.get(key) != cm.get(key):
                        m[key] = cm.get(key)
                        modified = True
                break
        if not found:
            models.append(cm)
            modified = True
            
    if modified:
        data['models'] = models
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Ensured custom models in: {file_path}")

def patch_glm_reasoning(file_path):
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return
    models = data.get('models', [])
    modified = False
    for model in models:
        if not isinstance(model, dict) or model.get('slug') not in glm_slugs:
            continue
        desired = {
            "supported_reasoning_levels": glm_reasoning_levels,
            "default_reasoning_level": "ultra",
            "supports_reasoning_summaries": True,
            "supports_reasoning_summary_parameter": True,
            "shell_type": "unified_exec",
            "tool_mode": "code_mode_only",
            "supports_parallel_tool_calls": True,
        }
        for key, value in desired.items():
            if model.get(key) != value:
                model[key] = value
                modified = True
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Patched GLM reasoning contract in: {file_path}")

def patch_reasoning_levels(file_path):
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return
    models = data.get('models', [])
    modified = False
    max_position = ladder_order.index('max')
    for model in models:
        if not isinstance(model, dict):
            continue
        levels = model.get('supported_reasoning_levels')
        if not isinstance(levels, list) or not levels:
            model['supported_reasoning_levels'] = list(reasoning_ladder)
            modified = True
            levels = model['supported_reasoning_levels']
        else:
            def rank(level):
                effort = str(level.get('effort')) if isinstance(level, dict) else ''
                return ladder_order.index(effort) if effort in ladder_order else max_position
            ordered = sorted(levels, key=rank)
            if ordered != levels:
                model['supported_reasoning_levels'] = ordered
                modified = True
        # Switching a model must land on max every time. A model that does not
        # expose max falls back to the highest level it does expose, so the
        # default can never point at a level the picker has no button for.
        efforts = [str(level.get('effort')) for level in levels if isinstance(level, dict)]
        wanted_default = 'max' if 'max' in efforts else (efforts[-1] if efforts else '')
        if wanted_default and model.get('default_reasoning_level') != wanted_default:
            model['default_reasoning_level'] = wanted_default
            modified = True
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Patched reasoning level contract in: {file_path}")

def patch_image_modalities(file_path):
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return
    models = data.get('models', [])
    modified = False
    for model in models:
        if not isinstance(model, dict):
            continue
        slug = model.get('slug')
        desired = image_input_modalities.get(slug)
        if desired is None:
            continue
        if model.get('input_modalities') != desired:
            model['input_modalities'] = desired
            modified = True
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Patched third-party image modality contract in: {file_path}")

def merge_gateway_models(target_path, source_path):
    if not os.path.exists(target_path) or not os.path.exists(source_path):
        return
    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            target = json.load(f)
        with open(source_path, 'r', encoding='utf-8') as f:
            source = json.load(f)
    except Exception:
        return

    target_models = target.get('models', [])
    existing_slugs = {m.get('slug') for m in target_models if isinstance(m, dict)}
    added = 0
    for model in source.get('models', []):
        if not isinstance(model, dict):
            continue
        slug = model.get('slug')
        if not slug or slug in existing_slugs:
            continue
        target_models.append(model)
        existing_slugs.add(slug)
        added += 1

    if added:
        target['models'] = target_models
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(target, f, ensure_ascii=False, indent=2)
        print(f"Merged {added} gateway models into: {target_path}")

merge_gateway_models(catalog_path, gateway_path)
merge_gateway_models(cache_path, gateway_path)
ensure_models_in_file(catalog_path)
ensure_models_in_file(gateway_path)
ensure_models_in_file(cache_path)
# Fall back to the last known-good allowlist so a cold start with CodexManager
# not up yet cannot blank the picker.
gateway_ids = read_gateway_allowlist()
if gateway_ids is None:
    gateway_ids = load_saved_allowlist()
    if gateway_ids:
        print('Gateway unreachable; reusing saved allowlist (' + str(len(gateway_ids)) + ' models)')
else:
    save_allowlist(gateway_ids)
restrict_to_gateway(catalog_path, gateway_ids)
restrict_to_gateway(cache_path, gateway_ids)
patch_glm_reasoning(catalog_path)
patch_glm_reasoning(gateway_path)
patch_glm_reasoning(cache_path)
patch_reasoning_levels(catalog_path)
patch_reasoning_levels(gateway_path)
patch_reasoning_levels(cache_path)
patch_image_modalities(catalog_path)
patch_image_modalities(gateway_path)
patch_image_modalities(cache_path)
"@

# Run python sync silently. Resolve the interpreter by its pinned physical
# path: a bare "python" resolves to the Microsoft Store alias on a fresh
# Windows host, which exits without running the patch block.
& '@@PYTHON_EXE:win@@' -c $pythonScript

# Ensure config.toml points to model_catalog.json
if (Test-Path -LiteralPath $configPath) {
    $configContent = [System.IO.File]::ReadAllText($configPath, [System.Text.Encoding]::UTF8)
    $targetLine = "model_catalog_json = '@@CODEXPP_HOME:win@@\model_catalog.json'"
    $pattern = "model_catalog_json\s*=\s*['`"][^'`"]+['`"]"
    
    if ($configContent -match $pattern) {
        $matchedLine = $Matches[0]
        if ($matchedLine -ne $targetLine) {
            $configContent = $configContent -replace $pattern, $targetLine
            [System.IO.File]::WriteAllText($configPath, $configContent, (New-Object System.Text.UTF8Encoding $false))
            Write-Host "[MODEL-GUARD] Restored model_catalog_json pointer in config.toml" -ForegroundColor Yellow
        }
    }
}
