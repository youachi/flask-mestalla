@echo off
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual...
  %PY% -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: no se encontro Python. Instalalo desde https://www.python.org/downloads/ marcando "Add Python to PATH".
  pause
  exit /b 1
)
echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
echo Arrancando la web en http://localhost:5000 ...
".venv\Scripts\python.exe" app.py
