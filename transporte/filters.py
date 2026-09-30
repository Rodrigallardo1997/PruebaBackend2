"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
MÓDULO: FILTRADO DECLARATIVO CON DJANGO-FILTER (filters.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
================================================================================
Este archivo implementa el conjunto de filtros para el catálogo de servicios
e itinerarios, dando cumplimiento a los requerimientos de la pauta:
- Endpoint: GET /api/servicios/buscar/
- Filtros por ciudad origen (por ID o por texto parcial).
- Filtros por ciudad destino (por ID o por texto parcial).
- Filtro por fecha de salida específica (YYYY-MM-DD).
- Filtros por rango de fechas (desde / hasta).
- Filtro por tarifa máxima.
================================================================================
"""

import django_filters
from .models import Servicio


class ServicioFilter(django_filters.FilterSet):
    """
    Filtro declarativo avanzado para la búsqueda de itinerarios interurbanos.
    Permite a los pasajeros encontrar buses según su trayecto y fecha deseada.
    """
    # Filtrado por ID o nombre de la ciudad de origen
    origen = django_filters.NumberFilter(
        field_name="ruta__origen__id",
        help_text="ID de la ciudad de origen (ej: 1).",
    )
    origen_nombre = django_filters.CharFilter(
        field_name="ruta__origen__nombre",
        lookup_expr="icontains",
        help_text="Nombre parcial o completo de la ciudad origen (ej: 'Santiago').",
    )

    # Filtrado por ID o nombre de la ciudad de destino
    destino = django_filters.NumberFilter(
        field_name="ruta__destino__id",
        help_text="ID de la ciudad de destino (ej: 2).",
    )
    destino_nombre = django_filters.CharFilter(
        field_name="ruta__destino__nombre",
        lookup_expr="icontains",
        help_text="Nombre parcial o completo de la ciudad destino (ej: 'Valparaíso').",
    )

    # Filtrado por fecha exacta de salida (formato YYYY-MM-DD)
    fecha_salida = django_filters.DateFilter(
        field_name="fecha_hora_salida__date",
        help_text="Fecha de salida en formato YYYY-MM-DD (ej: '2026-10-15').",
    )

    # Rango de fechas (desde / hasta)
    fecha_desde = django_filters.DateTimeFilter(
        field_name="fecha_hora_salida",
        lookup_expr="gte",
        help_text="Fecha y hora mínima de salida (ISO 8601).",
    )
    fecha_hasta = django_filters.DateTimeFilter(
        field_name="fecha_hora_salida",
        lookup_expr="lte",
        help_text="Fecha y hora máxima de salida (ISO 8601).",
    )

    # Filtrado por tarifa máxima
    precio_max = django_filters.NumberFilter(
        field_name="precio_semicama",
        lookup_expr="lte",
        help_text="Tarifa base semicama máxima que el pasajero está dispuesto a pagar.",
    )

    # Filtrado por estado del servicio
    estado = django_filters.CharFilter(
        field_name="estado",
        lookup_expr="iexact",
        help_text="Estado del servicio ('PROGRAMADO', 'EN_RUTA', etc.).",
    )

    # Filtrado por Empresa de Transporte / Tenant (Multi-Tenancy)
    empresa = django_filters.NumberFilter(
        field_name="empresa__id",
        help_text="ID de la Empresa de Transporte / Tenant (ej: 1).",
    )
    empresa_slug = django_filters.CharFilter(
        field_name="empresa__slug",
        lookup_expr="iexact",
        help_text="Identificador único del Tenant (ej: 'turbus', 'pullman').",
    )

    class Meta:
        model = Servicio
        fields = [
            "origen",
            "origen_nombre",
            "destino",
            "destino_nombre",
            "fecha_salida",
            "fecha_desde",
            "fecha_hasta",
            "precio_max",
            "estado",
            "empresa",
            "empresa_slug",
        ]
