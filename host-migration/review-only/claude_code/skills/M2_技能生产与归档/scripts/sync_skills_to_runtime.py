"""SSOT → 运行时层 Skill 同步脚本。

背景（2026-08-07 断链事故根治）：
  `.agent/skills/` 是 SSOT（治理层，doc_status=active-ssot），
  但 Claude Code 运行时实际加载的是 `.claude/skills/<skill>/`（带 .claude-plugin/plugin.json）。
  两者是两份独立副本，没有自动同步。只改 SSOT 不复制到运行时层，
  整改在运行时完全不可见，下次同类问题原样复发。

用法：
  # 同步单个 Skill
  python sync_skills_to_runtime.py --skill S20_飞书文档拉取

  # 同步全部 Skill
  python sync_skills_to_runtime.py --all

  # 只做差异报告，不实际复制
  python sync_skills_to_runtime.py --all --dry-run

规则：
  - 保留运行时层的 .claude-plugin/plugin.json 不动。
  - 复制 SKILL.md / scripts/ / resources/ 到运行时层。
  - 复制后校验关键内容关键词在运行时副本中存在。
  - 同步后输出回执 JSON（object_class / action / synced_files / verified）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SSOT_ROOT = Path(r'@@GENERAL_ROOT:win@@\assets\skills')
RUNTIME_ROOT = Path(r"@@CLAUDE_HOME:win@@\skills")

# 运行时层中需要保留、不被 SSOT 覆盖的文件/目录
PRESERVE = {".claude-plugin"}


def sync_one(skill_name: str, dry_run: bool = False) -> dict:
    """同步单个 Skill 从 SSOT 到运行时层。返回回执 dict。"""
    src = SSOT_ROOT / skill_name
    dst = RUNTIME_ROOT / skill_name

    if not src.exists():
        return {"skill": skill_name, "status": "SKIPPED", "reason": f"SSOT 不存在: {src}"}

    copied, preserved, removed_runtime_only = [], [], []

    # 1. 收集要复制的源项（顶层文件 + 子目录，排除 PRESERVE）
    src_items = [p for p in src.iterdir() if p.name not in PRESERVE]
    runtime_preserve = [p.name for p in (dst.iterdir() if dst.exists() else []) if p.name in PRESERVE]

    if dry_run:
        for item in src_items:
            copied.append(item.name)
        return {"skill": skill_name, "status": "DRY_RUN", "would_copy": copied, "would_preserve": runtime_preserve}

    # 2. 复制（dst 不存在则建目录）
    dst.mkdir(parents=True, exist_ok=True)
    for item in src_items:
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
        copied.append(item.name)

    # 3. 校验关键内容关键词在运行时副本中存在
    verified = {}
    skill_md_src = src / "SKILL.md"
    skill_md_dst = dst / "SKILL.md"
    if skill_md_src.exists() and skill_md_dst.exists():
        src_text = skill_md_src.read_text(encoding="utf-8")
        dst_text = skill_md_dst.read_text(encoding="utf-8")
        # 用 frontmatter 的 birth_ceremony_id 作为一致性锚点（如果都有）
        if "birth_ceremony_id:" in src_text and "birth_ceremony_id:" in dst_text:
            src_bc = [l for l in src_text.splitlines() if "birth_ceremony_id:" in l]
            dst_bc = [l for l in dst_text.splitlines() if "birth_ceremony_id:" in l]
            verified["birth_ceremony_match"] = src_bc == dst_bc
        verified["scripts_synced"] = all(
            (dst / "scripts" / f.name).exists()
            for f in (src / "scripts").iterdir() if f.is_file()
        ) if (src / "scripts").exists() else True
        verified["resources_synced"] = all(
            (dst / "resources" / f.name).exists()
            for f in (src / "resources").iterdir() if f.is_file()
        ) if (src / "resources").exists() else True

    return {
        "skill": skill_name,
        "status": "SYNCED",
        "copied": copied,
        "preserved": runtime_preserve,
        "removed_runtime_only": removed_runtime_only,
        "verified": verified,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="SSOT → 运行时层 Skill 同步")
    ap.add_argument("--skill", help="要同步的单个 Skill 名")
    ap.add_argument("--all", action="store_true", help="同步全部 Skill")
    ap.add_argument("--dry-run", action="store_true", help="只报告差异，不复制")
    args = ap.parse_args()

    if args.all:
        # 排除 .archived 等隐藏目录，防止已归档 Skill（如 M10）被复制回运行时层
        skills = sorted(p.name for p in SSOT_ROOT.iterdir() if p.is_dir() and not p.name.startswith("."))
    elif args.skill:
        skills = [args.skill]
    else:
        ap.error("必须指定 --skill 或 --all")
        return 1

    receipts = []
    for skill in skills:
        receipt = sync_one(skill, dry_run=args.dry_run)
        receipts.append(receipt)
        status = receipt["status"]
        print(f"[{status}] {skill}")
        if status == "SYNCED":
            print(f"  copied: {receipt['copied']}")
            print(f"  preserved: {receipt['preserved']}")
            print(f"  verified: {receipt['verified']}")
        elif status == "DRY_RUN":
            print(f"  would_copy: {receipt['would_copy']}")
            print(f"  would_preserve: {receipt['would_preserve']}")

    print(f"\n=== 同步回执 ===")
    print(json.dumps(receipts, ensure_ascii=False, indent=2))
    return 0 if all(r["status"] != "ERROR" for r in receipts) else 1


if __name__ == "__main__":
    sys.exit(main())
