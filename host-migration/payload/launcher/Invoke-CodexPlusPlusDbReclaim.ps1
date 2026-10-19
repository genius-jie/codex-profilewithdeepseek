#requires -Version 7.0
# Invoke-CodexPlusPlusDbReclaim.ps1
# Permanent, lossless guard against unbounded SQLite bloat in the Codex++ profile.
#
# Root cause (verified 2026-09-20): Codex core (codex.exe / sqlx) churns its log &
# thread-history SQLite DBs (insert heavy rows, prune old ones) but the freed pages
# stay in the freelist and are never returned to disk, so files ratchet up session
# after session (logs_2.sqlite hit 3.1GB with ~32MB of live rows; incremental_vacuum
# does NOT reclaim this legacy freelist, only VACUUM does). This runs ONE python
# process that, for each *.sqlite under the profile with a big-enough freelist,
# promotes auto_vacuum=FULL and VACUUMs it, while the app is not yet holding the DBs.
#
# Scope: SQLite physical compaction ONLY. No tweak, plugin, feature, schema or row
# is changed. Lossless by SQLite guarantee. Wired into Start-CodexPlusPlus-Proxy.cmd
# BEFORE the main launcher, so every start self-heals; future growth stays bounded.
param(
    [string]$CodexHome = '@@CODEXPP_HOME:win@@',
    [long]$FreelistThresholdMB = 200,
    [switch]$DryRun
)
$ErrorActionPreference = 'SilentlyContinue'
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = 'python' }
$logDir = '@@CODEXPP_RUNTIME:win@@\log'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir ("db_reclaim_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
function L($m){ $line='[{0}] {1}' -f (Get-Date -Format 's'),$m; Add-Content -Path $log -Value $line; Write-Host $line }

if (-not (Test-Path $CodexHome)) { L "no .codex profile at $CodexHome; skip"; exit 0 }

# One python process walks all DBs -> single startup, keeps launch snappy.
$pyCode = @'
import sqlite3,sys,os
root=sys.argv[1]; thr=int(sys.argv[2]); dry=(sys.argv[3]=='1')
out=[]; total=0
for dp,_,fs in os.walk(root):
    for fn in fs:
        if not fn.endswith('.sqlite'): continue
        db=os.path.join(dp,fn)
        try:
            con=sqlite3.connect(db, isolation_level=None, timeout=2)
            con.execute("PRAGMA busy_timeout=2000")
            ps=con.execute("PRAGMA page_size").fetchone()[0]
            fl=con.execute("PRAGMA freelist_count").fetchone()[0]*ps
            s0=os.path.getsize(db)
            if fl < thr or dry:
                con.close()
                if fl>=thr and dry: out.append("DRY|%s|%d|%d"%(fn,s0,fl))
                continue
            con.execute("PRAGMA auto_vacuum=FULL"); con.execute("VACUUM")
            s1=os.path.getsize(db); con.close()
            total += (s0-s1)
            out.append("VAC|%s|%d|%d|%d"%(fn,s0,s1,fl))
        except Exception as e:
            out.append("ERR|%s|%s"%(fn, type(e).__name__+":"+str(e)[:80]))
print("TOTAL|%d"%total)
for o in out: print(o)
'@
$pyf = Join-Path $env:TEMP 'codexpp_db_reclaim.py'
Set-Content -Path $pyf -Value $pyCode -Encoding utf8
$result = & $py $pyf $CodexHome ($FreelistThresholdMB*1MB) ([int][bool]$DryRun) 2>$null
Remove-Item $pyf -Force -ErrorAction SilentlyContinue

foreach ($line in $result) {
  $p = "$line" -split '\|'
  switch ($p[0]) {
    'TOTAL' { L ("DONE total_reclaimed={0}MB dryrun={1}" -f [math]::Round([int64]$p[1]/1MB,1),[bool]$DryRun) }
    'VAC'   { L ("{0} vacuumed: {1}MB -> {2}MB (freed {3}MB, freelist was {4}MB)" -f $p[1],[math]::Round([int64]$p[2]/1MB,1),[math]::Round([int64]$p[3]/1MB,1),[math]::Round(([int64]$p[2]-[int64]$p[3])/1MB,1),[math]::Round([int64]$p[4]/1MB,1)) }
    'DRY'   { L ("{0} would_vacuum: size={1}MB freelist={2}MB" -f $p[1],[math]::Round([int64]$p[2]/1MB,1),[math]::Round([int64]$p[3]/1MB,1)) }
    'ERR'   { L ("skip {0}: {1}" -f $p[1], $p[2]) }
  }
}
exit 0
