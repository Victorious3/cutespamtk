

:: Change HKCU to HKLM if you want to install globally.
:: %~dp0 is the directory containing this bat script and ends with a backslash.

SETLOCAL
SET EXTENSION=moe.nightfall.booru

REG ADD "HKCU\Software\Google\Chrome\NativeMessagingHosts\%EXTENSION%" /ve /t REG_SZ /d "%~dp0chrome\%EXTENSION%.json" /f
:: And Firefox
REG ADD "HKCU\Software\Mozilla\NativeMessagingHosts\%EXTENSION%" /ve /t REG_SZ /d "%~dp0firefox\%EXTENSION%.json" /f
