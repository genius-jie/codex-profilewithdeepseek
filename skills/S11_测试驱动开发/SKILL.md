---
name: S11 测试驱动开发
type: generic
domain: validator
tier: L3
doc_status: active-ssot
status: ACTIVE
version: 1
method:
  id: S11
  version: 1
  dimensions: [verification]
  applies_when: {fact: behavior_change, op: eq, value: true}
  requires: [{kind: artifact, id: behavior-spec}]
  stages:
    implement: {consumes: [behavior-spec], produces: [observed-red, minimal-green, regression-protection]}
    verify: {consumes: [regression-protection], produces: [fresh-test-results]}
  acceptance:
    required_evidence: [{kind: evidence, id: observed-red}, {kind: evidence, id: fresh-test-results}]
  host:
    requires: [{kind: capability, id: execute-verification}]
    handoff: [Return commands and missing capability to the caller; do not grant tools.]
  degradation:
    retain: [Behavior specification and executable test design]
    withdraw: [Executed RED or GREEN until commands actually run]
birth_ceremony_id: bc-s11-cfdaa836
birth_ceremony_date: '2026-05-02'
related:
- C:\Users\Administrator\.agent\control\registry\02-skill-catalog.md
description: 用户要求写测试、做TDD、写单元测试、集成测试时使用。

extends:
- C:\Users\Administrator\.agent\assets\rules\injection\skill-aop-prelude.md
- C:\Users\Administrator\.agent\assets\rules\error_handling.md
---
> **【S11 专属天条】**：敲击测试前必须强行压载 `rules/execution.md`。核心天条：**未见测试报错（RED），不许写生产代码；一切新增业务必须包裹在单元测试用例之中！**
> **【S-Tier 纪律加载说明】**：完整的 S 兵团执行纪律（210 行）由 `skill-aop-prelude.md` 的 AOP-3 条件路由触发。
> - **Standalone 模式**（用户直接调用，无 P3 派工单/session_dir）：AOP-3 不触发，仅执行本 Skill 内置的 RED-GREEN-REFACTOR 纪律。
> - **P3/P4 正式派工模式**（有派工单/session_dir）：AOP-3 触发，强制加载完整 S-Tier 协议。

# S11_单元测试驱动 (TDD Iron Forge)

<context>

## 1. 核心目标与防线边界
**专属负责**：写测试用例、执行 RED-GREEN-REFACTOR 循环、生成高并发/极端边界注入脚本。
**绝对不负责**：主导系统级的大规模联调（属于 S7 或 S8）、无头脑的业务乱拼凑。

### 组合工程方法（General Agent OS 通用）

本节是 `C:\Users\Administrator\.agent\assets\rules\agent-constitution.md` §2.1 的 TDD 场景化落地；即使单独加载本 Skill，以下条款也直接生效。

本 Skill 将General Agent OS 共同底座“目标、根因、职责边界、物理证据”翻译成 TDD 动作。各方法按当前问题条件选择和组合；这不是 Automation Core 专属，也不是固定的 S11 → S12 → S13 → S14 串行流水线。

- **输入**：明确的目标行为与验收边界；问题属于新行为，或已有根因已经指向需要永久行为保护；以及可以真实执行的测试入口。
- **本 Skill 输出**：能够对目标行为形成可证伪判断的 RED、只满足该行为的最小 GREEN、重构后仍通过的回归保护和对应物理命令结果。
- **条件交接**：若 RED 暴露的是尚未解释的环境、构建或既有回归，不猜测修复，携带失败命令、错误事实与健康对照交给 S12；已有候选变更是否调用 S13、准备完成时是否调用 S14，由任务风险和调用方验收契约决定。

</context>

<rules>

## 2. 🧠 红绿灯重压状态机 (Harness State Machine)
> **操作死劫卡点**：如果大模型企图“先写完了生产代码，再回头补写一个必过的测试”，当场物理熔断并没收执行权！这是对 TDD 灵魂的背叛。

### [STATE: BEHAVIOR_VERIFICATION_SPEC] (零相：行为准则提取)
- 明确这个被测接口/函数到底要干啥（What it should do）。
- **强行挂载图纸**：构思用例前，必须阅读独占装备库 `C:\Users\Administrator\.agent\assets\skills\S11_测试驱动开发\references\test-data-protocol.md`，使用 [5+X 分析法] 及 [笛卡尔积剧本] 构建防呆矩阵。
- **禁忌**：测试名严禁起诸如 `test_works` 这种垃圾名字，必须写明触发条件与预期结果。

### [STATE: RED_TEST_IMPLEMENTATION] (一相：写死局测试)
- 写入业务前，先只向 `tests/` 目录压入一段必败的测试代码。
- **物理硬卡点 (Watch It Fail)**：必须使用脚本引擎（如 Vitest / Pytest）跑一遍这个测试，向控制台展示出大红色的【FAIL】报错！证明测试是真的在拦截功能。

### [STATE: GREEN_CODE_INJECTION] (二相：写最小反制代码)
- 回到生产代码区，写下**能满足这个测试通过的、行数最少的代码**。绝不多写一行所谓的“为了未来拓展”的臃肿废话！
- 跑测试，向控制台展示大绿色的【PASS】！

### [STATE: REFACTOR_WITH_ARMOR] (三相：穿甲重构)
- 在确认绿灯的防弹衣保护下，把刚才写得烂的代码进行结构体提取与优化（DRY）。重构完后，绿灯必须依旧亮着。

</rules>

<template>

## 3. 📤 标准通信契约 (Harness Execution Contract)

正式调用方要求 `s-tier-execution-receipt.v3` 时，只有在调用方按契约实际触发并挂载独立 S13/S14 结果后，才能输出下面的成功回执。Standalone 或条件未触发场景沿用调用方自己的交接格式，不得把缺少独立裁决的半成品冒充 v3；S11 不得复制示例值自我批准。

```json
{
  "schema_version": "s-tier-execution-receipt.v3",
  "harness_metadata": { "phase": "S11_单元测试驱动", "status": "SUCCESS" },
  "contract_evidence": "TDD 三阶段完成：RED 阶段测试失败 → GREEN 阶段测试通过 → REFACTOR 阶段代码重构",
  "files_touched": ["src/utils/parser.ts", "tests/parser.spec.ts"],
  "next_routing": "W9_出口验收 或 P3_单体极速流水线",
  "required_validation_trail": {
    "verification_policy": "RECEIVER_MUST_VERIFY_BEFORE_ACCEPT",
    "required_weapons": [
      "verify-readback",
      "verify-scope-fence",
      "validate-evidence",
      "validate-schema",
      "pytest",
      "coverage"
    ],
    "gatekeeper_cmd": "pytest tests/parser.spec.ts -v"
  },
  "discipline_proof": {
    "entry_readback": {
      "executed": true,
      "timestamp": "<actual ISO-8601 execution timestamp>",
      "proof_of_read": "已阅读当前目标、验收契约与测试需求"
    },
    "scope_fence": {
      "executed": true,
      "timestamp": "<actual ISO-8601 execution timestamp>",
      "files_checked": ["src/utils/parser.ts", "tests/parser.spec.ts"],
      "all_in_scope": true
    },
    "evidence_check": {
      "executed": true,
      "timestamp": "<actual ISO-8601 execution timestamp>",
      "findings_validated": 0,
      "all_passed": true
    },
    "schema_check": {
      "executed": true,
      "timestamp": "<actual ISO-8601 execution timestamp>",
      "missing_fields": []
    }
  },
  "pytest_result": {
    "executed": true,
    "passed": 5,
    "failed": 0,
    "errors": 0,
    "summary": "5 passed in 0.23s",
    "tdd_red_phase": {
      "status": "PASS",
      "red_phase_failed_count": 1,
      "summary": "已物理证明新增测试在实现前按预期失败"
    },
    "tdd_green_phase": {
      "status": "PASS",
      "passed_count": 5,
      "summary": "最小实现后全部目标测试通过"
    },
    "tdd_phases": {
      "red": { "status": "FAIL", "test_count": 1, "description": "初始测试失败（预期行为）" },
      "green": { "status": "PASS", "test_count": 5, "description": "最小实现通过测试" },
      "refactor": { "status": "PASS", "test_count": 5, "description": "重构后测试保持通过" }
    }
  },
  "producer_evidence_summary": {
    "summary": "TDD 三阶段完成，所有测试通过",
    "evidence_refs": ["pytest_output.txt"]
  },
  "tests_changed": ["tests/parser.spec.ts"],
  "sandbox_proof": {
    "schema_version": "stage-execution-sandbox-proof.v1",
    "stage": "S11_单元测试驱动",
    "skill": "S11_测试驱动开发",
    "isolation_mode": "workspace_write_fence",
    "sandbox_status": "PASS",
    "execution_grant_ref": "<actual caller execution grant ref>",
    "write_scope": {
      "allowed_write_paths": ["src/utils", "tests"],
      "touched_paths": ["src/utils/parser.ts", "tests/parser.spec.ts"],
      "no_op_verified": false,
      "all_touched_paths_within_scope": true,
      "path_boundary_audit_ref": "scope-audit.json"
    },
    "command_policy": {
      "policy": "ALLOWLISTED_COMMANDS_ONLY",
      "commands_allowed": ["pytest tests/parser.spec.ts -v"],
      "commands_executed": ["pytest tests/parser.spec.ts -v"],
      "command_audit_ref": "command-audit.json"
    },
    "diff_receipt": {
      "before_ref": "before-change",
      "after_ref": "after-refactor",
      "diff_ref": "working-diff.patch",
      "changed_files": ["src/utils/parser.ts", "tests/parser.spec.ts"]
    },
    "environment": {
      "host_os": "<actual host OS>",
      "execution_host": "<actual execution host>",
      "secret_scan_ref": "",
      "network_boundary": "none",
      "credential_redaction_confirmed": true
    },
    "evidence_refs": ["scope-audit.json", "command-audit.json", "working-diff.patch"]
  },
  "s13_code_review": {
    "harness_metadata": { "phase": "S13_Code_Review", "status": "APPROVED" },
    "reviewed_files": ["src/utils/parser.ts"],
    "reviewed_tests": ["tests/parser.spec.ts"],
    "findings_open": 0,
    "blocking_findings": 0,
    "evidence_ref": "s13-review.json",
    "summary": "由独立 S13 在当前变更集上产出"
  },
  "s14_verification": {
    "harness_metadata": { "phase": "S14_Final_Verification", "status": "APPROVED" },
    "command_run": "pytest tests/parser.spec.ts -v",
    "exit_code": 0,
    "failures": 0,
    "evidence_ref": "s14-verification.json",
    "summary": "由独立 S14 在最后一次相关修改后产出"
  },
  "evidence_pointers": [
    { "type": "test", "ref": "pytest_output.txt" },
    { "type": "sandbox", "ref": "scope-audit.json" }
  ]
}
```

</template>
