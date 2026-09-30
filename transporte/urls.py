"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
MÓDULO: ENRUTAMIENTO DE LA APLICACIÓN (transporte/urls.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
================================================================================
Este archivo define el mapeo modular de URLs hacia las vistas de DRF,
cumpliendo con la matriz de endpoints requerida por la pauta de evaluación:
- Base / Footer: /api/info/
- Autenticación: /api/token/, /api/token/refresh/, /api/registro/
- Catálogo Público: /api/servicios/buscar/, /api/servicios/{id}/asientos/
- Rol Pasajero: /api/carro-pasajes/, /api/ventas/checkout/, /api/mis-boletos/
- Rol Administrador: /api/servicios/, /api/ventas/{id}/estado/
================================================================================
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    BaseFooterInfoView,
    CustomTokenObtainPairView,
    RegistroUsuarioView,
    ServiciosBuscarView,
    ServicioAsientosView,
    CarroPasajesView,
    CarroPasajesBulkView,
    CarroLimpiarAgotadosView,
    ItemCarroDeleteView,
    CheckoutView,
    MisBoletosView,
    ServiciosViewSet,
    CambioEstadoOrdenView,
    CiudadViewSet,
    BusViewSet,
    AsientoViewSet,
    RutaViewSet,
    EmpresaTransporteViewSet,
    BoletoEmbarqueView,
)

# Router para ViewSets de infraestructura y administración
router = DefaultRouter()
router.register(r"servicios", ServiciosViewSet, basename="servicio-admin")
router.register(r"empresas", EmpresaTransporteViewSet, basename="empresa")
router.register(r"ciudades", CiudadViewSet, basename="ciudad")
router.register(r"buses", BusViewSet, basename="bus")
router.register(r"asientos", AsientoViewSet, basename="asiento")
router.register(r"rutas", RutaViewSet, basename="ruta")

urlpatterns = [
    # --------------------------------------------------------------------------
    # 1. PIE DE PÁGINA Y DATOS BASE DEL ALUMNO (EVA-2)
    # --------------------------------------------------------------------------
    path("info/", BaseFooterInfoView.as_view(), name="api-info-footer"),

    # --------------------------------------------------------------------------
    # 2. AUTENTICACIÓN JWT CON ROLES Y REGISTRO
    # --------------------------------------------------------------------------
    path("token/", CustomTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("registro/", RegistroUsuarioView.as_view(), name="registro-pasajero"),

    # --------------------------------------------------------------------------
    # 3. CATÁLOGO Y BÚSQUEDA PÚBLICA DE SERVICIOS
    # --------------------------------------------------------------------------
    # Endpoint explícito requerido: GET /api/servicios/buscar/
    path("servicios/buscar/", ServiciosBuscarView.as_view(), name="servicios-buscar"),
    # Endpoint de disponibilidad de asientos: GET /api/servicios/{id}/asientos/
    path("servicios/<int:id>/asientos/", ServicioAsientosView.as_view(), name="servicio-asientos"),

    # --------------------------------------------------------------------------
    # 4. PASAJERO: CARRO PERSISTENTE, CHECKOUT ATÓMICO Y BOLETOS
    # --------------------------------------------------------------------------
    # Carro de pasajes persistente (GET: ver carro, POST: agregar asiento con pasajero/rut)
    path("carro-pasajes/", CarroPasajesView.as_view(), name="carro-pasajes"),
    # Agregar múltiples asientos en lote: POST /api/carro-pasajes/bulk/
    path("carro-pasajes/bulk/", CarroPasajesBulkView.as_view(), name="carro-pasajes-bulk"),
    # Limpiar asientos agotados/comprados por otros: POST/DELETE /api/carro-pasajes/limpiar-agotados/
    path("carro-pasajes/limpiar-agotados/", CarroLimpiarAgotadosView.as_view(), name="carro-limpiar-agotados"),
    # Quitar ítem del carro: DELETE /api/carro-pasajes/{item_id}/
    path("carro-pasajes/<int:pk>/", ItemCarroDeleteView.as_view(), name="carro-pasajes-delete"),

    # Checkout transaccional atómico: POST /api/ventas/checkout/
    path("ventas/checkout/", CheckoutView.as_view(), name="ventas-checkout"),

    # Historial de pasajes comprados con UUID: GET /api/mis-boletos/
    path("mis-boletos/", MisBoletosView.as_view(), name="mis-boletos"),

    # --------------------------------------------------------------------------
    # 5. ADMINISTRADOR DE FLOTA: CAMBIO DE ESTADO Y REVERSIÓN DE INVENTARIO
    # --------------------------------------------------------------------------
    # Cambio administrativo de estado de orden: PATCH /api/ventas/{id}/estado/
    path("ventas/<int:id>/estado/", CambioEstadoOrdenView.as_view(), name="orden-cambio-estado"),
    # Control de embarque del pasajero en boleto: PATCH /api/boletos/{uuid}/embarque/
    path("boletos/<uuid:codigo_uuid>/embarque/", BoletoEmbarqueView.as_view(), name="boleto-embarque"),

    # --------------------------------------------------------------------------
    # 6. ROUTER PARA CRUDs (SERVICIOS, BUSES, RUTAS, CIUDADES)
    # --------------------------------------------------------------------------
    path("", include(router.urls)),
]
