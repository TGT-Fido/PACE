Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
Name "PACE 7.0.0"
!ifndef OUTPUT_FILE
 !define OUTPUT_FILE "..\PACE-7.0.0-Setup.exe"
!endif
OutFile "${OUTPUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\PACE"
InstallDirRegKey HKCU "Software\PACE" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "Install PACE26 Version 7.0.0 with its own private Python runtime.$\r$\n$\r$\nNo separate Python installation is needed. Tailscale is optional.$\r$\n$\r$\nExit any running copy of PACE before continuing. Existing user data in the selected folder is preserved."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\runtime\pythonw.exe"
!define MUI_FINISHPAGE_RUN_PARAMETERS "$\"$INSTDIR\app\tray.pyw$\""
!define MUI_FINISHPAGE_RUN_TEXT "Open PACE"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Function .onInit
 ${IfNot} ${RunningX64}
  MessageBox MB_ICONSTOP "This package requires 64-bit Windows 10 or later."
  Abort
 ${EndIf}
 FindWindow $0 "PACETrayWindow"
 StrCmp $0 0 ready
 MessageBox MB_ICONSTOP "PACE is running. Exit PACE from its tray menu, then run Setup again."
 Abort
 ready:
FunctionEnd
Section "PACE"
 SetOutPath "$INSTDIR\app"
 File /r /x __pycache__ "..\app\*"
 SetOutPath "$INSTDIR\runtime"
 File /r "..\runtime\*"
 SetOutPath "$INSTDIR\defaults"
 File /r /x __pycache__ "..\defaults\*"
 SetOutPath "$INSTDIR\docs"
 File "..\docs\USER_GUIDE.md"
 File "..\docs\SAMPLE_FONT_LICENSE.txt"
 File "..\docs\WALLPAPER_MANIFEST.json"
 File "..\docs\V7_VALIDATION.md"
 SetOutPath "$INSTDIR\original-logo"
 File "..\original-logo\*"
 SetOutPath "$INSTDIR"
 File "..\README.md"
 File "..\THIRD_PARTY_NOTICES.md"
 File "..\START_PACE.cmd"
 File "..\TROUBLESHOOT_PACE.cmd"
 File "..\RECOVER_PACE.cmd"
 File "..\RECOVER_PACE.py"
 WriteRegStr HKCU "Software\PACE" "InstallDir" "$INSTDIR"
 WriteUninstaller "$INSTDIR\Uninstall.exe"
 CreateDirectory "$SMPROGRAMS\PACE"
 CreateShortcut "$SMPROGRAMS\PACE\PACE.lnk" "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\app\tray.pyw"' "$INSTDIR\app\pace.ico"
 CreateShortcut "$SMPROGRAMS\PACE\PACE folder.lnk" "$INSTDIR"
 CreateShortcut "$DESKTOP\PACE.lnk" "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\app\tray.pyw"' "$INSTDIR\app\pace.ico"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PACE" "DisplayName" "PACE26 - Version 7.0.0"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PACE" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PACE" "DisplayVersion" "7.0.0"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PACE" "InstallLocation" "$INSTDIR"
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PACE" "NoModify" 1
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PACE" "NoRepair" 1
SectionEnd
Function un.onInit
 FindWindow $0 "PACETrayWindow"
 StrCmp $0 0 ready
 MessageBox MB_ICONSTOP "Exit PACE from the tray before uninstalling."
 Abort
 ready:
FunctionEnd
Section "Uninstall"
 Delete "$DESKTOP\PACE.lnk"
 RMDir /r "$SMPROGRAMS\PACE"
 RMDir /r "$INSTDIR\app"
 RMDir /r "$INSTDIR\runtime"
 RMDir /r "$INSTDIR\defaults"
 RMDir /r "$INSTDIR\docs"
 RMDir /r "$INSTDIR\original-logo"
 Delete "$INSTDIR\START_PACE.cmd"
 Delete "$INSTDIR\TROUBLESHOOT_PACE.cmd"
 Delete "$INSTDIR\RECOVER_PACE.cmd"
 Delete "$INSTDIR\RECOVER_PACE.py"
 Delete "$INSTDIR\README.md"
 Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
 Delete "$INSTDIR\Uninstall.exe"
 RMDir "$INSTDIR"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PACE"
 DeleteRegKey HKCU "Software\PACE"
 MessageBox MB_OK "PACE was removed. Your data folder and any backups have been kept."
SectionEnd
