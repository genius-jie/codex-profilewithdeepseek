import os
import json
from datetime import datetime, date

# S19 日报采集器：只做"证据搬运"，不做工作结论推断。
# 重点：过滤 IDE 缓存、历史备份、会话状态、pipeline 中间态，避免把噪声误当成当天工作事实。
EXCLUDE_DIRS = {
    '.git', '.trae', '__pycache__', 'node_modules', '.venv', 'venv', '.idea', '.vscode',
    'logs', 'tmp', 'temp', 'dist', 'build',
    '.gemini', '.gemini-backup', 'antigravity-backup', 'antigravity-ide', 'code_tracker',
    'pipeline_state', 'sessions', 'hook-state', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    '.next', 'coverage', '.cache'
}

EXCLUDE_PATH_PARTS = {
    '.gemini',
    'antigravity-backup',
    'antigravity-ide',
    'code_tracker',
    'pipeline_state',
    'sessions',
    'hook-state',
}

MAX_FILES_PER_ROOT = 3000

AUTO_TASK_PATH_PARTS = {
    'logs',
    'cron',
    'scheduled',
    'automation',
}


def path_parts(rel_path):
    return {part.lower() for part in rel_path.replace('\\', '/').split('/') if part and part != '.'}


def is_excluded_rel_path(rel_path):
    return bool(path_parts(rel_path) & EXCLUDE_PATH_PARTS)


def is_auto_task_path(rel_path):
    """判断路径是否为机器运行产物目录。"""
    return bool(path_parts(rel_path) & AUTO_TASK_PATH_PARTS)


def classify_project(file_path, root_dir):
    """
    返回物理工作区标签，不做业务项目归类。
    业务主线归并必须由 Agent 基于三入口用户输入流完成。
    """
    rel_path = os.path.relpath(file_path, root_dir).replace('\\', '/')
    if is_auto_task_path(rel_path):
        return None, True
    workspace_name = os.path.basename(root_dir.rstrip('\\/'))
    return workspace_name, False


def collect_changes(root_dir):
    if not os.path.exists(root_dir):
        return []

    today = date.today()
    changed_files = []

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        rel_root = os.path.relpath(root, root_dir)
        if rel_root != '.' and is_excluded_rel_path(rel_root):
            dirs[:] = []
            continue

        for file in files:
            file_path = os.path.join(root, file)
            try:
                rel_path = os.path.relpath(file_path, root_dir)
                if is_excluded_rel_path(rel_path):
                    continue

                stat = os.stat(file_path)
                mtime = datetime.fromtimestamp(stat.st_mtime).date()
                ctime = datetime.fromtimestamp(stat.st_ctime).date()

                if mtime == today or ctime == today:
                    project, is_auto = classify_project(file_path, root_dir)
                    
                    # 定时任务产物跳过
                    if is_auto:
                        continue
                    
                    if project is None:
                        project = os.path.basename(root_dir.rstrip('\\/'))
                    
                    changed_files.append({
                        "project": project,
                        "path": rel_path,
                        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        "type": "new" if ctime == today else "modified",
                        "evidence_kind": "file_mtime",
                        "note": "file timestamp only; must be corroborated before becoming a report item",
                        "classification_owner": "agent",
                        "classification_mode": "workspace_root_only",
                        "is_auto_task": is_auto
                    })
                    if len(changed_files) >= MAX_FILES_PER_ROOT:
                        changed_files.append({
                            "project": "SYSTEM",
                            "path": "<TRUNCATED>",
                            "mtime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "type": "truncated",
                            "evidence_kind": "collector_guardrail",
                            "note": f"too many changed files under this root; capped at {MAX_FILES_PER_ROOT}",
                            "classification_owner": "agent",
                            "classification_mode": "workspace_root_only",
                            "is_auto_task": False
                        })
                        return changed_files
            except Exception:
                pass

    return changed_files


def get_ssot_work_dirs():
    ssot_path = r'@@GENERAL_ROOT:win@@\control\registry\01-asset-register.md'
    work_dirs = set()
    if not os.path.exists(ssot_path):
        return []
    with open(ssot_path, 'r', encoding='utf-8') as f:
        content = f.read()

    paths = [
        part
        for index, part in enumerate(content.split('`'))
        if index % 2 == 1 and len(part) >= 3 and part[1] == ':' and part[2] == '\\'
    ]
    for p in paths:
        p = p.rstrip('\\/')
        if p.endswith('.agent') or p.endswith('.agents'):
            p = os.path.dirname(p)
        work_dirs.add(p)
    return sorted(work_dirs)


def aggregate_by_project(changes):
    """
    按业务大项目聚合变更
    """
    projects = {}
    for change in changes:
        proj = change.get('project', 'Unknown')
        if proj not in projects:
            projects[proj] = []
        projects[proj].append(change)
    return projects


if __name__ == "__main__":
    work_dirs = get_ssot_work_dirs()

    all_changes = []
    for wd in work_dirs:
        all_changes.extend(collect_changes(wd))
    
    # 按项目聚合
    project_summary = aggregate_by_project(all_changes)
    
    result = {
        "changes": all_changes,
        "project_summary": project_summary,
        "summary": {
            "total_files": len(all_changes),
            "projects": list(project_summary.keys()),
            "project_classification_owner": "agent",
            "project_classification_mode": "workspace_root_only",
            "auto_task_filtered": True,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
