import os
import subprocess
import sys
from pathlib import Path


def create_inno_setup_script():
    print("Creating Inno Setup script...")
    
    version = "1.0.0"
    try:
        with open("pyproject.toml", "r") as f:
            for line in f:
                if line.startswith("version ="):
                    version = line.split('"')[1]
                    break
    except FileNotFoundError:
        pass
    
    inno_script = f"""[Setup]
AppId={{{{B7B5E4F2-1A2B-4C3D-8E9F-1234567890AB}}}}
AppName=App Blocker
AppVersion={version}
AppVerName=App Blocker {version}
AppPublisher=Liviere Studio
DefaultDirName={{autopf}}\\App Blocker
DefaultGroupName=App Blocker
AllowNoIcons=yes
OutputDir=dist\\installer
OutputBaseFilename=app-blocker-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: unchecked

[Files]
Source: "dist\\app-blocker\\app-blocker.exe"; DestDir: "{{app}}"; Flags: ignoreversion
Source: "dist\\app-blocker\\app-blocker-gui.exe"; DestDir: "{{app}}"; Flags: ignoreversion
Source: "dist\\app-blocker\\config.default.json"; DestDir: "{{app}}"; Flags: ignoreversion
Source: "dist\\app-blocker\\README.md"; DestDir: "{{app}}"; Flags: ignoreversion
Source: "dist\\app-blocker\\App Blocker GUI.bat"; DestDir: "{{app}}"; Flags: ignoreversion
Source: "dist\\app-blocker\\App Blocker Monitor.bat"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
Name: "{{group}}\\App Blocker"; Filename: "{{app}}\\app-blocker-gui.exe"
Name: "{{group}}\\App Blocker Monitor"; Filename: "{{app}}\\app-blocker.exe"
Name: "{{group}}\\{{cm:UninstallProgram,App Blocker}}"; Filename: "{{uninstallexe}}"
Name: "{{autodesktop}}\\App Blocker"; Filename: "{{app}}\\app-blocker-gui.exe"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\app-blocker-gui.exe"; Description: "{{cm:LaunchProgram,App Blocker}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not FileExists(ExpandConstant('{{app}}\\config.json')) then
    begin
      FileCopy(ExpandConstant('{{app}}\\config.default.json'), 
               ExpandConstant('{{app}}\\config.json'), False);
    end;
  end;
end;
"""
    
    with open("app-blocker.iss", "w", encoding="utf-8") as f:
        f.write(inno_script)
    
    print("Created: app-blocker.iss")


def check_inno_setup():
    print("Checking for Inno Setup...")
    
    inno_paths = [
        "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe",
        "C:\\Program Files\\Inno Setup 6\\ISCC.exe",
        "C:\\Program Files (x86)\\Inno Setup 5\\ISCC.exe",
        "C:\\Program Files\\Inno Setup 5\\ISCC.exe"
    ]
    
    for path in inno_paths:
        if os.path.exists(path):
            print(f"Found Inno Setup: {path}")
            return path
    
    print("Inno Setup not found")
    return None


def build_installer():
    print("Building installer...")
    
    inno_path = check_inno_setup()
    if not inno_path:
        print("Cannot build installer without Inno Setup")
        return False
    
    if not os.path.exists("dist/app-blocker"):
        print("Distribution files not found. Run 'python build.py' first.")
        return False
    
    Path("dist/installer").mkdir(parents=True, exist_ok=True)
    
    try:
        cmd = f'"{inno_path}" app-blocker.iss'
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print("Installer built successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Installer build failed: {e.stderr}")
        return False


def main():
    print("Setting up App Blocker Installer")
    print("=" * 50)
    
    create_inno_setup_script()
    
    if build_installer():
        print("\\nInstaller setup completed!")
        print("Installer file: dist/installer/app-blocker-setup.exe")
    else:
        print("\\nInstaller creation failed")


if __name__ == "__main__":
    main()
