[Setup]
AppName=Daily Companion
AppVersion=1.0.0
DefaultDirName={pf}\DailyCompanion
DefaultGroupName=Daily Companion
OutputDir=dist
OutputBaseFilename=DailyCompanionInstaller
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\DailyCompanion.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Daily Companion"; Filename: "{app}\DailyCompanion.exe"
Name: "{commondesktop}\Daily Companion"; Filename: "{app}\DailyCompanion.exe"

[Run]
Filename: "{app}\DailyCompanion.exe"; Description: "Launch Daily Companion"; Flags: nowait postinstall skipifsilent
