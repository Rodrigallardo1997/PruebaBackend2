@echo off
title Sistema de Reservas de Pasajes de Buses - EVA-2
color 0B
echo ==============================================================================
echo   INICIANDO SERVIDOR BACKEND - BUSES CHILE (EVALUACION EVA-2)
echo ==============================================================================
echo.

cd /d "%~dp0"

echo [1/3] Verificando dependencias y migraciones...
python manage.py migrate --noinput

echo [2/3] Verificando datos iniciales...
python manage.py poblar_datos

echo [3/3] Iniciando servidor Django en http://127.0.0.1:8000/ ...
echo.
echo Presiona Ctrl + C en esta ventana para detener el servidor.
echo.
python manage.py runserver 127.0.0.1:8000
pause
