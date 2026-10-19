@echo off
echo Stopping CodexIdSanitizer service...
net stop CodexIdSanitizer
timeout /t 2 /nobreak >nul
echo Starting CodexIdSanitizer service...
net start CodexIdSanitizer
timeout /t 2 /nobreak >nul
echo Checking health...
curl -s http://127.0.0.1:15740/health | findstr "adapter"
pause
