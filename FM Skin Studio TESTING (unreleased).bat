@echo off
rem TESTING launcher: the UNRELEASED Studio, compiled from this repo's source.
rem Use this to test the latest fixes before they are released, then report what you find.
rem It runs `npm run tauri dev`, so the version shown is the source version (1.1.0), not the installed 1.1.1.
rem Do NOT run the RELEASED launcher at the same time: both use the same workspace.
setlocal EnableExtensions
set "PATH=%PATH%;%USERPROFILE%\.cargo\bin"
cd /d "%~dp0studio" || (echo Cannot find the studio folder next to this file. & pause & exit /b 1)
if not exist node_modules (
  echo First run: installing the interface packages ...
  call npm install || (echo npm install failed. & pause & exit /b 1)
)
echo.
echo === TESTING Studio (unreleased source) ===
echo.
call npm run tauri dev
set "RC=%errorlevel%"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'skin_editor' -and $_.Name -match 'python' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
if not "%RC%"=="0" (
  echo.
  echo The testing Studio stopped with an error. Details are above.
  pause
  exit /b 1
)
