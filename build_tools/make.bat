@echo off
REM App Blocker Build and Distribution Script

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
pushd "%ROOT_DIR%" >nul

echo 🚀 App Blocker Build System
echo ================================

if "%1"=="clean" goto clean
if "%1"=="test" goto test
if "%1"=="build" goto build
if "%1"=="installer" goto installer
if "%1"=="all" goto all
if "%1"=="help" goto help
goto help

:clean
echo 🧹 Cleaning build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec
if exist __pycache__ rmdir /s /q __pycache__
if exist tests\__pycache__ rmdir /s /q tests\__pycache__
echo ✅ Clean completed
goto :eof

:test
echo 🧪 Running tests...
poetry run pytest -v
if %errorlevel% neq 0 (
    echo ❌ Tests failed
    exit /b 1
)
echo ✅ Tests passed
goto :eof

:build
echo 🔨 Building executables...
poetry run python build_tools\build.py
if %errorlevel% neq 0 (
    echo ❌ Build failed
    exit /b 1
)
echo ✅ Build completed
goto :eof

:installer
echo 📦 Creating installer...
poetry run python build_tools\setup_installer.py
if %errorlevel% neq 0 (
    echo ❌ Installer creation failed
    exit /b 1
)
echo ✅ Installer created
goto :eof

:all
echo 🚀 Running full build process...
call :clean
call :test
if %errorlevel% neq 0 exit /b 1
call :build
if %errorlevel% neq 0 exit /b 1
call :installer
if %errorlevel% neq 0 exit /b 1
echo 🎉 Full build completed successfully!
echo 📁 Find your installer at: dist\installer\app-blocker-setup.exe
goto :eof

:help
echo Available commands:
echo   make.bat clean     - Clean build artifacts
echo   make.bat test      - Run tests
echo   make.bat build     - Build executables
echo   make.bat installer - Create installer
echo   make.bat all       - Run complete build process
echo   make.bat help      - Show this help
goto end

:end
popd >nul
