"""
CodeGraph Advisory Hook - 代码探索情境感知提醒

触发条件：agent 在 openclaw-mono 项目中做代码探索（grep/find/rg/连续 Read .ts/.js 文件）
动作：注入 advisory 提醒 agent 考虑使用 codegraph_explore
性质：非阻断，仅 advisory
"""
import sys
import json

from claude_context_common import resolve_effective_cwd, within_openclaw

def main():
    try:
        stdin_data = sys.stdin.read()
        request = json.loads(stdin_data)

        tool_name = request.get('tool_name', '')
        tool_input = request.get('tool_input', {})

        # Scope comes from the runner-verified caller/event cwd.  The child is
        # intentionally started in the hooks directory, so the child's local
        # working directory is not a valid project signal.
        scope = resolve_effective_cwd(request)
        if not scope["valid"] or not within_openclaw(request):
            sys.exit(0)  # 不在目标项目，静默退出

        # 判断是否是代码探索操作
        is_code_exploration = False

        # Bash: grep/find/rg/ast-grep 等代码搜索命令
        if tool_name == 'Bash':
            command = tool_input.get('command', '')
            code_search_patterns = ['grep ', 'find ', 'rg ', 'ast-grep', 'codegraph explore']
            if any(p in command for p in code_search_patterns):
                # 排除 git 命令和包管理命令
                if not command.startswith('git ') and 'npm ' not in command and 'pip ' not in command:
                    is_code_exploration = True

        # Read: 读取 .ts/.js/.py 等代码文件
        elif tool_name == 'Read':
            file_path = tool_input.get('file_path', '')
            code_extensions = ['.ts', '.tsx', '.js', '.jsx', '.py', '.go', '.rs']
            if any(file_path.endswith(ext) for ext in code_extensions):
                # 排除配置文件、node_modules、dist 等
                if '/node_modules/' not in file_path and '/dist/' not in file_path:
                    is_code_exploration = True

        if is_code_exploration:
            # 注入 advisory
            advisory = {
                "decision": "advise",
                "message": (
                    "CodeGraph Advisory: 你正在探索 openclaw-mono 的代码结构。"
                    "如果任务是理解函数调用链、查找符号定义、分析修改影响范围，"
                    "优先使用 `codegraph_explore` MCP 工具（一次查询返回完整调用图 + blast radius），"
                    "比 grep/Read 多轮翻文件更高效。"
                    "仅当需要读取文件具体内容（而非理解代码关系）时，才用 Read。"
                ),
                "suppress_output": True  # 不显示给用户，仅影响 agent 决策
            }
            print(json.dumps(advisory))

        sys.exit(0)

    except Exception as e:
        # 异常时静默退出，不阻断 agent
        sys.exit(0)

if __name__ == '__main__':
    main()
