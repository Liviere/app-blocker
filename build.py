#!/usr/bin/env python3
"""
Build script for App Blocker using PyInstaller
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def clean_build_directories():
    """Clean previous build artifacts"""
    print("\n🧹 Cleaning build directories...")
    
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Removed: {dir_name}")
    
    # Clean .spec files
    for spec_file in Path(".").glob("*.spec"):
        spec_file.unlink()
        print(f"  Removed: {spec_file}")


def create_pyinstaller_specs():
    """Create PyInstaller specification files"""
    print("\n📝 Creating PyInstaller specifications...")
    
    # Main application spec
    main_spec = """# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('config.default.json', '.'),
    ],
    hiddenimports=['psutil'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='app-blocker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)
"""
    
    # GUI application spec
    gui_spec = """# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('config.default.json', '.'),
    ],
    hiddenimports=['psutil', 'tkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='app-blocker-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)
"""
    
    with open("main.spec", "w") as f:
        f.write(main_spec)
    
    with open("gui.spec", "w") as f:
        f.write(gui_spec)
    
    print("  Created: main.spec")
    print("  Created: gui.spec")


def build_executables():
    """Build executables using PyInstaller"""
    print("\n🔨 Building executables...")
    
    # Get Python executable path from environment
    python_exe = sys.executable
    pyinstaller_path = os.path.join(os.path.dirname(python_exe), "pyinstaller.exe")
    
    # Check if pyinstaller exists in the same directory as python
    if not os.path.exists(pyinstaller_path):
        # Try Scripts subdirectory (common in venv)
        pyinstaller_path = os.path.join(os.path.dirname(python_exe), "Scripts", "pyinstaller.exe")
    
    # Fallback to system pyinstaller if not found in venv
    if not os.path.exists(pyinstaller_path):
        pyinstaller_path = "pyinstaller"
    
    print(f"  Using PyInstaller: {pyinstaller_path}")
    
    # Build main application
    run_command(f'"{pyinstaller_path}" main.spec', "Building main application")
    
    # Build GUI application
    run_command(f'"{pyinstaller_path}" gui.spec', "Building GUI application")


def prepare_distribution():
    """Prepare distribution folder with all necessary files"""
    print("\n📦 Preparing distribution...")
    
    # Create distribution directory
    dist_dir = Path("dist/app-blocker")
    dist_dir.mkdir(exist_ok=True)
    
    # Copy executables
    shutil.copy2("dist/app-blocker.exe", dist_dir / "app-blocker.exe")
    shutil.copy2("dist/app-blocker-gui.exe", dist_dir / "app-blocker-gui.exe")
    
    # Copy configuration files
    if os.path.exists("config.default.json"):
        shutil.copy2("config.default.json", dist_dir / "config.default.json")
    
    # Copy documentation
    shutil.copy2("README.md", dist_dir / "README.md")
    
    # Create batch files for easy execution
    gui_bat = """@echo off
start "" "%~dp0app-blocker-gui.exe"
"""
    
    monitor_bat = """@echo off
"%~dp0app-blocker.exe"
pause
"""
    
    with open(dist_dir / "App Blocker GUI.bat", "w") as f:
        f.write(gui_bat)
    
    with open(dist_dir / "App Blocker Monitor.bat", "w") as f:
        f.write(monitor_bat)
    
    print(f"  Distribution prepared in: {dist_dir}")


def main():
    """Main build process"""
    print("🚀 Building App Blocker")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("main.py") or not os.path.exists("gui.py"):
        print("❌ Error: main.py or gui.py not found in current directory")
        sys.exit(1)
    
    # Install PyInstaller if not available
    try:
        import PyInstaller
    except ImportError:
        print("🔄 Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Build process
    clean_build_directories()
    create_pyinstaller_specs()
    build_executables()
    prepare_distribution()
    
    print("\n🎉 Build completed successfully!")
    print(f"📁 Distribution files are in: dist/app-blocker/")
    print("\nNext steps:")
    print("1. Test the executables in dist/app-blocker/")
    print("2. Run 'python setup_installer.py' to create Windows installer")


if __name__ == "__main__":
    main()
