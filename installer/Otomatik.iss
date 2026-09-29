; Otomatik - Windows installer (Inno Setup 6.3 or later)
;
; 1. Run build.bat at the project root   -> creates dist\Otomatik.exe
; 2. Open this file in Inno Setup and press Compile (Ctrl+F9)
;    -> creates installer\installer_output\Otomatik_Setup_<version>.exe
;
; The EXE already contains every Python dependency (PySide6, OpenCV, ...),
; so nothing has to be pip-installed on the target PC. The only external
; requirement is Tesseract OCR (Compteur de peche): the installer downloads
; and installs it when it is missing, and ships the French language data.

#if VER < EncodeVer(6, 3, 0)
  #error Inno Setup 6.3 or later is required.
#endif

#define MyAppName "Otomatik"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Chitollie"
#define MyAppURL "https://github.com/Chitollie/Otomatik"
#define MyAppExeName "Otomatik.exe"

#define TesseractUrl "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
#define TesseractSha256 "c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9"

[Setup]
AppId={{6F37FA3B-FC90-49C7-BCFE-CACAEDAA1465}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=Otomatik_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#if FileExists(CompilerPath + "Languages\French.isl")
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "Creer un raccourci sur le bureau"; GroupDescription: "Raccourcis :"
Name: "tesseract"; Description: "Installer Tesseract OCR (necessaire au Compteur de peche, environ 50 Mo a telecharger)"; GroupDescription: "Composants :"; Check: not TesseractInstalled

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\tessdata\fra.traineddata"; DestDir: "{app}\tessdata"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer Otomatik"; Flags: nowait postinstall skipifsilent

[Code]
var
  DownloadPage: TDownloadWizardPage;
  TesseractSetupPath: String;

function TesseractInstalled: Boolean;
var
  InstallDir: String;
begin
  Result :=
    FileExists(ExpandConstant('{commonpf64}\Tesseract-OCR\tesseract.exe')) or
    FileExists(ExpandConstant('{commonpf32}\Tesseract-OCR\tesseract.exe'));

  if (not Result) and RegQueryStringValue(HKLM64, 'SOFTWARE\Tesseract-OCR', 'InstallDir', InstallDir) then
    Result := FileExists(AddBackslash(InstallDir) + 'tesseract.exe');
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if (CurPageID = wpReady) and WizardIsTaskSelected('tesseract') then
  begin
    TesseractSetupPath := '';
    DownloadPage.Clear;
    DownloadPage.Add('{#TesseractUrl}', 'tesseract-setup.exe', '{#TesseractSha256}');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        TesseractSetupPath := ExpandConstant('{tmp}\tesseract-setup.exe');
      except
        if not DownloadPage.AbortedByUser then
          SuppressibleMsgBox(
            AddPeriod(GetExceptionMessage) + #13#10#13#10 +
            'Otomatik sera installe sans Tesseract. Tu pourras l''installer plus tard : ' +
            'https://github.com/UB-Mannheim/tesseract/wiki',
            mbError, MB_OK, IDOK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and (TesseractSetupPath <> '') then
  begin
    WizardForm.StatusLabel.Caption := 'Installation de Tesseract OCR...';
    if not ShellExec('runas', TesseractSetupPath, '/S', '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then
      SuppressibleMsgBox(
        'Tesseract OCR n''a pas pu etre installe (code ' + IntToStr(ResultCode) + ').' + #13#10 +
        'Otomatik fonctionne, mais le Compteur de peche a besoin de Tesseract.',
        mbError, MB_OK, IDOK);
  end;
end;
