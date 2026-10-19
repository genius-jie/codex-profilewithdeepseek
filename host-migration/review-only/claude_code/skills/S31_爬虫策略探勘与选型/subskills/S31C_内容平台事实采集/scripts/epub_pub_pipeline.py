#!/usr/bin/env python3
"""Run the reusable S31A -> S31C -> S31D EPUB.pub single-book pipeline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import epub_pub_book_collector as collector
import epub_pub_interactions as interactions
import epub_pub_verify as verifier


PIPELINE_SCHEMA = "s31c_epub_pub_pipeline_receipt.v1"
DEFAULT_CAPABILITY_ID = "ebook.epub_pub.single_book_fulltext.v1"
DEFAULT_BUSINESS_PROFILE = "ebook_single_book_fulltext"
DEFAULT_REGISTRY_PATH = SCRIPT_DIR.parents[2] / "references" / "crawler_capability_registry.yaml"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def localize_interaction_observation(source: Path, output_dir: Path) -> Path:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("interaction_observation_not_object")
    target = output_dir / "interaction_observation.v1.json"
    write_json(target, payload)
    return target


def annotate_json_object(path: Path, fields: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_artifact_not_object:{path}")
    payload.update(fields)
    write_json(path, payload)
    return payload


def capability_context(args: argparse.Namespace) -> dict[str, Any]:
    resolution_ref = getattr(args, "capability_resolution_ref", None)
    registry_ref = getattr(args, "capability_registry_ref", None) or str(DEFAULT_REGISTRY_PATH.resolve())
    return {
        "capability_id": getattr(args, "capability_id", None) or DEFAULT_CAPABILITY_ID,
        "capability_resolution_ref": str(Path(resolution_ref).resolve()) if resolution_ref else None,
        "crawler_capability_registry_ref": str(Path(registry_ref).resolve()),
        "business_profile": DEFAULT_BUSINESS_PROFILE,
        "source_adapter": "epub_pub",
    }


def localize_route_receipt(source: Path, output_dir: Path, context: dict[str, Any]) -> Path:
    target = output_dir / "s31a_route_receipt.v1.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("route_receipt_not_object")
    payload.update(context)
    payload.update({
        "platform_adapter": "epub_pub",
        "adapter_entrypoint": str(Path(__file__).resolve()),
        "required_nodes": ["S31A", "S31C", "S31D"],
        "adapter_contract": "checked_fact_pack_plus_w31_handoff",
    })
    write_json(target, payload)
    return target


def resolve_sibling_script(prefix: str, filename: str, env_var: str) -> Path:
    override = os.environ.get(env_var)
    if override:
        path = Path(override).expanduser().resolve()
        if path.is_file():
            return path
        raise FileNotFoundError(f"{env_var}_not_found:{path}")

    subskills_dir = SCRIPT_DIR.parent.parent
    for skill_dir in sorted(subskills_dir.glob(f"{prefix}_*")):
        candidate = skill_dir / "scripts" / filename
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"sibling_script_not_found:{prefix}:{filename}")


def run_command(label: str, argv: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "label": label,
        "argv": argv,
        "exit_code": completed.returncode,
        "status": "ok" if completed.returncode == 0 else "failed",
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def build_route_receipt(args: argparse.Namespace, output_dir: Path) -> tuple[Path, dict[str, Any]]:
    context = capability_context(args)
    if args.route_receipt:
        source = Path(args.route_receipt).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"route_receipt_not_found:{source}")
        path = localize_route_receipt(source, output_dir, context)
        return path, {
            "label": "s31a_route_probe",
            "status": "reused_and_localized",
            "source_path": str(source),
            "path": str(path),
        }

    route_script = resolve_sibling_script(
        "S31A",
        "route_probe_cli.py",
        "S31A_ROUTE_PROBE_SCRIPT",
    )
    route_path = output_dir / "s31a_route_receipt.v1.json"
    command = [
        sys.executable,
        str(route_script),
        "--url",
        args.url,
        "--platform",
        "epub_pub",
        "--collection-mode",
        "query_search_data_collection",
        "--source-id",
        "epub_pub_book",
        "--source-family",
        "ebook_site",
        "--source-role",
        "user_selected_primary_source",
        "--api-evidence",
        "epub_asset_manifest_http",
        "--timeout",
        str(args.route_timeout),
        "--json-output",
        str(route_path),
    ]
    receipt = run_command("s31a_route_probe", command)
    if receipt["exit_code"] != 0 or not route_path.is_file():
        raise RuntimeError(f"s31a_route_probe_failed:{receipt['stderr_tail'] or receipt['stdout_tail']}")
    localize_route_receipt(route_path, output_dir, context)
    receipt["path"] = str(route_path)
    return route_path, receipt


def collect_book(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    collector_args = argparse.Namespace(
        url=args.url,
        output_dir=str(output_dir),
        concurrency=args.concurrency,
        timeout=args.timeout,
        retries=args.retries,
        min_interval=args.min_interval,
        user_agent=args.user_agent,
    )
    return collector.Collector(collector_args).run()


def finalize_fact_pack(output_dir: Path) -> dict[str, Any]:
    validator = resolve_sibling_script(
        "S31D",
        "crawler_fact_pack.py",
        "S31D_CRAWLER_FACT_PACK_SCRIPT",
    )
    command = [
        sys.executable,
        str(validator),
        "--input",
        str(output_dir / "crawler_fact_pack.v1.json"),
        "--output",
        str(output_dir / "crawler_fact_pack.v1.checked.json"),
    ]
    return run_command("s31d_fact_pack_validation", command)


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = output_dir / "epub_pub_pipeline_receipt.v1.json"
    context = capability_context(args)
    receipt: dict[str, Any] = {
        "schema_version": PIPELINE_SCHEMA,
        "status": "running",
        "source_url": args.url,
        "output_dir": str(output_dir),
        **context,
        "started_at": collector.utc_now(),
        "stages": {},
        "output_refs": [],
    }

    try:
        if args.require_interactions and not args.interaction_observation:
            raise ValueError("interaction_observation_required")

        route_path, route_stage = build_route_receipt(args, output_dir)
        receipt["stages"]["route_probe"] = route_stage

        acceptance = collect_book(args, output_dir)
        receipt["stages"]["book_collection"] = {
            "status": acceptance.get("status"),
            "manifest_items": (acceptance.get("counts") or {}).get("manifest_items", 0),
            "chapters": (acceptance.get("counts") or {}).get("chapters_rows", 0),
            "paragraphs": (acceptance.get("counts") or {}).get("paragraph_rows", 0),
            "body_char_count": acceptance.get("body_char_count", 0),
        }
        if acceptance.get("status") != "ok":
            raise RuntimeError(f"book_collection_not_complete:{acceptance.get('failure_reason') or acceptance.get('status')}")

        if args.interaction_observation:
            observation_path = Path(args.interaction_observation).resolve()
            if not observation_path.is_file():
                raise FileNotFoundError(f"interaction_observation_not_found:{observation_path}")
            local_observation = localize_interaction_observation(observation_path, output_dir)
            interaction_summary = interactions.merge(output_dir, local_observation)
            receipt["stages"]["interaction_merge"] = interaction_summary
        else:
            receipt["stages"]["interaction_merge"] = {
                "status": "not_requested",
                "quality_flag": "comments_not_collected",
            }

        annotate_json_object(output_dir / "crawler_fact_pack.v1.json", context)
        fact_stage = finalize_fact_pack(output_dir)
        receipt["stages"]["fact_pack_validation"] = fact_stage
        if fact_stage["exit_code"] != 0:
            raise RuntimeError(f"s31d_fact_pack_validation_failed:{fact_stage['stderr_tail'] or fact_stage['stdout_tail']}")

        verification = verifier.verify(
            output_dir,
            require_interactions=bool(args.interaction_observation or args.require_interactions),
        )
        verification_path = output_dir / "verification_receipt.v1.json"
        write_json(verification_path, verification)
        verifier.write_handoff(output_dir, verification, str(route_path))
        annotate_json_object(output_dir / "w31_handoff.v1.json", context)
        receipt["stages"]["verification"] = {
            "status": verification.get("status"),
            "failure_count": len(verification.get("failures") or []),
            "path": str(verification_path),
        }
        if verification.get("status") != "passed":
            raise RuntimeError("verification_failed:" + ",".join(verification.get("failures") or []))

        receipt["status"] = "passed"
        receipt["output_refs"] = [
            str((output_dir / "normalized" / "book_full.txt").resolve()),
            str((output_dir / "book_metadata.json").resolve()),
            str((output_dir / "chapters.jsonl").resolve()),
            str((output_dir / "paragraphs.jsonl").resolve()),
            str((output_dir / "crawler_fact_pack.v1.checked.json").resolve()),
            str((output_dir / "w31_handoff.v1.json").resolve()),
            str(verification_path.resolve()),
        ]
    except Exception as exc:  # receipt keeps every failed stage observable
        receipt["status"] = "failed"
        receipt["failure_reason"] = f"{type(exc).__name__}:{exc}"
    finally:
        receipt["finished_at"] = collector.utc_now()
        write_json(receipt_path, receipt)
    return receipt


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect and verify one EPUB.pub book through the governed S31/W31 chain."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--route-receipt")
    parser.add_argument("--capability-id", default=DEFAULT_CAPABILITY_ID)
    parser.add_argument("--capability-resolution-ref")
    parser.add_argument("--capability-registry-ref", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--interaction-observation")
    parser.add_argument("--require-interactions", action="store_true")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--route-timeout", type=float, default=10.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--min-interval", type=float, default=0.15)
    parser.add_argument("--user-agent", default=collector.DEFAULT_USER_AGENT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    receipt = run_pipeline(parse_args(argv))
    print(json.dumps({
        "status": receipt["status"],
        "output_dir": receipt["output_dir"],
        "output_refs": receipt.get("output_refs", []),
        "failure_reason": receipt.get("failure_reason"),
    }, ensure_ascii=False, indent=2))
    return 0 if receipt["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
