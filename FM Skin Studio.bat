@echo off
rem FM Skin Studio (new desktop interface). Double-click to start. The first start compiles the Rust shell (a few minutes); later starts take seconds.
rem The window starts the Python engine itself and stops it (and waits for it) when the window closes.
rem As a fallback, every skin_editor Python process is also stopped after the window has closed, so no old engine survives to be reused.
rem Needs Node and Rust (both installed on this PC).
setlocal EnableExtensions
set "PATH=%PATH%;%USERPROFILE%\.cargo\bin"
cd /d "%~dp0studio" || (echo Cannot find the studio folder next to this file. & pause & exit /b 1)
if not exist node_modules (
  echo First run: installing the interface packages ...
  call npm install || (echo npm install failed. & pause & exit /b 1)
)
call npm run tauri dev
set "RC=%errorlevel%"
rem Fallback cleanup, runs every time after the main window has exited.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'skin_editor' -and $_.Name -match 'python' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
if not "%RC%"=="0" (
  echo.
  echo The shell stopped with an error. The details are printed above.
  echo Check that Node and Rust are installed:  node -v   and   cargo --version
  pause
  exit /b 1
)
