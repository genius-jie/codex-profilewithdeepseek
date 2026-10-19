---
name: tophub-remote-deploy
description: Deploy and operate the TopHub Daily Trend Radar public Linux service at 115.191.17.254 and its governed local debug slot. Use when Codex is asked to deploy, redeploy, verify, smoke test, restart, rollback, clean disk space, troubleshoot TopHub, open local PG data, run hot reload, inspect local Next.js slot conflicts, or debug long-list filter switching lag/RSC request contention, including release/current publishing, PM2, nginx-facing Next.js, PostgreSQL migrations, deployment receipts, public API checks, browser verification, local ops:start-dev-pg entrypoint enforcement, and Next Link prefetch checks.
domain: tophub-ops
tier: L1
doc_status: active-ssot
related:
  - @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\ops\auto-deploy-to-public.ps1
  - @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\ops\linux-deploy.sh
  - @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\ops\build-release-package.ps1
  - @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web\scripts\guard-next-build.mjs
  - @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web\scripts\start-dev-pg.ps1
  - @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web\scripts\dev-postgres.mjs
  - @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web\components\video-reports-shell.tsx
  - @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\ops\linux-disk-housekeep.sh
  - @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\ops\remote-disk-housekeep.ps1
birth_ceremony_id: bc-tophubremotedeploy-6e2c1a9b
birth_ceremony_date: 2026-05-07
---

# TopHub Remote Deploy

Use this skill for the dedicated TopHub Daily Trend Radar public host. Keep the path fast: verify local build safety, build one release artifact, publish through `release/current`, then prove the public service is live with smoke data and a deployment receipt.

## Fixed Context

- Workspace: `@@OPENCLAW_ROOT:win@@`
- Project: `@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar`
- Public URL: `http://115.191.17.254/`
- Remote SSH: `root@115.191.17.254`
- Remote app dir: `/opt/tophub-daily-trend-radar`
- PM2 app: `tophub-daily-trend-radar`
- Next.js port: `3001`, nginx exposes port `80`
- Linux deploy entry: `ops/linux-deploy.sh`
- Release builder: `ops/build-release-package.ps1`

## Operating Principles

- 发布只走 `release -> current`，现场目录不直接构建。
- 回滚是正常动作，不是补丁；切回后要重启、smoke、留 receipt。
- 端口只认一个 owner；PM2 pid、端口 owner、cwd、script、`current` 必须对齐。
- smoke 要用真实业务数据，别拿固定样板请求当绿灯。
- 先看 receipt/status，再看终端输出；终端说过的话不算账本。
- 磁盘先分层：缓存、临时文件、旧备份、日志可治理，`release`、`runtime`、数据库、PM2 状态默认不碰。
- 本地 `.next` 只能有一个 owner，build 前先审计，冲突进程先停。
- 本地热更新只写 `.next-dev*`，构建/启动只写 `.next`；日志和 status 落到 `runtime`，不要放进 `.next`。
- 本地看 PG 真数据只走 `npm run ops:start-dev-pg`；禁止手写 `next dev`、`npm run dev:pg`、`next start` 或 `Start-Process` 抢 3333。
- 清理脚本必须幂等、可重复安装、可审计。

## Local Debug Entry Gate

Use this gate whenever the user asks to open the local page, verify local PG data, debug hot reload, or use port `3333`.

1. Audit the local runtime slot:

```powershell
cd @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web
npm run ops:audit-next
```

2. If the audit reports a build/start `.next` conflict, stop the old local Next owner:

```powershell
npm run ops:stop-next
```

3. Start local PostgreSQL-backed hot reload only through the governed wrapper:

```powershell
npm run ops:start-dev-pg
```

4. Verify the wrapper receipt and health endpoint:

```powershell
Get-Content @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\runtime\logs\local-web\dev-pg-status.json
Invoke-RestMethod -Uri http://127.0.0.1:3333/api/health -TimeoutSec 10
```

Do not directly run `next dev`, `npm run dev`, `npm run dev:pg`, `next start`, or ad hoc `Start-Process` for local port `3333`. Those commands bypass the slot boundary and can make `.next` and `.next-dev-pg` overwrite each other. If an exceptional debug case truly needs a raw command, first state why the wrapper is insufficient, run `npm run ops:audit-next`, and write a status receipt under `runtime\logs\local-web`.

## Pitfall Prevention Rules

### Local Workstation

- If `http://127.0.0.1:3333/api/health` returns `mode=file` while the user asked for current PG data, the wrong entrypoint is running. Stop local Next owners with `npm run ops:stop-next`, then use `npm run ops:start-dev-pg`.
- If `npm run ops:audit-next` returns `conflicts`, do not build and do not bypass the guard. Clear the owner with `npm run ops:stop-next` or inspect the PID before continuing.
- `isolatedDevProcesses` in `ops:audit-next` are allowed during a build; they must be `next dev` descendants using `.next-dev*`, not `next start` owners of `.next`.
- Never put local debug logs, status files, or ad hoc receipts under `.next`. Use `runtime\logs\local-web`.
- If `ops:start-dev-pg` fails, read `runtime\logs\local-web\dev-pg-status.json`, then the referenced stdout/stderr logs. Do not "verify quickly" by switching to raw `next start`.
- A raw local command is an exception path, not a normal shortcut. Before using one, state why the wrapper is insufficient, run `npm run ops:audit-next`, and leave a status receipt under `runtime\logs\local-web`.
- If long lists become slow after filters or date/source switches, inspect `next/link` first. Repeated list links must set `prefetch={false}` so default prefetch does not steal App Router RSC requests from the active filter navigation.

### Public Linux Host

- Treat `/opt/tophub-daily-trend-radar/current` as a pointer, not a workshop. Do not build, patch, or clean inside `current` while PM2 owns the app.
- A deploy is incomplete until all four are true: `current` points at the intended release, PM2 is online, port `3001` is owned by the PM2 Next process, and the latest deploy receipt plus smoke data are present.
- Rollback is the first recovery tool when a bad release is already live. Do not hot-edit `current` to "save time".
- Keep at least two retained releases. If cleanup would leave no rollback target, stop.
- Disk cleanup must stay in safe scopes: apt/npm/pip caches, journald limits, old full backups, and old packaged artifacts. Do not delete `releases`, `runtime`, PostgreSQL data, PM2 state, or active release files as a disk shortcut.
- If root disk pressure is mostly outside TopHub, run disk housekeeping and record a status receipt; do not blame or prune the project directory without evidence.
- Terminal output is a hint, not proof. Final status must cite receipts, health checks, PM2/port owner, release pointer, and disk status when relevant.

## Golden Path: Publish

1. Check what changed before packaging:

```powershell
git -C @@OPENCLAW_ROOT:win@@ status --short -- projects/tophub-daily-trend-radar | Measure-Object -Line
git -C @@OPENCLAW_ROOT:win@@ status --short -- projects/tophub-daily-trend-radar | Select-Object -First 80
```

2. Before any local build, audit the local Next `.next` owner:

```powershell
cd @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web
npm run ops:audit-next
```

If the audit reports a local `next dev` or `next start` process using this app's `.next`, stop it before building:

```powershell
npm run ops:stop-next
```

3. Run the minimum local gates:

```powershell
npm run typecheck
npm run build
```

For smoke runner or deployment contract changes, also run:

```powershell
cd @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar
python -m pytest tests/smoke/test_smoke_runner_contract.py -q
```

4. Build one release package. The builder emits both `.zip` and `.tar.gz`; prefer the `.tar.gz`.

```powershell
cd @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\ops\build-release-package.ps1
```

5. Publish with the atomic release flow:

```powershell
cd @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\ops\auto-deploy-to-public.ps1 -DeployAction quick
```

The script uploads the latest package, extracts into `/opt/tophub-daily-trend-radar/releases/<release_id>`, builds inside that release directory, then atomically switches `/opt/tophub-daily-trend-radar/current`.

Use `-DeployAction deploy` only when migrations must run:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\ops\auto-deploy-to-public.ps1 -DeployAction deploy
```

## Rollback

Rollback switches `current`, clean-restarts PM2, runs smoke, and writes a receipt.

Rollback to the previous retained release:

```powershell
cd @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\ops\auto-deploy-to-public.ps1 -DeployAction rollback
```

Rollback to a named release:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\ops\auto-deploy-to-public.ps1 -DeployAction rollback -RollbackRelease tophub-daily-trend-radar-YYYYMMDD-HHMMSS
```

## Remote Direct Actions

Use the remote `linux-deploy.sh` directly for pure reload or smoke. Do not use `auto-deploy-to-public.ps1 -DeployAction smoke` as a pure smoke command, because the wrapper is a publish path for non-rollback actions.

```powershell
ssh root@115.191.17.254 'cd /opt/tophub-daily-trend-radar/current && bash ops/linux-deploy.sh smoke'
ssh root@115.191.17.254 'cd /opt/tophub-daily-trend-radar/current && bash ops/linux-deploy.sh reload'
```

The smoke script auto-selects a data-bearing date and slot when `SMOKE_DATE` and `SMOKE_SLOT` are not supplied. It tries recent dates and the current slots `13:00`, then `09:00`.

## Safety Rules

- Never build inside live `/opt/tophub-daily-trend-radar/current` while PM2 owns the app. Build only in a release directory.
- `auto-deploy-to-public.ps1` uses a local deploy lock at `scratch\tophub-deploy.lock`; if it says another deployment is running, stop and investigate instead of bypassing it.
- Remote publish defaults to retaining 3 releases. Keep at least 2 so rollback remains possible.
- PM2 is clean-started instead of hot reloaded to avoid fork-mode port races on `3001`.
- If port `3001` is held by an orphan `next-server`, stop only that orphan after confirming PM2 is not the owner.
- Runtime env comes from `.env` or the existing PM2 process. Never print secrets.
- If `current` changes while you are operating, treat it as possible manual or external automation activity. Verify PM2, health, and receipts before switching anything back.

## Required Verification

After publish or rollback, verify the release pointer, PM2, port, receipt, public health, and page render.

Remote release and receipt:

```powershell
ssh root@115.191.17.254 'printf "current="; readlink -f /opt/tophub-daily-trend-radar/current; printf "receipt="; ls -1t /opt/tophub-daily-trend-radar/deploy-receipts/*.json | head -1; printf "releases="; find /opt/tophub-daily-trend-radar/releases -mindepth 1 -maxdepth 1 -type d | wc -l'
```

Public API:

```powershell
$receiptPath = (ssh root@115.191.17.254 'ls -1t /opt/tophub-daily-trend-radar/deploy-receipts/*.json | head -1').Trim()
$receipt = ((ssh root@115.191.17.254 "cat $receiptPath") -join "`n") | ConvertFrom-Json
$smokeDate = if ($receipt.smoke.date) { $receipt.smoke.date } else { Get-Date -Format 'yyyy-MM-dd' }
$smokeSlot = if ($receipt.smoke.slot) { [uri]::EscapeDataString($receipt.smoke.slot) } else { '13%3A00' }
$health = Invoke-RestMethod -Uri 'http://115.191.17.254/api/health' -TimeoutSec 20
$trends = Invoke-RestMethod -Uri "http://115.191.17.254/api/trends?date=$smokeDate&slot=$smokeSlot" -TimeoutSec 20
$reports = Invoke-RestMethod -Uri "http://115.191.17.254/api/reports?date=$smokeDate" -TimeoutSec 20
[pscustomobject]@{
  healthOk = $health.ok
  mode = $health.mode
  snapshots = $health.snapshots
  items = $health.items
  smokeDate = $smokeDate
  smokeSlot = $receipt.smoke.slot
  trendsTotal = $trends.total
  trendGroups = @($trends.groups).Count
  reportsOk = $reports.ok
} | ConvertTo-Json -Compress
```

PM2 and port:

```powershell
ssh root@115.191.17.254 'pm2 ls --no-color | sed -n "1,20p"; ss -ltnp "sport = :3001" || true'
```

Use Codex bundled Playwright instead of requiring project-local `playwright`:

```powershell
$node = '@@USERPROFILE:win@@\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$env:NODE_PATH = '@@USERPROFILE:win@@\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
@'
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto("http://115.191.17.254/", { waitUntil: "networkidle" });
  const title = await page.locator("body").innerText();
  console.log(JSON.stringify({
    hasTrendRadar: title.includes("热点雷达"),
    hasMorningAfternoon: title.includes("早上") && title.includes("下午"),
    bodyHead: title.slice(0, 200)
  }, null, 2));
  await browser.close();
})();
'@ | & $node -
```

## Disk Housekeeping

If the root filesystem is high, inspect first:

```powershell
ssh root@115.191.17.254 'df -h /; df -ih /; du -xhd1 / 2>/dev/null | sort -h | tail -20'
```

Safe recurring housekeeping is installed on the host:

- Repo script: `@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\ops\linux-disk-housekeep.sh`
- Remote wrapper: `@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\ops\remote-disk-housekeep.ps1`
- Script: `/usr/local/sbin/tophub-disk-housekeep.sh`
- Cron: `/etc/cron.d/tophub-disk-housekeep`
- Journal cap: `/etc/systemd/journald.conf.d/99-tophub-disk-cap.conf`

It only clears package caches, caps systemd journal, removes TopHub deployment temp files from `/tmp`, and prunes legacy `/opt/tophub-daily-trend-radar.backup.*` directories when `release/current` is healthy. It must not delete PostgreSQL data, release directories, PM2 state, runtime artifacts, or browser automation caches unless `TOPHUB_CLEAN_BROWSER_CACHE=1`.

Use the wrapper for repeatable audit, clean, or install:

```powershell
cd @@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\ops\remote-disk-housekeep.ps1 -Action audit
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\ops\remote-disk-housekeep.ps1 -Action clean
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\ops\remote-disk-housekeep.ps1 -Action install
```

## Cleanup

```powershell
ssh root@115.191.17.254 'find /tmp -maxdepth 1 \( -type d -name "tophub-release-*" -o -type f -name "tophub-daily-trend-radar-*.tar.gz" -o -type f -name "tophub-remote-*.sh" \) -exec rm -rf -- {} +'
```

## Report Back

Report these facts, not raw logs:

- Public URL
- Health mode and `ok` status
- PM2 app status and PID
- Port `3001` owner
- `current` target and latest deployment receipt path
- Public data count used for smoke
- Browser verification highlights
- Root filesystem usage if disk work was part of the task
- Any residual risk, especially external/manual `current` changes or smoke data gaps
