# ==============================================================================
# Script de Inicio Rápido en PowerShell - Sistema de Buses Chile (EVA-2)
# ==============================================================================
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "   INICIANDO SERVIDOR BACKEND - BUSES CHILE (EVALUACION EVA-2)" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Cyan

Set-Location $PSScriptRoot

Write-Host "`n[1/3] Aplicando migraciones de base de datos..." -ForegroundColor Yellow
python manage.py migrate --noinput

Write-Host "`n[2/3] Verificando datos iniciales (usuarios, rutas, buses)..." -ForegroundColor Yellow
python manage.py poblar_datos

Write-Host "`n[3/3] Iniciando servidor Django REST Framework..." -ForegroundColor Green
Write-Host "-> Vista Base / Datos Alumno: http://127.0.0.1:8000/" -ForegroundColor White
Write-Host "-> Documentacion Swagger API: http://127.0.0.1:8000/api/docs/" -ForegroundColor White
Write-Host "-> Panel de Administracion:   http://127.0.0.1:8000/admin/`n" -ForegroundColor White

python manage.py runserver 127.0.0.1:8000
