from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Mapping
from functools import partial
from typing import Any


_ENDPOINTS_ENV = "AUTOMATION_CORE_MONITOR_ENDPOINTS"
_ALLOWED_CONFIG_KEYS = {"db_path", "thread_id", "signal"}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _pending(observation: Mapping[str, Any]) -> dict[str, str]:
    interrupts = observation.get("interrupts")
    if not isinstance(interrupts, list) or len(interrupts) != 1:
        return {}
    packet = interrupts[0]
    if not isinstance(packet, Mapping):
        return {}
    return {
        key: text
        for key in ("stage", "kind", "phase", "task_id")
        if (text := _text(packet.get(key)))
    }


def _normalized_signal(pending: Mapping[str, str], explicit: str) -> str:
    if explicit:
        return explicit
    kind = pending.get("kind", "")
    if kind == "human":
        return "human-input-required"
    if kind == "clarification":
        return "clarification-required"
    return ""


def inspect_projection(
    *,
    db_path: str,
    thread_id: str,
    signal: str = "",
) -> dict[str, object]:
    """Return the bounded V4 projection from Core's public read-only CLI."""
    completed = subprocess.run(
        [
            "automation-core",
            "inspect",
            "--db",
            db_path,
            "--thread-id",
            thread_id,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"automation-core inspect failed with exit code {completed.returncode}"
        )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, Mapping):
        raise TypeError("automation-core inspect must return a JSON object")
    observation = payload.get("observation")
    if not isinstance(observation, Mapping):
        raise TypeError("automation-core inspect payload is missing observation")
    pending = _pending(observation)
    return {
        "checkpoint_id": _text(observation.get("checkpoint_id")),
        "status": _text(payload.get("status")) or "UNKNOWN",
        "pending": pending,
        "signal": _normalized_signal(pending, _text(signal)),
    }


def endpoint_mapping() -> Mapping[str, Callable[[], Mapping[str, object]]]:
    """Build ephemeral logical endpoints supplied by the trusted-host process."""
    raw = os.environ.get(_ENDPOINTS_ENV, "")
    value = json.loads(raw)
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{_ENDPOINTS_ENV} must be a non-empty JSON object")
    endpoints: dict[str, Callable[[], Mapping[str, object]]] = {}
    for name, config in value.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("endpoint name must be a non-empty string")
        if not isinstance(config, Mapping):
            raise ValueError("endpoint config must be a JSON object")
        if set(config) - _ALLOWED_CONFIG_KEYS:
            raise ValueError("endpoint config contains unsupported fields")
        db_path = _text(config.get("db_path"))
        thread_id = _text(config.get("thread_id"))
        signal = _text(config.get("signal"))
        if not db_path or not thread_id:
            raise ValueError("endpoint config requires db_path and thread_id")
        endpoints[name.strip()] = partial(
            inspect_projection,
            db_path=db_path,
            thread_id=thread_id,
            signal=signal,
        )
    return endpoints

