@echo off
setlocal

rem Start-CodexPlusPlus.ps1 owns the single StartupGuard transaction and all
rem Codex++ isolation, base repair, and Host capability projection work.
rem Self-heal first: re-inject the package-identity launch line if a Codex++
rem upgrade regenerated Start-CodexPlusPlus.ps1 (exit code intentionally ignored).
"@@POWERSHELL_EXE:win@@" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Invoke-CodexPlusPlusLauncherCompat.ps1"
rem Lossless SQLite freelist reclaim BEFORE the app opens its DBs; keeps the Codex
rem core log/thread DBs from ratcheting up unboundedly (no tweak/feature touched).
"@@POWERSHELL_EXE:win@@" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Invoke-CodexPlusPlusDbReclaim.ps1"
rem Ensure the project-workspace parent chain exists so the app's non-recursive
rem mkdir of Documents\Codex\<date> never hits ENOENT (idempotent, leaf not created).
"@@POWERSHELL_EXE:win@@" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Invoke-CodexPlusPlusEnsureWorkspace.ps1"
"@@POWERSHELL_EXE:win@@" -NoProfile -File "%~dp0Start-CodexPlusPlus.ps1" -SkipConnectorSync -SkipOpenCliAdapterSync -SkipSessionPathTest
set "CODEXPP_EXIT=%ERRORLEVEL%"

if not "%CODEXPP_EXIT%"=="0" (
    echo.
    echo Codex++ launch failed!
    pause
)

endlocal & exit /b %CODEXPP_EXIT%
