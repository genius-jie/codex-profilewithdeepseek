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
$gatewayPath = "@@USERPROFILE:win@@\AppData\Roaming\com.codexmanager.desktop\codex-profiles\36ec6912363378718309ab2c8fb2ec264afaaf895549658cca6919bdabcc4ee3\gateway-models.json"

$pythonScript = @"
import json, os

catalog_path = r'$catalogPath'
cache_path = r'$cachePath'
gateway_path = r'$gatewayPath'

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
    }
]

# GLM is supplied by the gateway catalog, but that catalog historically left
# reasoning levels empty. Keep the gateway's model metadata and patch only the
# shared third-party capability fields so the Codex++ picker and the existing
# Responses -> Chat adapter use the same reasoning contract as DeepSeek/Kimi.
glm_reasoning_levels = [
    {"effort": effort, "description": ""}
    for effort in ["low", "medium", "high", "xhigh", "ultra", "max"]
]
glm_slugs = {"glm-5.2", "glm-5.3", "glm-5.3-flash"}

# Image support is a consumer-facing capability contract. Keep it in this
# single sync source so the picker, cache, and gateway mirror cannot drift.
# The DeepSeek entries are covered by the existing 15740 content-aware route;
# Kimi K3, Qwen 3.8 Max/Flash, and GLM-5.3-Flash are confirmed Chat
# Completions vision models. Qwen must stay on the active A2Agent route; the
# retired omnimodel route rejects image input and is disabled separately.
image_input_modalities = {
    "deepseek-v4-pro": ["text", "image"],
    "deepseek-v4.1-flash": ["text", "image"],
    "kimi-k3": ["text", "image"],
    "qwen3.8-max": ["text", "image"],
    "qwen3.8-flash": ["text", "image"],
    "glm-5.3-flash": ["text", "image"],
}

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
patch_glm_reasoning(catalog_path)
patch_glm_reasoning(gateway_path)
patch_glm_reasoning(cache_path)
patch_image_modalities(catalog_path)
patch_image_modalities(gateway_path)
patch_image_modalities(cache_path)
"@

# Run python sync silently
python -c $pythonScript

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
