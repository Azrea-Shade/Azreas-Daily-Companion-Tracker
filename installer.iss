[Setup]
AppName=Daily Companion
AppVersion=1.0.0
DefaultDirName={pf}\DailyCompanion
DefaultGroupName=Daily Companion
OutputDir=dist
OutputBaseFilename=DailyCompanionInstaller
Compression=lzma
SolidCompression=yes

[Tasks]
Name: "autorun"; Description: "Start Daily Companion when I sign in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "dist\DailyCompanion.exe"; DestDir: "{app}"; Flags: ignoreversion
; VC++ runtime downloaded by CI
Source: "build\prereq\vcredist_x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Registry]
; Add HKCU Run key only if user checked Startup
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DailyCompanion"; ValueData: """{app}\DailyCompanion.exe"""; Tasks: autorun

[Run]
; Install VC++ redist silently (skip if not found)
Filename: "{tmp}\vcredist_x64.exe"; Parameters: "/quiet /norestart"; Flags: waituntilterminated skipifdoesntexist
; Launch app after install
Filename: "{app}\DailyCompanion.exe"; Description: "Launch Daily Companion"; Flags: nowait postinstall skipifsilent

; -- Added by automation: Startup task
[Tasks]
Name: "startupicon"; Description: "Start at Windows login"; GroupDescription: "Startup:"; Flags: unchecked

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "AzreaCompanion"; \
    ValueData: """{app}\AzreaCompanion.exe"""; Tasks: startupicon
