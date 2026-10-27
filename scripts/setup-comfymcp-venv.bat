@echo off
REM ===================================================================
REM  Create an isolated venv for comfy-mcp
REM  -------------------------------------------------------------------
REM  WHY ISOLATED?
REM    comfy-mcp 0.10.0    requires MCP SDK 2.x -> mcp.server.mcpserver
REM    langchain-mcp-adapters (used by Octop) requires MCP SDK 1.x ->
REM        mcp.server.fastmcp.*  (imported at module TOP LEVEL)
REM    They are mutually exclusive in a single env. Upgrading the main
REM    env to 2.x breaks Octop's whole MCP client; downgrading to 1.x
REM    makes comfy-mcp fail to start. Isolation is the only safe fix.
REM
REM  NOTE: keep this file ASCII-only (no CJK).
REM -------------------------------------------------------------------
REM  EDIT THESE TWO LINES to match your environment
REM  (or set CONDA_BASE / COMFYMCP_VENV in a local .env and run from there):
set "BASE_PYTHON=<CONDA_BASE>/python.exe"
set "VENV_DIR=<COMFYMCP_VENV>"
REM ===================================================================

set "PIP_INDEX=https://mirrors.aliyun.com/pypi/simple"

REM --- guard: placeholder not replaced? (use substitution test; do NOT
REM     echo the value, because a literal "<" in it is parsed as redirection) ---
set "BP=%BASE_PYTHON%"
if not "%BP:<=%"=="%BP%" (
  echo [ERROR] BASE_PYTHON still contains a placeholder. Edit the top of this script.
  exit /b 1
)
set "VD=%VENV_DIR%"
if not "%VD:<=%"=="%VD%" (
  echo [ERROR] VENV_DIR still contains a placeholder. Edit the top of this script.
  exit /b 1
)

echo ============================================================
echo  comfy-mcp isolated venv setup
echo ============================================================
echo   Base python : %BASE_PYTHON%
echo   Venv dir    : %VENV_DIR%
echo   Pip index   : %PIP_INDEX%
echo.

if not exist "%BASE_PYTHON%" (
    echo [ERROR] Base python not found: "%BASE_PYTHON%"
    echo         Edit BASE_PYTHON at the top of this script.
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [1/3] Creating venv ...
    "%BASE_PYTHON%" -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] venv creation failed.
        exit /b 1
    )
) else (
    echo [1/3] Venv already exists, skipping creation.
)

echo [2/3] Upgrading pip ...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip -i "%PIP_INDEX%"

echo [3/3] Installing from comfy-mcp-requirements.txt ...
"%VENV_DIR%\Scripts\python.exe" -m pip install -i "%PIP_INDEX%" -r comfy-mcp-requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed. Try another mirror, e.g.
    echo         -i https://pypi.tuna.tsinghua.edu.cn/simple
    exit /b 1
)

echo.
echo Verifying imports ...
"%VENV_DIR%\Scripts\python.exe" -c "from mcp.server.mcpserver import MCPServer; import comfy_mcp.server; print('[OK] comfy-mcp isolated env is ready')"
if errorlevel 1 (
    echo [ERROR] Import check failed.
    exit /b 1
)

echo.
echo ============================================================
echo  Done.
echo
echo  Next steps:
echo    1. Copy config\comfyui-mcp-connector.example.json
echo       to     config\comfyui-mcp-connector.json
echo    2. Edit it:
echo         command          = %VENV_DIR%\Scripts\comfy-mcp.exe
echo         env.COMFY_BIN    = <your octop env>\Scripts\comfy.exe
echo    3. Run: python scripts\setup-connector.py
echo    4. Run: python scripts\verify.py
echo ============================================================
pause
