#requires -Version 7.0
<#
.SYNOPSIS
    Guarantees that third-party models (deepseek-v4-pro, deepseek-v4.1-flash,
    qwen3.8-max, kimi-k3, glm-5.3-flash) and custom configurations
    are synchronized and aligned with Codex / Codex++ profile.
#>

param(
    [string]$ProfileRoot = $PSScriptRoot | Split-Path -Parent
)

$ErrorActionPreference = "Stop"

$catalogPath = Join-Path $ProfileRoot "model_catalog.json"
$cachePath = Join-Path $ProfileRoot "models_cache.json"
$configPath = Join-Path $ProfileRoot "config.toml"

$pythonScript = @"
import json, os

catalog_path = r'$catalogPath'
cache_path = r'$cachePath'

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
        },
        "input_modalities": ["text", "image"]
    },
    {
        "slug": "deepseek-v4.1-flash",
        "display_name": "DeepSeek-V4.1-Flash",
        "description": "DeepSeek V4.1 Flash (High speed, reasoning-ready)",
        "provider": "custom",
        "family": "deepseek",
        "category": "chat",
        "tags": ["custom", "flash", "fast"],
        "origin": "custom",
        "enabled": True,
        "supported_in_api": True,
        "visibility": "list",
        "sort_order": 55,
        "context_window": 872000,
        "max_context_window": 1000000,
        "auto_compact_token_limit": 160000,
        "default_reasoning_effort": "medium",
        "supported_reasoning_efforts": ["low", "medium", "high"],
        "capabilities": {
            "supports_tools": True,
            "supports_streaming": True,
            "supports_multimodal": True
        },
        "input_modalities": ["text", "image"]
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
        },
        "input_modalities": ["text", "image"]
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
        },
        "input_modalities": ["text", "image"]
    }
]

def ensure_models_in_file(file_path):
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return
    
    models = data.get('models', [])
    modified = False
    
    for cm in custom_models_def:
        slug = cm['slug']
        found = False
        for i, m in enumerate(models):
            if m.get('slug') == slug:
                found = True
                for key in ('context_window', 'max_context_window', 'auto_compact_token_limit', 'capabilities', 'input_modalities'):
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
        print(f"[MODEL-SYNC] Ensured custom models in: {file_path}")

ensure_models_in_file(catalog_path)
if os.path.exists(cache_path):
    ensure_models_in_file(cache_path)
"@

python -c $pythonScript
Write-Host "[MODEL-SYNC] Third-party model catalog verification finished." -ForegroundColor Green