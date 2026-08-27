@echo off
rem Restart Jiajia: kill any running jiajia instance, then relaunch detached.
cd /d "%~dp0.."
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'jiajia' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
start "" pythonw -m jiajia.main
