"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
MÓDULO: CONTROL DE ACCESO BASADO EN ROLES (RBAC) (permissions.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
================================================================================
Este archivo define las clases de permisos personalizadas para Django REST
Framework. Permite implementar una arquitectura de seguridad estricta basada
en la matriz de roles requerida:
1. Pasajero (Cliente): Acceso exclusivo a su carro persistente, checkout
   y consulta de sus propios boletos comprados.
2. Administrador de Flota (Gestor): Creación, edición y eliminación de
   servicios e itinerarios, así como la gestión y cancelación de órdenes.
3. Público / Sin Autenticación: Búsqueda y consulta de catálogo de itinerarios
   y disponibilidad de asientos.
================================================================================
"""

from rest_framework import permissions


class IsPasajero(permissions.BasePermission):
    """
    Permiso que autoriza únicamente a usuarios autenticados que posean
    el rol de 'PASAJERO' (o superusuarios del sistema).
    Utilizado en:
    - Gestión de Carro de Pasajes (/api/carro-pasajes/)
    - Checkout y Pago Atómico (/api/ventas/checkout/)
    - Consulta de Mis Boletos (/api/mis-boletos/)
    """
    message = "Acceso denegado: Se requiere una cuenta de usuario con rol 'PASAJERO'."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                getattr(request.user, "rol", None) == "PASAJERO"
                or request.user.is_superuser
            )
        )


class IsAdminFlota(permissions.BasePermission):
    """
    Permiso que autoriza únicamente a usuarios autenticados con rol
    de 'ADMIN_FLOTA', staff o superusuarios.
    Utilizado en:
    - Administración completa de servicios (POST, PUT, DELETE /api/servicios/)
    - Cambio administrativo de estado de órdenes (PATCH /api/ventas/{id}/estado/)
    - Gestión de flota (ciudades, rutas, buses y asientos).
    """
    message = "Acceso denegado: Se requiere rol de 'ADMIN_FLOTA' para ejecutar esta operación."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                getattr(request.user, "rol", None) == "ADMIN_FLOTA"
                or request.user.is_staff
                or request.user.is_superuser
            )
        )


class IsAdminFlotaOrReadOnly(permissions.BasePermission):
    """
    Permiso que permite lectura pública (GET, HEAD, OPTIONS) a cualquier cliente,
    pero restringe las mutaciones (POST, PUT, PATCH, DELETE) exclusivamente
    a administradores de flota.
    """
    message = "Acceso denegado: Solo el Administrador de Flota puede modificar este recurso."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                getattr(request.user, "rol", None) == "ADMIN_FLOTA"
                or request.user.is_staff
                or request.user.is_superuser
            )
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permiso a nivel de objeto que autoriza al propietario del recurso
    (por ejemplo, el usuario dueño de la orden o boleto) o a un Administrador de Flota.
    """
    message = "Acceso denegado: No tienes permisos sobre este recurso."

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False

        # Si el usuario es administrador de flota o superusuario, tiene acceso completo
        if getattr(request.user, "rol", None) == "ADMIN_FLOTA" or request.user.is_staff or request.user.is_superuser:
            return True

        # Si el objeto tiene un campo usuario (ej: OrdenCompra, CarroPasajes)
        if hasattr(obj, "usuario"):
            return obj.usuario_id == request.user.id

        # Si el objeto es un Boleto, verificar mediante la orden asociada
        if hasattr(obj, "orden") and hasattr(obj.orden, "usuario"):
            return obj.orden.usuario_id == request.user.id

        return False
