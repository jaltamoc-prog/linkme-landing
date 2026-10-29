@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo.
echo STRIPE CARGOS FICTICIOS - MODO PYTHON
echo.
echo Esta alternativa evita el archivo EXE si Smart App Control lo bloquea.
echo Solo utiliza la carpeta donde esta instalado este proceso.
echo.
py -3 -c "import flask, requests, urllib3, bs4, reportlab" >nul 2>&1
if errorlevel 1 (
  echo Instalando dependencias Python para la prueba...
  py -3 -m pip install Flask==3.0.3 reportlab==4.2.5 beautifulsoup4==4.12.3 urllib3==2.2.3 requests==2.32.3
  if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias.
    pause
    exit /b 1
  )
)
py -3 "%~dp0stripe_cargos_ficticios_gui.py"
if errorlevel 1 (
  echo Se produjo un error. Lee el mensaje anterior.
  pause
  exit /b 1
)
exit /b 0
