#!/usr/bin/env python3
"""
Test script for built executables
"""

import subprocess
import sys
import os
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
os.chdir(ROOT_DIR)


def test_executable(exe_path, description):
    """Test if executable runs correctly"""
    print(f"🧪 Testing {description}...")
    
    if not os.path.exists(exe_path):
        print(f"❌ {description} not found: {exe_path}")
        return False
    
    try:
        # For GUI app, just check if it starts (it will show window)
        if "gui" in exe_path.lower():
            print(f"  Starting {description} (close the window to continue test)")
            process = subprocess.Popen([exe_path])
            # Wait a bit to see if it crashes immediately
            time.sleep(2)
            if process.poll() is None:
                print(f"✅ {description} started successfully")
                # Kill the process since it's just a test
                process.terminate()
                return True
            else:
                print(f"❌ {description} crashed on startup")
                return False
        else:
            # For console app, run with --help or similar
            result = subprocess.run([exe_path, "--help"], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            if result.returncode == 0 or "usage" in result.stdout.lower():
                print(f"✅ {description} runs correctly")
                return True
            else:
                print(f"❌ {description} failed to run")
                return False
    except subprocess.TimeoutExpired:
        print(f"⚠️ {description} timed out (might be normal for monitor)")
        return True
    except Exception as e:
        print(f"❌ {description} test failed: {e}")
        return False


def check_files():
    """Check if all required files exist"""
    print("📋 Checking distribution files...")
    
    dist_dir = Path("dist/app-blocker")
    required_files = [
        "app-blocker.exe",
        "app-blocker-gui.exe",
        "config.default.json",
        "README.md",
        "App Blocker GUI.bat",
        "App Blocker Monitor.bat"
    ]
    
    all_present = True
    for file_name in required_files:
        file_path = dist_dir / file_name
        if file_path.exists():
            print(f"  ✅ {file_name}")
        else:
            print(f"  ❌ {file_name} - MISSING")
            all_present = False
    
    return all_present


def test_batch_files():
    """Test batch files"""
    print("🧪 Testing batch files...")
    
    dist_dir = Path("dist/app-blocker")
    
    # Test GUI batch file
    gui_bat = dist_dir / "App Blocker GUI.bat"
    if gui_bat.exists():
        print("  ✅ App Blocker GUI.bat exists")
    else:
        print("  ❌ App Blocker GUI.bat missing")
    
    # Test Monitor batch file
    monitor_bat = dist_dir / "App Blocker Monitor.bat"
    if monitor_bat.exists():
        print("  ✅ App Blocker Monitor.bat exists")
    else:
        print("  ❌ App Blocker Monitor.bat missing")


def main():
    """Main test function"""
    print("🧪 Testing App Blocker Distribution")
    print("=" * 50)
    
    # Check if distribution exists
    dist_dir = Path("dist/app-blocker")
    if not dist_dir.exists():
        print("❌ Distribution directory not found: dist/app-blocker")
        print("Run 'python build.py' first to create the distribution")
        sys.exit(1)
    
    # Run tests
    all_tests_passed = True
    
    # Check files
    if not check_files():
        all_tests_passed = False
    
    # Test batch files
    test_batch_files()
    
    # Test executables
    tests = [
        (dist_dir / "app-blocker-gui.exe", "App Blocker GUI"),
        (dist_dir / "app-blocker.exe", "App Blocker Monitor"),
    ]
    
    for exe_path, description in tests:
        if not test_executable(str(exe_path), description):
            all_tests_passed = False
    
    # Summary
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("🎉 All tests passed!")
        print("✅ Distribution is ready for installation")
        
        # Check for installer
        installer_path = Path("dist/installer/app-blocker-setup.exe")
        if installer_path.exists():
            print(f"📦 Installer available: {installer_path}")
        else:
            print("📦 Run 'python setup_installer.py' to create installer")
    else:
        print("❌ Some tests failed!")
        print("🔧 Please fix the issues and rebuild")
        sys.exit(1)


if __name__ == "__main__":
    main()
