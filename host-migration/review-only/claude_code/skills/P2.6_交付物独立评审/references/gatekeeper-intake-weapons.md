<!-- 拆自 P2.6 SKILL.md §2 [STATE: BLUE_TEAM_INTAKE]（2026-08-15 走查 SKSEM-11） -->

- **【反偷懒武器：审计预检三件套】**：接收蓝队交付物后，P2.6 **必须依次执行**三个武器：
  1. `python @@GENERAL_ROOT:win@@\control\guards\gatekeeper_weapons.py verify-scope-fence <audit_session_dir> --file <交付物路径>` — 确认交付物路径在授权范围内，防止审错文件。
  2. `python @@GENERAL_ROOT:win@@\control\guards\gatekeeper_weapons.py verify-readback <audit_session_dir> --file <交付物路径> --slice 1` — 随机抽取交付物中的一行内容，P2.6 必须在报告中引用该行证明自己真正读了交付物（而非凭记忆橡皮图章）。
  3. `python @@GENERAL_ROOT:win@@\control\guards\gatekeeper_weapons.py plant-canary <audit_session_dir> --canary-id audit_trap --inject` — 注入金丝雀。如果 P2.6 的审计报告中包含该金丝雀值，说明 P2.6 在伪造审计结果。
- **【前置自律证据物理校验 (Discipline Proof Pre-Check)】**：在执行完审计预检三件套后，P2.6 **必须物理调用专用武器校验蓝队的自律证据**：
  - 将蓝队交付物的握手/回执 JSON 写入临时文件，然后调用：
    - 审 S 兵团回执时：`python @@GENERAL_ROOT:win@@\control\guards\gatekeeper_weapons.py validate-discipline-proof --input <回执JSON> --tier s --session-dir <audit_session_dir> --source-file <交付物路径> --slice 1`
    - 审 P1/P2/P2.5/P4 握手时：`python @@GENERAL_ROOT:win@@\control\guards\gatekeeper_weapons.py validate-discipline-proof --input <握手JSON> --tier p --session-dir <audit_session_dir>`
  - 武器会检查：(1) discipline_proof 字段是否存在 (2) 各卡口的 executed/timestamp 是否真实填充 (3) executed=false 时是否提供了 reason
  - 如果校验 **通过**：P2.6 继续用 `verify-readback --verify` 交叉验证 `proof_of_read` 内容；对 S 兵团回执还会拿 `gatekeeper_state.json` 里的挑战记录反查 `challenge_line/proof_of_read` 是否和真实读验一致
  - 如果校验 **失败**（exit=1）：P2.6 在审计报告首段标注 `⚠️ BLUE_MISS` + 武器输出的 issues 清单，容错阈值收紧
- **【审计状态单写者规则 (Gatekeeper State Single-Writer)】**：同一个 `gk_audit_session/gatekeeper_state.json` 是共享状态文件。`verify-scope-fence`、`verify-canary`、`validate-discipline-proof`、`check-coverage`、`validate-execution-trail` 等会写状态的命令必须顺序执行；只读文件检查才允许并行。若出现 JSON `Extra data` 或状态文件破损，先修复审计状态并记录到错题本，再继续审计。
- **【修补后一致性扫尾 (Post-Repair Consistency Sweep)】**：P2.6 允许上游蓝队修补缺陷后，必须复扫所有正式产物：Tech Spec、handoff、manifest、review receipt、evidence、pipeline-state。若 PASS 后仍残留 `DRAFT_READY`、`PENDING`、`待执行` 等旧状态描述，或 manifest 用 PASS 搭配未完成条件，必须继续打回修补。P2.6 不只审“缺什么”，还要审“修完后是否全局同态”。同态不只看路径存在，还必须抽查正式消费面的 `status / reasons / warnings / evidence_hash / content hash` 是否与当前封签一致；route card、GateOutput、audit record、handoff、governance receipt 任一内容仍指向旧批次，就不得给 PASS。
- **【代码化 BLUE_MISS 钩子】**：运行时 `reviewer_protocol.py` 会读取 `blue_team_self_review`、`{stage}_blue_team_review`、`{stage}_self_review_report`、`{stage}_delivery_receipts.blue_team_review` 中的 `passed_checks/pass_checks/checked_passes/reviewed_passes`。蓝队标 PASS、红队结构化检查 FAIL 的项必须落为 `BLUE_MISS`，不得继续记作普通 FAIL 或被吞掉。
