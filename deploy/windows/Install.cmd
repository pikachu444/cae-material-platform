@echo off
setlocal EnableExtensions DisableDelayedExpansion
call :verify "%~dp0bundle-manifest.json" "__BUNDLE_MANIFEST_SHA256__"
if errorlevel 1 exit /b %ERRORLEVEL%
call :verify "%~dp0payload.zip" "__PAYLOAD_ARCHIVE_SHA256__"
if errorlevel 1 exit /b %ERRORLEVEL%
where tar.exe >nul 2>&1
if errorlevel 1 (
  echo CMP installer error: Windows tar.exe is required to open the verified payload 1>&2
  exit /b 2
)
set "CMP_BOOTSTRAP=%TEMP%\CMP-Install-%RANDOM%-%RANDOM%"
if exist "%CMP_BOOTSTRAP%" (
  echo CMP installer error: temporary bootstrap path already exists: %CMP_BOOTSTRAP% 1>&2
  exit /b 2
)
mkdir "%CMP_BOOTSTRAP%"
if errorlevel 1 exit /b 2
tar.exe -xf "%~dp0payload.zip" -C "%CMP_BOOTSTRAP%"
if errorlevel 1 (
  rmdir /s /q "%CMP_BOOTSTRAP%"
  echo CMP installer error: verified payload extraction failed 1>&2
  exit /b 2
)
copy /y "%~dp0bundle-manifest.json" "%CMP_BOOTSTRAP%\bundle-manifest.json" >nul
if errorlevel 1 (
  rmdir /s /q "%CMP_BOOTSTRAP%"
  exit /b 2
)
"%CMP_BOOTSTRAP%\payload\python\python.exe" -m cmp.tools.windows_installer install --bundle-root "%CMP_BOOTSTRAP%" --expected-manifest-sha256 "__BUNDLE_MANIFEST_SHA256__" %*
set "CMP_INSTALL_EXIT=%ERRORLEVEL%"
rmdir /s /q "%CMP_BOOTSTRAP%"
exit /b %CMP_INSTALL_EXIT%

:verify
if not exist "%~1" (
  echo CMP installer error: verified bundle file is missing: %~1 1>&2
  exit /b 2
)
set "CMP_ACTUAL_SHA256="
for /f "tokens=*" %%H in ('certutil -hashfile "%~1" SHA256 ^| findstr /r /i "^[0-9a-f][0-9a-f]*$"') do set "CMP_ACTUAL_SHA256=%%H"
if not defined CMP_ACTUAL_SHA256 (
  echo CMP installer error: certutil could not verify: %~1 1>&2
  exit /b 2
)
if /i not "%CMP_ACTUAL_SHA256%"=="%~2" (
  echo CMP installer error: pre-execution checksum mismatch: %~1 1>&2
  exit /b 2
)
exit /b 0
