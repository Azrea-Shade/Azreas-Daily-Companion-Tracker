[Setup]
AppName=Azrea''s Daily Companion Tracker
AppVersion=1.0.0
DefaultDirName={autopf}\AzreasDailyCompanionTracker
DefaultGroupName=Azrea''s Daily Companion Tracker
OutputDir=installer\dist
OutputBaseFilename=AzreasDailyCompanionTracker_Setup
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
SetupIconFile=artworkpp_icon.ico
WizardImageFile=artwork\installer_wizard_164x314.bmp
WizardSmallImageFile=artwork\installer_small_55x55.bmp
LicenseFile=
UsePreviousLanguage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; TODO: Update the Source path to your built Windows executable before building the installer.
; For example, if your build produces dist\Azrea.exe, point to it like below:
; Source: "dist\Azrea.exe"; DestDir: "{app}"; Flags: ignoreversion
; You can add additional runtime files, DLLs, data folders here.

[Icons]
Name: "{group}\Azrea''s Daily Companion Tracker"; Filename: "{app}\Azrea.exe"; WorkingDir: "{app}"; IconFilename: "{app}pp_icon.ico"; Check: FileExists('{app}\Azrea.exe')
Name: "{autodesktop}\Azrea''s Daily Companion Tracker"; Filename: "{app}\Azrea.exe"; Tasks: desktopicon; IconFilename: "{app}pp_icon.ico"; Check: FileExists('{app}\Azrea.exe')

[Tasks]
Name: desktopicon; Description: "Create a &Desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\Azrea.exe"; Description: "Launch Azrea''s Daily Companion Tracker"; Flags: nowait postinstall skipifsilent; Check: FileExists('{app}\Azrea.exe')

[InstallDelete]
; Ensure icon is copied to {app} if your app expects it alongside the exe

Source: "artworkpp_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
