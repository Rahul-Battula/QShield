@echo off
setlocal
cd /d "%~dp0"

rem QShield -- one-command launcher.
rem Starts the backend (which serves the frontend) and opens the dashboard.

set "PY=py -3.11"
%PY% -c "pass" >nul 2>&1
if errorlevel 1 set "PY=python"

%PY% -c "import app" >nul 2>&1
if errorlevel 1 (
    echo First run: installing Python dependencies with %PY% ...
    %PY% -m pip install -r requirements.txt
)

rem Build the Vite dashboard if it isn't built and Node is available.
rem If Node is missing, the backend falls back to the vendored frontend-legacy/.
if not exist "frontend\dist\index.html" (
    where npm >nul 2>&1 && (
        echo Building the dashboard ^(one-time^) ...
        pushd frontend
        call npm install --no-audit --no-fund
        call npm run build
        popd
    )
)

echo.
echo   QShield  -^>  http://127.0.0.1:8000/
echo.
%PY% -m app.api
