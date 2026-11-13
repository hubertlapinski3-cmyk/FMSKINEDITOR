@echo off
rem FM27 Skin Editor launcher for Windows: double-click to start the editor and open it in the browser.
rem First run creates a private Python environment (.venv) next to this file and installs requirements.txt (needs Python 3.10+ and internet once).
rem Every failure prints what went wrong and the command to run by hand, then waits for a key: the window never closes by itself on an error.
rem To stop the editor: "Quit server" on the Setup tab, Ctrl+C here, or close this window.
rem Optional: set FM27SE_PYTHON to a python.exe to use instead of .venv. Extra arguments run a command and stop, e.g.  "FM27 Skin Editor.bat" check-layout DUMP.json
setlocal EnableExtensions
cd /d "%~dp0"
title FM27 Skin Editor

if "%~1"=="" goto :interactive
call :resolve_python
if errorlevel 1 exit /b 1
"%PY%" -m skin_editor %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo.& echo The command finished with exit code %RC%.
exit /b %RC%

:interactive
set "WS=%FM27SE_WORKSPACE%"
if not defined WS set "WS=%LOCALAPPDATA%\FM27SkinEditor"

rem Already running for this workspace? Open that session instead of starting a second server.
if not exist "%WS%\state\last-url" goto :start
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $u=(Get-Content -Raw -LiteralPath '%WS%\state\last-url').Trim(); $p=([uri]$u).Port; $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri ('http://127.0.0.1:'+$p+'/ping'); if ($r.Content -like 'fm27-skin-editor *') { Start-Process $u; exit 0 } } catch {}; exit 1"
if errorlevel 1 goto :start
echo FM27 Skin Editor is already running: opened the existing session in your browser.
ping -n 4 127.0.0.1 >nul
exit /b 0

:start
call :resolve_python
if errorlevel 1 exit /b 1
echo Starting FM27 Skin Editor ...
echo Keep this window open while you use the editor. To stop it: "Quit server" on the Setup tab, Ctrl+C here, or close this window.
"%PY%" -m skin_editor
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" exit /b 0
echo.
echo ERROR: the editor stopped or could not start (exit code %RC%). The details are printed above.
echo If it says the address is already in use, another program (or another copy of the editor) holds the port:
echo   close it, or change "port" under "server" in "%WS%\config.json".
echo To run it by hand in a terminal:
echo   cd /d "%~dp0"
echo   "%PY%" -m skin_editor
goto :pause_exit

:resolve_python
rem sets PY to a python.exe that has the requirements; creates .venv on first run
if defined FM27SE_PYTHON (
  set "PY=%FM27SE_PYTHON%"
  exit /b 0
)
if exist ".venv\Scripts\python.exe" goto :have_venv
set "BASE="
rem prefer a Python that has prebuilt packages for requirements.txt (3.12 to 3.14); the newest or pre-release one ("py -3") is the last resort
for %%C in ("py -3.12" "py -3.13" "py -3.11" "py -3.14" "py -3.10" "python" "py -3") do (
  if not defined BASE (
    %%~C -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "BASE=%%~C"
  )
)
if not defined BASE (
  echo.
  echo ERROR: Python 3.10 or newer was not found.
  echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^), then double-click this file again.
  echo Or, if Python is installed but not on PATH, run once in a terminal:
  echo   cd /d "%~dp0"
  echo   "C:\path\to\python.exe" -m venv ".venv"
  goto :pause_exit
)
echo First run: creating the Python environment with %BASE% ...
%BASE% -m venv ".venv"
if errorlevel 1 (
  echo.
  echo ERROR: creating the Python environment failed ^(see above^).
  echo To do it by hand in a terminal:
  echo   cd /d "%~dp0"
  echo   %BASE% -m venv ".venv"
  echo   ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  goto :pause_exit
)
:have_venv
set "PY=%~dp0.venv\Scripts\python.exe"
"%PY%" -c "import UnityPy" >nul 2>nul
if not errorlevel 1 exit /b 0
echo Installing the Python packages ^(first run, this can take a few minutes^) ...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
  rem a damaged or locked file in pip's download cache ^(Permission denied^) fails the install: retry once without the cache
  echo.
  echo The install failed. Retrying once without pip's download cache ...
  "%PY%" -m pip install --no-cache-dir -r "%~dp0requirements.txt"
)
if errorlevel 1 (
  echo.
  echo ERROR: installing the Python packages failed ^(see above^). Check your internet connection.
  echo If the message says "Permission denied" on a file under pip\cache, that cache file is locked: delete the folder
  echo   "%LOCALAPPDATA%\pip\cache"   ^(or run the retry command below^).
  echo If the message mentions "Microsoft Visual C++ 14.0" or building a wheel, this Python version has no prebuilt packages.
  echo Install Python 3.12 from https://www.python.org/downloads/, delete the ".venv" folder next to this file, and double-click again.
  echo To retry by hand in a terminal:
  echo   "%PY%" -m pip install --no-cache-dir -r "%~dp0requirements.txt"
  goto :pause_exit
)
exit /b 0

:pause_exit
echo.
echo This window stays open so you can read the message. Press a key to close it.
pause >nul
exit /b 1
