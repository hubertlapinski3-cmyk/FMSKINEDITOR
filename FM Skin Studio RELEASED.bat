@echo off
rem RELEASED launcher: the installed FM Skin Studio (version 1.1.1), for comparison with the TESTING build.
rem This is the full app that the updater installs. It does NOT contain unreleased fixes from this repo.
rem Do NOT run the TESTING launcher at the same time: both use the same workspace.
setlocal EnableExtensions
set "EXE=%LOCALAPPDATA%\FM Skin Studio\fm-skin-studio.exe"
if not exist "%EXE%" (
  echo Installed FM Skin Studio not found at "%EXE%".
  pause
  exit /b 1
)
echo.
echo === RELEASED FM Skin Studio ===
echo.
start "" "%EXE%"
