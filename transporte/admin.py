"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
MÓDULO: ADMINISTRACIÓN DE DJANGO (transporte/admin.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
================================================================================
Configura el panel de administración de Django para la gestión visual de:
- Usuarios y asignación de Roles ('PASAJERO', 'ADMIN_FLOTA').
- Ciudades y Terminales.
- Buses y Asientos.
- Rutas e Itinerarios (Servicios).
- Carros persistentes e Ítems.
- Órdenes de Compra y Boletos con UUID.
================================================================================
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Usuario,
    EmpresaTransporte,
    Ciudad,
    Bus,
    Asiento,
    Ruta,
    Servicio,
    CarroPasajes,
    ItemCarro,
    OrdenCompra,
    Boleto,
)


@admin.register(EmpresaTransporte)
class EmpresaTransporteAdmin(admin.ModelAdmin):
    list_display = ["nombre", "rut", "slug", "activo", "creado_en"]
    search_fields = ["nombre", "rut", "slug"]
    list_filter = ["activo"]
    prepopulated_fields = {"slug": ("nombre",)}


@admin.register(Usuario)
class UsuarioAdminCustom(UserAdmin):
    """Administración personalizada del modelo de Usuario con roles y Tenant."""
    list_display = ["username", "email", "rol", "empresa", "first_name", "last_name", "rut", "is_staff"]
    list_filter = ["rol", "empresa", "is_staff", "is_active"]
    search_fields = ["username", "email", "rut", "first_name", "last_name"]
    fieldsets = UserAdmin.fieldsets + (
        ("Roles y Multi-Tenancy", {"fields": ("rol", "empresa", "rut", "telefono")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Roles y Multi-Tenancy", {"fields": ("rol", "empresa", "rut", "telefono")}),
    )


@admin.register(Ciudad)
class CiudadAdmin(admin.ModelAdmin):
    list_display = ["nombre", "terminal", "region"]
    search_fields = ["nombre", "terminal", "region"]
    list_filter = ["region"]


class AsientoInline(admin.TabularInline):
    model = Asiento
    extra = 0
    fields = ["numero", "tipo", "piso"]


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ["patente", "modelo", "marca", "capacidad_total", "activo"]
    search_fields = ["patente", "modelo", "marca"]
    list_filter = ["activo", "marca"]
    inlines = [AsientoInline]


@admin.register(Asiento)
class AsientoAdmin(admin.ModelAdmin):
    list_display = ["bus", "numero", "tipo", "piso"]
    list_filter = ["tipo", "piso", "bus"]
    search_fields = ["bus__patente", "numero"]


@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display = ["__str__", "origen", "destino", "distancia_km", "duracion_estimada_minutos"]
    search_fields = ["origen__nombre", "destino__nombre"]
    list_filter = ["origen", "destino"]


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "ruta",
        "bus",
        "fecha_hora_salida",
        "precio_semicama",
        "precio_cama",
        "estado",
    ]
    list_filter = ["estado", "ruta", "bus", "fecha_hora_salida"]
    search_fields = ["ruta__origen__nombre", "ruta__destino__nombre", "bus__patente"]


class ItemCarroInline(admin.TabularInline):
    model = ItemCarro
    extra = 0
    fields = ["servicio", "asiento", "nombre_pasajero", "rut_pasajero", "precio_unitario"]


@admin.register(CarroPasajes)
class CarroPasajesAdmin(admin.ModelAdmin):
    list_display = ["usuario", "total", "creado_en", "actualizado_en"]
    search_fields = ["usuario__username"]
    inlines = [ItemCarroInline]


class BoletoInline(admin.TabularInline):
    model = Boleto
    extra = 0
    readonly_fields = ["codigo_uuid", "fecha_emision"]
    fields = ["codigo_uuid", "servicio", "asiento", "nombre_pasajero", "rut_pasajero", "precio_pagado", "activo"]


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ["id", "usuario", "total", "estado", "fecha_creacion"]
    list_filter = ["estado", "fecha_creacion"]
    search_fields = ["usuario__username", "id"]
    inlines = [BoletoInline]


@admin.register(Boleto)
class BoletoAdmin(admin.ModelAdmin):
    list_display = [
        "codigo_uuid",
        "orden",
        "servicio",
        "asiento",
        "nombre_pasajero",
        "rut_pasajero",
        "precio_pagado",
        "activo",
        "fecha_emision",
    ]
    list_filter = ["activo", "servicio", "fecha_emision"]
    search_fields = ["codigo_uuid", "nombre_pasajero", "rut_pasajero", "orden__id"]
    readonly_fields = ["codigo_uuid", "fecha_emision"]
