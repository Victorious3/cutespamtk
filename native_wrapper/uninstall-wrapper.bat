SETLOCAL
SET EXTENSION=moe.nightfall.booru

REG DELETE "HKCU\Software\Google\Chrome\NativeMessagingHosts\%EXTENSION%" /f
REG DELETE "HKCU\Software\Mozilla\NativeMessagingHosts\%EXTENSION%" /f