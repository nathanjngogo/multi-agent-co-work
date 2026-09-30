@echo off
REM ============================================================================
REM  Plan C catalog - page-order-engine driven build (MARS-11 phase A)
REM
REM  Usage (run from this directory):
REM      build.cmd                     build the full 32P catalog (both variants)
REM      build.cmd --samples           build 1-2 sample pages per page type
REM      build.cmd A7 CR208 P11        build specific M2 pages only (models from v6)
REM      build.cmd --variant email     build the email variant only
REM      build.cmd --prepare-fonts     regenerate static font instances only
REM
REM  Output: output\print\*.pdf   print   303x216 mm (A4 landscape + 3 mm bleed)
REM          output\email\*.pdf   email   297x210 mm (trim size, no bleed)
REM          output\_build.json            build manifest for this run
REM          output\_selfcheck.json        pre-delivery self-check report
REM
REM  NOTE: this file is intentionally ASCII-only. cmd.exe parses .cmd files using
REM  the OEM code page, so non-ASCII text here can corrupt line parsing.
REM  Chinese documentation lives in README.md.
REM ============================================================================
setlocal

set "HERE=%~dp0"
pushd "%HERE%"

REM ---- 1. dependencies (installed into vendor\ on first run) ------------------
if not exist "vendor\reportlab" (
    echo [1/3] installing dependencies into vendor\ ...
    python -m pip install --target vendor --no-cache-dir reportlab pymupdf fonttools pillow
    if errorlevel 1 goto :fail
) else (
    echo [1/3] dependencies ready ^(vendor\^)
)

REM ---- 2. static font instances (Source Han Sans SC / Inter Tight / Bahnschrift)
if not exist "fonts\static\NotoSansSC-SemiBold.ttf" (
    echo [2/3] generating static font instances ...
    python catalog\build.py --prepare-fonts
    if errorlevel 1 goto :fail
) else (
    echo [2/3] fonts ready ^(fonts\static\^)
)

REM ---- 3. build + self-check --------------------------------------------------
echo [3/3] building ...
if "%~1"=="" (
    python catalog\build.py
) else (
    python catalog\build.py %*
)
if errorlevel 1 goto :fail

echo.
echo Done. Output directory: %HERE%output\  (print\ + email\)
popd
endlocal
exit /b 0

:fail
echo.
echo BUILD FAILED - see the messages above.
popd
endlocal
exit /b 1
