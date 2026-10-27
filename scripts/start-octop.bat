@echo off
REM ===================================================================
REM  Octop launcher
REM  -------------------------------------------------------------------
REM  Usage: start-octop.bat [conda env dir]
REM    no arg  -> uses DEFAULT_ENV below
REM    with arg-> uses the given conda env dir
REM
REM  NOTE: keep this file ASCII-only (no CJK). cmd.exe parses .bat in
REM        the local codepage; non-ASCII bytes can garble output and
REM        even break parenthesized blocks.
REM -------------------------------------------------------------------
REM  EDIT THIS LINE to match your conda env location:
set "DEFAULT_ENV=<OCTOP_CONDA_ENV>"
REM ===================================================================

set "OCTOP_ENV=%~1"
if "%OCTOP_ENV%"=="" set "OCTOP_ENV=%DEFAULT_ENV%"

REM --- guard: placeholder not replaced? (substitution test; "<" is special) ---
set "OE=%OCTOP_ENV%"
if not "%OE:<=%"=="%OE%" (
  echo [ERROR] OCTOP_CONDA_ENV placeholder not replaced. Edit DEFAULT_ENV at top.
  exit /b 1
)

if not exist "%OCTOP_ENV%\Scripts\octop.exe" (
    echo [ERROR] octop.exe not found under "%OCTOP_ENV%\Scripts\".
    echo         Usage: %~nx0 [conda env dir]
    echo         e.g.   %~nx0 <OCTOP_CONDA_ENV>
    exit /b 1
)

echo Starting Octop ...
echo   Env      : %OCTOP_ENV%
echo   Dashboard: http://127.0.0.1:8088
echo   Data dir : %USERPROFILE%\.octop
echo.

"%OCTOP_ENV%\Scripts\octop.exe" run
