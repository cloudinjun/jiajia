@echo off
rem Restart Paperclip Pal: kill any running python_pal instance, then relaunch detached.
cd /d C:\Users\cloud\.codex\desktop-pets\paperclip-pal
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'python_pal' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
start "" pythonw -m python_pal.main
