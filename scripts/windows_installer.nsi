Unicode true
!include "MUI2.nsh"

Name "Douyinhehe Pro Studio"
OutFile "DouyinhehePro-Setup-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\DouyinhehePro"
RequestExecutionLevel user
SetCompressor zlib
SetCompressorDictSize 8
ShowInstDetails show
ShowUninstDetails show

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Vietnamese"
!insertmacro MUI_LANGUAGE "English"

Section "Douyinhehe Pro" SecMain
  SetOutPath "$INSTDIR"
  File /r "dist\DouyinhehePro\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Douyinhehe Pro"
  CreateShortCut "$SMPROGRAMS\Douyinhehe Pro\Douyinhehe Studio.lnk" "$INSTDIR\DouyinhehePro.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DouyinhehePro" "DisplayName" "Douyinhehe Pro Studio"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DouyinhehePro" "DisplayVersion" "4.0.0-rc1"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DouyinhehePro" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DouyinhehePro" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DouyinhehePro" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DouyinhehePro" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\Douyinhehe Pro\Douyinhehe Studio.lnk"
  RMDir "$SMPROGRAMS\Douyinhehe Pro"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DouyinhehePro"
  ; Only the application installation folder is removed. Database, saved
  ; projects, downloaded videos, account keys and caches in user_data_dir()
  ; are deliberately kept intact across upgrades and uninstall.
  RMDir /r "$INSTDIR"
SectionEnd
