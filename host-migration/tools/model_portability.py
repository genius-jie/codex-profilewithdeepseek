"""Narrow export-time portability fixes; live service sources are never edited."""
from __future__ import annotations
import re


def transform_adapter(label: str, text: str, powershell_exe: str):
    changes = []
    if label == "adapter/install-codex-id-sanitizer-nssm.ps1":
        old = "$powershell = Join-Path $PSHOME 'powershell.exe'"
        if old in text:
            text = text.replace(old, "$powershell = '" + powershell_exe + "'")
            changes.append("use the selected absolute PowerShell 7 executable in the service")
    if label == "adapter/install-cc-switch-sanitizer-supervisor-service.ps1":
        if "'powershell.exe'" in text:
            text = text.replace("'powershell.exe'", "'" + powershell_exe + "'")
            changes.append("use the selected absolute PowerShell 7 executable for the canonical supervisor")
        text, replaced = re.subn(
            r"(?m)^\$nssm = '([^'\r\n]*\\system32\\nssm\.exe)'[ \t]*$",
            lambda match: "$nssmCommand = Get-Command nssm.exe -ErrorAction SilentlyContinue\n$nssm = if ($nssmCommand) { $nssmCommand.Source } else { '" + match[1] + "' }",
            text, flags=re.IGNORECASE)
        if replaced:
            changes.append("resolve NSSM from the target machine PATH before the existing System32 fallback")
    if label == "adapter/start-cc-switch-sanitizer-supervisor.ps1":
        text, replaced = re.subn(r"(?m)^\$deepseekProviderId\s*=\s*'[0-9a-fA-F-]{36}'[ \t]*$", lambda _: "$deepseekProviderId = $env:CC_SWITCH_DEEPSEEK_PROVIDER_ID", text)
        if replaced:
            text = text.replace("function Ensure-ClaudeDeepSeekSettings {", "function Ensure-ClaudeDeepSeekSettings {\n  if (-not $deepseekProviderId) { return }")
            changes.append("do not reuse the original machine provider ID; settings repair is opt-in")
        if "$qwenUpstream =" not in text:
            marker = "$deepseekProviderId = $env:CC_SWITCH_DEEPSEEK_PROVIDER_ID"
            text = text.replace(marker, marker + "\n$qwenUpstream = if ($env:CC_SWITCH_QWEN_UPSTREAM) { $env:CC_SWITCH_QWEN_UPSTREAM } else { 'https://api.a2agent.me' }\n$glmUpstream = if ($env:CC_SWITCH_GLM_UPSTREAM) { $env:CC_SWITCH_GLM_UPSTREAM } else { 'https://api.a2agent.me' }")
            text = text.replace("Name = 'qwen'; Port = '15727'; Upstream = 'https://api.a2agent.me'", "Name = 'qwen'; Port = '15727'; Upstream = $qwenUpstream")
            text = text.replace("READ_SANITIZER_PORT = '15727'; READ_SANITIZER_UPSTREAM = 'https://api.a2agent.me'", "READ_SANITIZER_PORT = '15727'; READ_SANITIZER_UPSTREAM = $qwenUpstream")
            text = text.replace("Name = 'glm'; Port = '15726'; Upstream = 'https://api.a2agent.me'", "Name = 'glm'; Port = '15726'; Upstream = $glmUpstream")
            text = text.replace("READ_SANITIZER_PORT = '15726'; READ_SANITIZER_UPSTREAM = 'https://api.a2agent.me'", "READ_SANITIZER_PORT = '15726'; READ_SANITIZER_UPSTREAM = $glmUpstream")
            changes.append("allow explicit Qwen/GLM upstream selection while preserving the observed default route")
    return text, changes
