@echo off
setlocal EnableExtensions
set "DEST=C:\procesos python\Revisar metricas web\versiones\Stripe cargos ficticios"
set "SOURCE=%~dp0paquete"
if not exist "%SOURCE%\Stripe cargos ficticios.exe" (
  echo ERROR: Descomprime primero todo el archivo ZIP.
  echo Falta: %SOURCE%\Stripe cargos ficticios.exe
  pause
  exit /b 1
)
if not exist "%DEST%" mkdir "%DEST%" 2>nul
if not exist "%DEST%" (
  echo ERROR: No se pudo crear esta carpeta:
  echo %DEST%
  pause
  exit /b 1
)
xcopy "%SOURCE%\*" "%DEST%\" /E /I /Y /Q >nul
if errorlevel 1 (
  echo ERROR: La copia no se completo. No se modificaron otros proyectos.
  pause
  exit /b 1
)
echo.
echo Instalado en:
echo %DEST%
echo.
echo Abriendo Stripe cargos ficticios...
start "" "%DEST%\Stripe cargos ficticios.exe"
exit /b 0
