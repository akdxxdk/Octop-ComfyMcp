@echo off
REM ===================================================================
REM  ComfyUI (aki pack) headless launcher -- for Octop MCP (comfy-mcp)
REM  -------------------------------------------------------------------
REM  Usage: start-comfyui.bat [aki root dir]
REM    no arg     -> uses DEFAULT_ROOT below
REM    with arg   -> uses the given aki root dir
REM
REM  IMPORTANT: the aki pack nests ComfyUI one level deeper:
REM      <root>\ComfyUI\main.py        <- real ComfyUI root
REM      <root>\python\python.exe      <- bundled interpreter
REM
REM  NOTE: keep this file ASCII-only (no CJK). cmd.exe parses .bat in
REM        the local codepage; non-ASCII bytes can break parenthesized
REM        blocks (exit code 255 with garbled output).
REM -------------------------------------------------------------------
REM  EDIT THIS LINE to match your aki pack location:
set "DEFAULT_ROOT=<COMFYUI_AKI_ROOT>"
REM ===================================================================

set "COMFY_ROOT=%~1"
if "%COMFY_ROOT%"=="" set "COMFY_ROOT=%DEFAULT_ROOT%"

REM --- guard: placeholder not replaced? (substitution test; "<" is special) ---
set "CR=%COMFY_ROOT%"
if not "%CR:<=%"=="%CR%" (
  echo [ERROR] COMFYUI_AKI_ROOT placeholder not replaced. Edit DEFAULT_ROOT at top.
  exit /b 1
)

if not exist "%COMFY_ROOT%\ComfyUI\main.py" (
    echo [ERROR] main.py not found under "%COMFY_ROOT%\ComfyUI\".
    echo         Usage: %~nx0 [aki root dir]
    echo         e.g.   %~nx0 <COMFYUI_AKI_ROOT>
    exit /b 1
)

echo Starting ComfyUI ...
echo   Root: %COMFY_ROOT%
echo   URL : http://127.0.0.1:8188
echo.

cd /d "%COMFY_ROOT%\ComfyUI"
"%COMFY_ROOT%\python\python.exe" main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch
