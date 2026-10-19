# _archived/ — 已下线的 hook 脚本

## wrapper_verify_helper_ssot_dedup.py（2026-08-15 归档）

下线原因：
1. 未挂载：settings.local.json 中 0 处引用，从未被任何 hook 事件调用。
2. 路径解析错误：默认指向 $HOME/openclaw-mono（@@USERPROFILE:win@@\openclaw-mono，不存在），
   真实仓库在 @@OPENCLAW_ROOT:win@@。
3. 最后一次运行 2026-07-03（42 天未跑），且该次是人工调用。
4. 即使运行也是 passive log-only（return 0，从不阻断），无门禁价值。

其包裹的真实 SSOT 去重门禁仍在项目中存活：
@@OPENCLAW_ROOT:win@@\projects\automation-core\scripts\verify-helper-ssot-dedup.py（303 行），
由项目自身维护。若需恢复用户级包装，先修正 OPENCLAW_MONO 路径解析再挂载。
