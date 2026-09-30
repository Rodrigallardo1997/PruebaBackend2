"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
MÓDULO: ENRUTADOR PRINCIPAL DEL PROYECTO (interurban_bus_system/urls.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
================================================================================
Configura las rutas principales del sistema:
1. Panel de Administración de Django en '/admin/'.
2. Documentación OpenAPI 3.0 interactiva (Swagger UI) en '/api/docs/'.
3. Esquema OpenAPI crudo en '/api/schema/'.
4. Documentación alternativa ReDoc en '/api/redoc/'.
5. Endpoints de la API de transporte en '/api/'.
6. Vista base con los datos del alumno (nombre, sección, año 2026) en la raíz '/'.
================================================================================
"""

from django.contrib import admin
from django.urls import path, re_path, include
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from transporte.views import BaseFooterInfoView, FrontendAppView

urlpatterns = [
    # Vista base con datos del estudiante y pie de página en la raíz del servidor
    path("", BaseFooterInfoView.as_view(), name="root-footer-base"),

    # Aplicación Frontend interactiva SPA conectada al Backend
    path("app/", FrontendAppView.as_view(), name="frontend-app"),

    # Panel administrativo de Django
    path("admin/", admin.site.urls),

    # Documentación interactiva Swagger / OpenAPI 3.0 requerida en /api/docs/
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Endpoints de negocio del sistema de buses interurbanos
    path("api/", include("transporte.urls")),

    # Redirección comodín (Catch-all): Cualquier URL no reconocida redirige automáticamente a /app/
    re_path(r"^.*$", RedirectView.as_view(url="/app/", permanent=False)),
]
