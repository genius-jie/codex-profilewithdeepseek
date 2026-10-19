#!/usr/bin/env python3
"""S45 deterministic transport adapter for external model providers.

The current Agent owns semantic decisions. This module only owns credentials,
transport, provider quirks, syntactic validation, and redacted receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SKILL_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = SKILL_ROOT / "config"
CONTRACT_PATH = CONFIG_DIR / "provider-profiles.json"
SCHEMA_PATH = CONFIG_DIR / "provider-profiles.schema.json"
CREDENTIAL_PATH = CONFIG_DIR / "provider-credentials.env"
FINAL_MARKER = "<<<S45_FINAL>>>"


class ContractError(RuntimeError):
    """Raised when the physical provider contract is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path}")
    return value


def load_credentials(path: Path = CREDENTIAL_PATH) -> dict[str, str]:
    credentials: dict[str, str] = {}
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ContractError(
                f"Invalid credential assignment at {path}:{line_number}"
            )
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if not name:
            raise ContractError(f"Empty credential name at {path}:{line_number}")
        if name in credentials:
            raise ContractError(f"Duplicate credential name: {name}")
        credentials[name] = value
    return credentials


def atomic_write(path: Path, content: str) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def validate_contract() -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    contract = load_json(CONTRACT_PATH)
    schema = load_json(SCHEMA_PATH)
    credentials = load_credentials()
    errors: list[str] = []

    try:
        from jsonschema import Draft202012Validator, FormatChecker

        validator = Draft202012Validator(
            schema, format_checker=FormatChecker()
        )
        for error in sorted(
            validator.iter_errors(contract), key=lambda item: list(item.path)
        ):
            location = ".".join(str(part) for part in error.path) or "$"
            errors.append(f"schema:{location}:{error.message}")
    except ImportError:
        errors.append("dependency:jsonschema is required")

    required = contract.get("required_credentials", [])
    if not isinstance(required, list):
        required = []
        errors.append("contract:required_credentials must be an array")

    required_set = set(required)
    actual_set = set(credentials)
    missing = sorted(required_set - actual_set)
    extra = sorted(actual_set - required_set)
    empty = sorted(name for name in required_set if not credentials.get(name, ""))
    if missing:
        errors.append("credentials:missing:" + ",".join(missing))
    if extra:
        errors.append("credentials:unexpected:" + ",".join(extra))
    if empty:
        errors.append("credentials:empty:" + ",".join(empty))

    defaults = contract.get("global_defaults", {})
    if defaults.get("sdk_max_retries") != 0:
        errors.append("retry:sdk_max_retries must be 0")
    if defaults.get("transport_retries_max") != 1:
        errors.append("retry:transport_retries_max must be 1")
    if defaults.get("response_repair_retries_max") != 1:
        errors.append("retry:response_repair_retries_max must be 1")

    providers = contract.get("providers", {})
    if isinstance(providers, dict):
        for provider_name, profile in providers.items():
            if not isinstance(profile, dict):
                errors.append(f"provider:{provider_name}:profile must be object")
                continue
            env_name = profile.get("api_key_env")
            if env_name not in required_set:
                errors.append(
                    f"provider:{provider_name}:unknown api_key_env:{env_name}"
                )
            roles = profile.get("model_roles", {})
            if profile.get("default_model") not in set(roles.values()):
                errors.append(
                    f"provider:{provider_name}:default_model missing from model_roles"
                )

    receipt = {
        "contract": contract.get("contract_version"),
        "status": "PASS" if not errors else "FAIL",
        "checked_at": utc_now(),
        "skill_root": str(SKILL_ROOT),
        "credential_source": str(CREDENTIAL_PATH),
        "credential_file_sha256": sha256_file(CREDENTIAL_PATH),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "credential_count": len(credentials),
        "credentials": [
            {
                "env": name,
                "present": bool(credentials.get(name)),
                "length": len(credentials.get(name, "")),
            }
            for name in required
        ],
        "provider_count": len(providers) if isinstance(providers, dict) else 0,
        "errors": errors,
    }
    return contract, credentials, receipt


def require_valid_contract() -> tuple[dict[str, Any], dict[str, str]]:
    contract, credentials, receipt = validate_contract()
    if receipt["status"] != "PASS":
        raise ContractError("; ".join(receipt["errors"]))
    return contract, credentials


def provider_profile(
    contract: dict[str, Any], provider_name: str
) -> dict[str, Any]:
    providers = contract.get("providers", {})
    profile = providers.get(provider_name) if isinstance(providers, dict) else None
    if not isinstance(profile, dict):
        available = ", ".join(sorted(providers)) if isinstance(providers, dict) else ""
        raise ContractError(
            f"Unknown provider '{provider_name}'. Available: {available}"
        )
    return profile


def provider_key(
    profile: dict[str, Any], credentials: dict[str, str]
) -> tuple[str, str]:
    env_name = str(profile["api_key_env"])
    value = credentials.get(env_name, "")
    if not value:
        raise ContractError(f"Credential is empty: {env_name}")
    return env_name, value


def classify_http_status(status: int | None) -> str:
    if status in (401, 403):
        return "AUTH_OR_PERMISSION"
    if status == 429:
        return "RATE_LIMIT"
    if status is not None and status >= 500:
        return "PROVIDER_SERVER_ERROR"
    if status is not None and status >= 400:
        return "PROVIDER_REQUEST_ERROR"
    return "TRANSPORT_ERROR"


def error_status(exc: BaseException) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def parse_model_payload(payload: dict[str, Any], parser_name: str) -> list[str]:
    models: list[str] = []
    if parser_name == "openai":
        values = payload.get("data", [])
        if isinstance(values, list):
            for value in values:
                if isinstance(value, dict) and value.get("id"):
                    models.append(str(value["id"]))
    elif parser_name == "google":
        values = payload.get("models", [])
        if isinstance(values, list):
            for value in values:
                if not isinstance(value, dict):
                    continue
                methods = value.get("supportedGenerationMethods") or []
                if methods and "generateContent" not in methods:
                    continue
                name = value.get("name") or value.get("id")
                if name:
                    models.append(str(name).removeprefix("models/"))
    else:
        raise ContractError(f"Unsupported model list parser: {parser_name}")
    return sorted(set(models))


def list_models(
    profile: dict[str, Any], key: str, timeout_seconds: float
) -> tuple[int, list[str]]:
    model_list = profile["model_list"]
    headers = {
        "Accept": "application/json",
        "User-Agent": "S45-model-provider/1.0",
    }
    if model_list["auth"] == "x-goog-api-key":
        headers["x-goog-api-key"] = key
    else:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(
        model_list["url"], headers=headers, method="GET"
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ContractError("Provider model list returned a non-object JSON root")
        return response.status, parse_model_payload(payload, model_list["parser"])


def strip_single_json_fence(content: str) -> str:
    value = content.strip()
    lines = value.splitlines()
    if len(lines) >= 3 and lines[0].strip().lower() in ("~~~json", "~~~"):
        if lines[-1].strip() == "~~~":
            return "\n".join(lines[1:-1]).strip()
    ticks = chr(96) * 3
    if len(lines) >= 3 and lines[0].strip().lower() in (ticks + "json", ticks):
        if lines[-1].strip() == ticks:
            return "\n".join(lines[1:-1]).strip()
    return value


def has_reasoning_leak(content: str) -> bool:
    lowered = content.lower()
    return "<think>" in lowered or "</think>" in lowered


def normalize_reasoning_content(
    content: str, policy: str, expect_json: bool
) -> tuple[str, dict[str, Any]]:
    """Recover final content from provider reasoning wrappers deterministically."""
    value = content.strip()
    stats: dict[str, Any] = {
        "policy": policy,
        "marker_used": False,
        "think_detected": has_reasoning_leak(value),
        "think_blocks_stripped": 0,
        "stripped_reasoning_length": 0,
        "json_suffix_recovered": False,
        "unclosed_think_tags_cleaned": 0,
        "orphan_close_tags_cleaned": 0,
        "compatibility_warnings": [],
    }

    marker_count = value.count(FINAL_MARKER)
    stats["marker_count"] = marker_count
    if marker_count:
        tail = value.rsplit(FINAL_MARKER, 1)[1].strip()
        if tail:
            value = tail
        else:
            value = value.replace(FINAL_MARKER, "").strip()
            stats["compatibility_warnings"].append(
                "TRAILING_FINAL_MARKER_RECOVERED"
            )
        stats["marker_used"] = True

    open_tag = "<think>"
    close_tag = "</think>"
    while True:
        lowered = value.lower()
        open_index = lowered.find(open_tag)
        if open_index < 0:
            break
        close_index = lowered.find(close_tag, open_index + len(open_tag))
        if close_index < 0:
            value = value[:open_index] + value[open_index + len(open_tag) :]
            stats["unclosed_think_tags_cleaned"] += 1
            stats["compatibility_warnings"].append("UNCLOSED_THINK_TAG_CLEANED")
            continue
        stats["think_blocks_stripped"] += 1
        stats["stripped_reasoning_length"] += (
            close_index - open_index - len(open_tag)
        )
        value = (
            value[:open_index]
            + value[close_index + len(close_tag) :]
        )

    while close_tag in value.lower():
        lowered = value.lower()
        close_index = lowered.find(close_tag)
        value = value[:close_index] + value[close_index + len(close_tag) :]
        stats["orphan_close_tags_cleaned"] += 1
        stats["compatibility_warnings"].append("ORPHAN_CLOSE_TAG_CLEANED")

    value = value.strip()
    if expect_json:
        decoder = json.JSONDecoder()
        recovered: str | None = None
        starters = set('{["-0123456789tfn')
        for index, char in enumerate(value):
            if char not in starters:
                continue
            try:
                parsed, end_index = decoder.raw_decode(value, index)
            except json.JSONDecodeError:
                continue
            if value[end_index:].strip():
                continue
            recovered = json.dumps(parsed, ensure_ascii=False, indent=2)
        if recovered is not None and recovered.strip() != value:
            value = recovered
            stats["json_suffix_recovered"] = True
            stats["compatibility_warnings"].append("JSON_SUFFIX_RECOVERED")

    if not value:
        value = content.replace(FINAL_MARKER, "").strip()
        stats["compatibility_warnings"].append("EMPTY_AFTER_CLEANUP_RAW_FALLBACK")
    return value, stats


def message_reasoning_stats(
    message_payload: dict[str, Any], reasoning_fields: list[str]
) -> tuple[bool, int]:
    present = False
    total_length = 0
    for field in reasoning_fields:
        value = message_payload.get(field)
        if value in (None, "", [], {}):
            continue
        present = True
        if isinstance(value, str):
            total_length += len(value)
        else:
            total_length += len(json.dumps(value, ensure_ascii=False))
    return present, total_length


def read_argument_text(
    inline: str | None, file_path: str | None, label: str
) -> str:
    if inline and file_path:
        raise ContractError(f"Use only one of --{label} or --{label}-file")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8-sig")
    if inline is not None:
        return inline
    if label == "prompt":
        raise ContractError("A prompt is required")
    return ""


def resolve_model(
    profile: dict[str, Any], explicit_model: str | None, model_role: str
) -> str:
    if explicit_model:
        return explicit_model
    roles = profile.get("model_roles", {})
    model = roles.get(model_role) if isinstance(roles, dict) else None
    if not model:
        available = ", ".join(sorted(roles)) if isinstance(roles, dict) else ""
        raise ContractError(
            f"Unknown model role '{model_role}'. Available: {available}"
        )
    return str(model)


def validate_json_value(
    content: str, schema_path: str | None
) -> tuple[Any, list[str]]:
    value = json.loads(strip_single_json_fence(content))
    errors: list[str] = []
    if schema_path:
        schema = load_json(Path(schema_path))
        try:
            from jsonschema import Draft202012Validator, FormatChecker

            validator = Draft202012Validator(
                schema, format_checker=FormatChecker()
            )
            for error in sorted(
                validator.iter_errors(value), key=lambda item: list(item.path)
            ):
                location = ".".join(str(part) for part in error.path) or "$"
                errors.append(f"{location}:{error.message}")
        except ImportError:
            errors.append("jsonschema dependency is required for --schema")
    return value, errors


def openai_call(
    profile: dict[str, Any],
    key: str,
    model: str,
    prompt: str,
    system: str,
    timeout_seconds: float,
    max_output_tokens: int,
    temperature: float,
    transport_retries: int,
    retry_statuses: set[int],
) -> tuple[Any, int]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ContractError("Python package 'openai' is required") from exc

    client = OpenAI(
        api_key=key,
        base_url=profile["base_url"],
        timeout=timeout_seconds,
        max_retries=0,
    )
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    request_adapter = profile["request_adapter"]
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    kwargs[request_adapter["max_tokens_field"]] = max_output_tokens
    extra_body = request_adapter.get("extra_body") or {}
    if extra_body:
        kwargs["extra_body"] = extra_body

    attempt = 0
    while True:
        try:
            response = client.chat.completions.create(**kwargs)
            return response, attempt
        except Exception as exc:
            status = error_status(exc)
            if attempt < transport_retries and status in retry_statuses:
                attempt += 1
                time.sleep(min(2**attempt, 4))
                continue
            raise


def cmd_validate(args: argparse.Namespace) -> int:
    _, _, receipt = validate_contract()
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if args.receipt_out:
        write_json(Path(args.receipt_out), receipt)
    return 0 if receipt["status"] == "PASS" else 2


def cmd_models(args: argparse.Namespace) -> int:
    contract, credentials = require_valid_contract()
    profile = provider_profile(contract, args.provider)
    env_name, key = provider_key(profile, credentials)
    timeout_seconds = float(
        args.timeout or contract["global_defaults"]["timeout_seconds"]
    )
    defaults = contract["global_defaults"]
    transport_retries = (
        int(args.transport_retries)
        if args.transport_retries is not None
        else int(defaults["transport_retries"])
    )
    if transport_retries < 0 or transport_retries > int(
        defaults["transport_retries_max"]
    ):
        raise ContractError("transport retries must be between 0 and 1")
    started = time.perf_counter()
    receipt: dict[str, Any] = {
        "contract": contract["contract_version"],
        "action": "models",
        "provider": args.provider,
        "credential_env": env_name,
        "credential_present": True,
        "credential_length": len(key),
        "transport_retries_requested": transport_retries,
        "started_at": utc_now(),
    }
    attempt = 0
    try:
        while True:
            try:
                status, models = list_models(profile, key, timeout_seconds)
                break
            except urllib.error.HTTPError as exc:
                if (
                    attempt < transport_retries
                    and exc.code in set(defaults["retry_http_statuses"])
                ):
                    attempt += 1
                    time.sleep(min(2**attempt, 4))
                    continue
                raise
        if args.contains:
            needle = args.contains.lower()
            models = [model for model in models if needle in model.lower()]
        visible = models[: args.limit]
        receipt.update(
            {
                "status": "PASS",
                "http_status": status,
                "model_count": len(models),
                "models_returned": len(visible),
                "models": visible,
                "transport_retries_used": attempt,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        if args.receipt_out:
            write_json(Path(args.receipt_out), receipt)
        return 0
    except urllib.error.HTTPError as exc:
        receipt.update(
            {
                "status": "FAIL",
                "http_status": exc.code,
                "error_class": classify_http_status(exc.code),
                "transport_retries_used": attempt,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    except Exception as exc:
        receipt.update(
            {
                "status": "FAIL",
                "http_status": None,
                "error_class": type(exc).__name__,
                "transport_retries_used": attempt,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if args.receipt_out:
        write_json(Path(args.receipt_out), receipt)
    return 3


def cmd_call(args: argparse.Namespace) -> int:
    contract, credentials = require_valid_contract()
    profile = provider_profile(contract, args.provider)
    env_name, key = provider_key(profile, credentials)
    model = resolve_model(profile, args.model, args.model_role)
    prompt = read_argument_text(args.prompt, args.prompt_file, "prompt")
    system = read_argument_text(args.system, args.system_file, "system")
    if args.expect_json:
        system = (
            system.rstrip()
            + "\nThe final payload after the transport marker must be exactly one "
            "JSON value. Do not use Markdown fences or commentary in that payload."
        ).strip()
    system = (
        system.rstrip()
        + f"\nPut the final answer after the marker {FINAL_MARKER}. "
        "The marker must appear exactly once and must not appear inside reasoning."
    ).strip()

    defaults = contract["global_defaults"]
    timeout_seconds = float(args.timeout or defaults["timeout_seconds"])
    max_output_tokens = int(
        args.max_output_tokens or defaults["max_output_tokens"]
    )
    temperature = (
        float(args.temperature)
        if args.temperature is not None
        else float(defaults["temperature"])
    )
    transport_retries = (
        int(args.transport_retries)
        if args.transport_retries is not None
        else int(defaults["transport_retries"])
    )
    if transport_retries < 0 or transport_retries > int(
        defaults["transport_retries_max"]
    ):
        raise ContractError("transport retries must be between 0 and 1")
    response_repair_retries = (
        int(args.response_repair_retries)
        if args.response_repair_retries is not None
        else int(defaults["response_repair_retries"])
    )
    if response_repair_retries < 0 or response_repair_retries > int(
        defaults["response_repair_retries_max"]
    ):
        raise ContractError("response repair retries must be between 0 and 1")

    started = time.perf_counter()
    receipt: dict[str, Any] = {
        "contract": contract["contract_version"],
        "action": "call",
        "status": "RUNNING",
        "terminal": False,
        "completion_state": "IN_PROGRESS",
        "provider": args.provider,
        "model": model,
        "model_role": args.model_role,
        "base_url_host": urlparse(profile["base_url"]).netloc,
        "credential_env": env_name,
        "credential_present": True,
        "credential_length": len(key),
        "timeout_seconds": timeout_seconds,
        "sdk_max_retries": 0,
        "transport_retries_requested": transport_retries,
        "response_repair_retries_requested": response_repair_retries,
        "max_output_tokens": max_output_tokens,
        "expect_json": bool(args.expect_json),
        "schema_path": str(Path(args.schema).resolve()) if args.schema else None,
        "started_at": utc_now(),
        "attempts": [],
    }
    response_retries_used = 0
    total_transport_retries_used = 0
    while True:
        attempt_number = response_retries_used + 1
        attempt_system = system
        if response_retries_used:
            attempt_system = (
                system.rstrip()
                + "\nThis is a bounded response-envelope repair attempt. Re-run the "
                "original task and emit only the usable final payload. Do not emit "
                "reasoning, analysis, Markdown fences, or extra commentary."
            )
        try:
            response, retries_used = openai_call(
                profile=profile,
                key=key,
                model=model,
                prompt=prompt,
                system=attempt_system,
                timeout_seconds=timeout_seconds,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                transport_retries=transport_retries,
                retry_statuses=set(defaults["retry_http_statuses"]),
            )
        except Exception as exc:
            status = error_status(exc)
            error_class = classify_http_status(status)
            receipt["attempts"].append(
                {
                    "attempt": attempt_number,
                    "status": "ERROR",
                    "http_status": status,
                    "error_class": error_class,
                    "exception_type": type(exc).__name__,
                }
            )
            receipt.update(
                {
                    "status": (
                        "BLOCKED"
                        if error_class == "AUTH_OR_PERMISSION"
                        else "RETRY_REQUIRED"
                    ),
                    "terminal": False,
                    "completion_state": "CONTINUE_REQUIRED",
                    "http_status": status,
                    "error_class": error_class,
                    "exception_type": type(exc).__name__,
                    "response_repair_retries_used": response_retries_used,
                    "duration_ms": round(
                        (time.perf_counter() - started) * 1000, 2
                    ),
                }
            )
            if args.receipt_out:
                write_json(Path(args.receipt_out), receipt)
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
            return 3

        total_transport_retries_used += retries_used
        choice = response.choices[0]
        message = choice.message
        content = message.content or ""
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        message_payload = message.model_dump()
        reasoning_present, reasoning_length = message_reasoning_stats(
            message_payload, profile["response_adapter"]["reasoning_fields"]
        )
        think_policy = profile["response_adapter"]["think_content_policy"]
        normalized_content, reasoning_compatibility = normalize_reasoning_content(
            content, think_policy, bool(args.expect_json)
        )
        finish_reason = getattr(choice, "finish_reason", None)
        usage = response.usage.model_dump() if response.usage else None
        attempt_record: dict[str, Any] = {
            "attempt": attempt_number,
            "status": "RECEIVED",
            "http_status": 200,
            "finish_reason": finish_reason,
            "transport_retries_used": retries_used,
            "reasoning_present": reasoning_present,
            "reasoning_length": reasoning_length,
            "reasoning_compatibility": reasoning_compatibility,
            "content_sha256": sha256_text(content),
            "content_length": len(content),
        }
        error_class: str | None = None
        exit_code = 5
        json_value: Any = None
        schema_errors: list[str] = []
        if not normalized_content.strip():
            error_class = "EMPTY_CONTENT"
        elif args.expect_json:
            try:
                json_value, schema_errors = validate_json_value(
                    normalized_content, args.schema
                )
            except json.JSONDecodeError:
                error_class = (
                    "OUTPUT_TRUNCATED"
                    if finish_reason == "length"
                    else "INVALID_JSON"
                )
            else:
                if schema_errors:
                    error_class = "SCHEMA_VALIDATION_FAILED"
                    exit_code = 6

        repairable = error_class in {"EMPTY_CONTENT", "INVALID_JSON"}
        if repairable and response_retries_used < response_repair_retries:
            attempt_record["status"] = "REPAIR_RETRY"
            attempt_record["error_class"] = error_class
            receipt["attempts"].append(attempt_record)
            response_retries_used += 1
            continue

        receipt["attempts"].append(attempt_record)
        receipt.update(
            {
                "http_status": 200,
                "response_id": getattr(response, "id", None),
                "finish_reason": finish_reason,
                "transport_retries_used": total_transport_retries_used,
                "response_repair_retries_used": response_retries_used,
                "reasoning_present": reasoning_present,
                "reasoning_length": reasoning_length,
                "reasoning_compatibility": reasoning_compatibility,
                "content_sha256": sha256_text(content),
                "content_length": len(content),
                "usage": usage,
            }
        )
        if error_class:
            receipt.update(
                {
                    "status": "RETRY_REQUIRED",
                    "terminal": False,
                    "completion_state": "CONTINUE_REQUIRED",
                    "error_class": error_class,
                    "json_valid": False if error_class != "SCHEMA_VALIDATION_FAILED" else True,
                    "schema_valid": (
                        False if args.schema or error_class == "SCHEMA_VALIDATION_FAILED" else None
                    ),
                    "schema_errors": schema_errors[:20] if schema_errors else [],
                    "duration_ms": round(
                        (time.perf_counter() - started) * 1000, 2
                    ),
                }
            )
            if args.receipt_out:
                write_json(Path(args.receipt_out), receipt)
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
            return exit_code
        if args.expect_json:
            normalized_content = json.dumps(
                json_value, ensure_ascii=False, indent=2
            )
            receipt["json_valid"] = True
            receipt["schema_valid"] = True if args.schema else None
        break

    if args.response_out:
        atomic_write(Path(args.response_out), normalized_content + "\n")
    else:
        print(normalized_content)

    receipt.update(
        {
            "status": "PASS",
            "terminal": True,
            "completion_state": "SUCCEEDED",
            "normalized_content_sha256": sha256_text(normalized_content),
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "completed_at": utc_now(),
        }
    )
    if args.receipt_out:
        write_json(Path(args.receipt_out), receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


def cmd_run_tool(args: argparse.Namespace) -> int:
    contract, credentials = require_valid_contract()
    child_env = os.environ.copy()
    injected: list[str] = []
    if args.all_credentials:
        names = contract["required_credentials"]
        tool_env: dict[str, str] = {}
    else:
        profile = provider_profile(contract, args.provider)
        names = [profile["api_key_env"]]
        tool_env = profile.get("tool_env") or {}
    for name in names:
        value = credentials.get(name, "")
        if not value:
            raise ContractError(f"Credential is empty: {name}")
        child_env[name] = value
        injected.append(name)
    for name, value in tool_env.items():
        child_env[str(name)] = str(value)

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ContractError("run-tool requires a command after --")

    started = time.perf_counter()
    completed = subprocess.run(command, env=child_env, check=False)
    executable_name = Path(command[0]).stem.lower()
    postcondition: dict[str, Any] | None = None
    postcondition_ok = True
    if executable_name == "graphify" and len(command) > 1 and command[1] == "extract":
        out_value: str | None = None
        for index, value in enumerate(command):
            if value == "--out" and index + 1 < len(command):
                out_value = command[index + 1]
                break
            if value.startswith("--out="):
                out_value = value.split("=", 1)[1]
                break
        target_value = command[2] if len(command) > 2 and not command[2].startswith("-") else "."
        graph_root = Path(out_value or target_value).resolve()
        graph_path = graph_root / "graphify-out" / "graph.json"
        postcondition = {
            "type": "graphify_semantic_extract",
            "graph_path": str(graph_path),
            "graph_exists": graph_path.is_file(),
            "graph_sha256": sha256_file(graph_path) if graph_path.is_file() else None,
            "nodes": 0,
            "edges": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "model_return_verified": False,
        }
        if graph_path.is_file():
            try:
                graph_payload = load_json(graph_path)
                nodes = graph_payload.get("nodes") or []
                edges = graph_payload.get("edges") or []
                postcondition.update(
                    {
                        "nodes": len(nodes) if isinstance(nodes, list) else 0,
                        "edges": len(edges) if isinstance(edges, list) else 0,
                        "input_tokens": int(graph_payload.get("input_tokens") or 0),
                        "output_tokens": int(graph_payload.get("output_tokens") or 0),
                    }
                )
                if postcondition["output_tokens"] <= 0:
                    analysis_path = graph_path.parent / "analysis.json"
                    marker_path = graph_path.parent / ".graphify_semantic_marker"
                    if analysis_path.is_file():
                        analysis_payload = load_json(analysis_path)
                        tokens = analysis_payload.get("tokens") or {}
                        if isinstance(tokens, dict):
                            postcondition["input_tokens"] = int(
                                tokens.get("input") or postcondition["input_tokens"]
                            )
                            postcondition["output_tokens"] = int(
                                tokens.get("output") or 0
                            )
                    if postcondition["output_tokens"] <= 0 and marker_path.is_file():
                        marker_payload = load_json(marker_path)
                        postcondition["output_tokens"] = int(
                            marker_payload.get("output_tokens") or 0
                        )
            except (OSError, ValueError, json.JSONDecodeError, ContractError) as exc:
                postcondition["verification_error"] = type(exc).__name__
        postcondition["model_return_verified"] = bool(
            postcondition["nodes"] > 0 and postcondition["output_tokens"] > 0
        )
        postcondition_ok = bool(postcondition["model_return_verified"])

    tool_ok = completed.returncode == 0 and postcondition_ok
    receipt = {
        "contract": contract["contract_version"],
        "action": "run-tool",
        "status": "PASS" if tool_ok else "RETRY_REQUIRED",
        "terminal": bool(tool_ok),
        "completion_state": "SUCCEEDED" if tool_ok else "CONTINUE_REQUIRED",
        "provider": None if args.all_credentials else args.provider,
        "credentials_injected": injected,
        "tool_env_injected": sorted(tool_env),
        "executable": command[0],
        "argument_count": max(len(command) - 1, 0),
        "command_sha256": sha256_text(
            json.dumps(command, ensure_ascii=False)
        ),
        "exit_code": completed.returncode,
        "postcondition": postcondition,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "completed_at": utc_now(),
    }
    if args.receipt_out:
        write_json(Path(args.receipt_out), receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if completed.returncode != 0:
        return completed.returncode
    return 0 if postcondition_ok else 7


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="S45 multi-provider deterministic model adapter"
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="validate schema, profiles, and exact seven credentials"
    )
    validate_parser.add_argument("--receipt-out")
    validate_parser.set_defaults(handler=cmd_validate)

    models_parser = subparsers.add_parser(
        "models", help="list models visible to one provider credential"
    )
    models_parser.add_argument("--provider", required=True)
    models_parser.add_argument("--contains")
    models_parser.add_argument("--limit", type=int, default=100)
    models_parser.add_argument("--timeout", type=float)
    models_parser.add_argument("--transport-retries", type=int)
    models_parser.add_argument("--receipt-out")
    models_parser.set_defaults(handler=cmd_models)

    call_parser = subparsers.add_parser(
        "call", help="perform one explicit provider/model call"
    )
    call_parser.add_argument("--provider", required=True)
    call_parser.add_argument("--model-role", default="default")
    call_parser.add_argument("--model")
    call_parser.add_argument("--prompt")
    call_parser.add_argument("--prompt-file")
    call_parser.add_argument("--system")
    call_parser.add_argument("--system-file")
    call_parser.add_argument("--expect-json", action="store_true")
    call_parser.add_argument("--schema")
    call_parser.add_argument("--timeout", type=float)
    call_parser.add_argument("--max-output-tokens", type=int)
    call_parser.add_argument("--temperature", type=float)
    call_parser.add_argument("--transport-retries", type=int)
    call_parser.add_argument("--response-repair-retries", type=int)
    call_parser.add_argument("--response-out")
    call_parser.add_argument("--receipt-out")
    call_parser.set_defaults(handler=cmd_call)

    tool_parser = subparsers.add_parser(
        "run-tool", help="run a child tool with credentials loaded from the SSOT"
    )
    provider_group = tool_parser.add_mutually_exclusive_group(required=True)
    provider_group.add_argument("--provider")
    provider_group.add_argument("--all-credentials", action="store_true")
    tool_parser.add_argument("--receipt-out")
    tool_parser.add_argument("command", nargs=argparse.REMAINDER)
    tool_parser.set_defaults(handler=cmd_run_tool)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except ContractError as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_class": "CONTRACT_ERROR",
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
