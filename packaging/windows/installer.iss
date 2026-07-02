; DVtools - Inno Setup installer script
; --------------------------------------
; Packages the Nuitka standalone build (dvtools_windows.dist/) into a
; single-file Windows installer. This does NOT include ffmpeg -- the
; app downloads it on first run if missing (see offer_ffmpeg_download()
; in dvtools_core.py). That keeps this installer small.
;
; Build with: iscc packaging\windows\installer.iss
; (Inno Setup Compiler -- https://jrsoftware.org/isinfo.php, or
; `choco install innosetup` in CI)
;
; Expects the Nuitka standalone output at build\dvtools_windows.dist\
; relative to the repo root (see .github/workflows/build.yml).

#define MyAppName "DVtools"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "DVtools"
#define MyAppExeName "dvtools_windows.exe"
#define SourceDist "..\..\build\dvtools_windows.dist"

[Setup]
AppId={{8F1B6C1E-6D2A-4B7B-9A3E-DV7001TOOLS}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=DVtools-Setup-Windows
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; No admin rights required: installs per-user by default, so it also
; works for users without local-admin permissions on shared machines.
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\icons\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Pulls in the whole Nuitka standalone folder (app + Python runtime +
; fonts + plugins), keeping the internal folder structure intact so
; BASE_PATH-relative lookups (fonts/, plugins/) keep working exactly
; like they do when running the .py files directly.
Source: "{#SourceDist}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
