@echo off
REM App Blocker - Windows helper script

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
pushd "%ROOT_DIR%" >nul

if "%1"=="gui" (
    echo Starting App Blocker GUI...
    poetry run python -m app.gui
) else if "%1"=="monitor" (
    echo Starting App Blocker monitoring...
    poetry run python -m app.main
) else if "%1"=="install" (
    echo Installing dependencies...
    poetry install
) else if "%1"=="format" (
    echo Formatting code with Black...
    poetry run black .
) else if "%1"=="lint" (
    echo Linting code with flake8...
    poetry run flake8 .
) else if "%1"=="test" (
    echo Running tests...
    poetry run pytest
) else (
    echo App Blocker Helper Script
    echo.
    echo Usage:
    echo   app.bat gui       - Start GUI
    echo   app.bat monitor   - Start monitoring
    echo   app.bat install   - Install dependencies
    echo   app.bat format    - Format code
    echo   app.bat lint      - Lint code
    echo   app.bat test      - Run tests
)

popd >nul
