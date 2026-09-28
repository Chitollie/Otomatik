; Otomatik Windows Installer
; Requires Inno Setup 6.x.
; Build dist\Otomatik.exe before compiling this installer.

#define MyAppName "Otomatik"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Otomatik"
#define MyAppExeName "Otomatik.exe"

[Setup]
AppId={{A7E8F4C2-6B9D-4B4C-9E3D-OTOMATIK1000}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Otomatik
DefaultGroupName=Otomatik
OutputDir=installer_output
OutputBaseFilename=Otomatik_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Files]
Source: "..\dist\Otomatik.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Otomatik"; Filename: "{app}\Otomatik.exe"
Name: "{autodesktop}\Otomatik"; Filename: "{app}\Otomatik.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Raccourcis :"

[Run]
Filename: "{app}\Otomatik.exe"; Description: "Lancer Otomatik"; Flags: nowait postinstall skipifsilent
