---
domain: meta-governance
tier: L2
doc_status: active-reference
status: active
related:
- @@GENERAL_ROOT:win@@\assets\skills\M5_系统与知识资产治理\SKILL.md
birth_ceremony_id: bc-m5-report-json-template-20260815
birth_ceremony_date: '2026-08-15'
---

# M5 标准通信契约 JSON 模板 + governance_budget 口径

> 由 M5 SKILL.md 外置。完整 JSON 模板与治理预算镜口径见正文。

## 3. 标准通信契约 (Harness JSON I/O - OpenSpec Template)
M5 完成治理任务后，必须向主控台输出标准 JSON 格式报告：
```json
{
  "harness_metadata": { "phase": "M5_Garbage_Collector", "status": "COMPLETED" },
  "cognitive_diagnosis": {
    "conflicts_resolved": "已合并 rules 中冲突的两条规则",
    "ontology_enforced": "已删除 3 份缺乏 tier 元数据的根目录文件，并清理 2 份过期的 tier=04 报告",
    "abstraction_level": "将 15 行的详细记录提炼为 1 条结构化测试规则"
  },
  "execution_actions": [
    { "target": "scripts/orphan_script.py", "action": "PHYSICAL_DELETE", "reason": "未被引用的遗留脚本" },
    { "target": "docs/stray_readme.md", "action": "PHYSICAL_DELETE", "reason": "缺乏 tier/domain YAML 元数据的违规文件" },
    { "target": "rules/execution.md", "action": "REWRITE", "status": "完成规则合并" }
  ],
  "anti_laziness_audit": {
    "samples_checked": 3,
    "results": [
      { "check_id": "ALW-01", "check": "MapReduce分片", "verdict": "PASS", "evidence": "W1契约#abc中Slice切分记录完整" },
      { "check_id": "ALW-05", "check": "物理证据指针", "verdict": "VIOLATION", "evidence": "P3回执中3条finding缺失evidence_pointer", "remediation": "要求P3补齐证据指针后重新提交" }
    ],
    "total_pass": 8,
    "total_violation": 1,
    "total_warning": 0
  },
  "governance_budget": {
    "rules_added": 0,
    "rules_deleted": 2,
    "rules_merged": 1,
    "net_delta": -3,
    "trend": "CONTRACTING",
    "self_reflection": "本轮净收缩：删 2 合 1、零新增。治理系统在做减法，符合宪法。"
  }
}
```

> **【治理预算镜 governance_budget 使用口径】(🆕 v2.8 — advisory 镜子，非门禁)**：本字段是 M5 每轮巡山对自己照的一面镜子，**只反映趋势、不阻断任何操作**。数据从本轮 `execution_actions[]` 直接聚合，零新增采集成本：
> - `rules_added`：本轮新增的规则/STATE/门禁/检查项条数（CREATE 类动作）
> - `rules_deleted` + `rules_merged`：本轮物理删除 + 合并收敛的规则条数（PHYSICAL_DELETE / REWRITE-合并类动作）
> - `net_delta = rules_added - (rules_deleted + rules_merged)`
> - `trend`：`net_delta < 0` → `CONTRACTING`（健康，治理系统在瘦身）；`= 0` → `STEADY`（持平，可接受）；`> 0` → `EXPANDING`（膨胀预警）
> - **当 `trend = EXPANDING` 时，`self_reflection` 必须回答那条判据**：*"本轮新增这些检查，是因为生成系统（提示词/思维模型）真的修不好，还是因为『加个 gate』比『修根因』省事？"* 若是后者，按 agent-constitution「优先改生成系统而非增加检查系统」退回，改用 S22 修提示词或改 IA，而不是新增门禁。
> - **反向配重纪律**：一套成熟的治理系统，长期 `net_delta` 应持平或为负。若连续多轮 `EXPANDING`，说明治理系统本身正在成为需要被治理的对象——这是 M5 该对自己动刀的信号，不是继续加规则的理由。
