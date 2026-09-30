"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
MÓDULO: SERVICIOS Y LÓGICA DE NEGOCIO TRANSACCIONAL (services.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
================================================================================
Este archivo concentra las reglas de negocio críticas y transacciones ACID:
1. CHECKOUT ATÓMICO:
   - Uso de db.transaction.atomic() y select_for_update() para control de concurrencia.
   - Verificación de stock/cupo en el instante exacto del pago (no al meter al carro).
   - Transición PENDIENTE -> PAGADO y emisión de boletos con código UUID único.
   - Limpieza del carro persistente en PostgreSQL.
2. GESTIÓN Y REVERSIÓN DE INVENTARIO:
   - Si una orden pasa a CANCELADO, los asientos quedan liberados automáticamente.
3. MAPA DE DISPONIBILIDAD DE ASIENTOS:
   - Cálculo en tiempo real de asientos libres vs ocupados para cada servicio.
================================================================================
"""

from decimal import Decimal
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import (
    Asiento,
    Servicio,
    CarroPasajes,
    ItemCarro,
    OrdenCompra,
    Boleto,
)


class VentaService:
    """
    Servicio encargado de orquestar la transacción de Checkout, pago
    y manejo del inventario de asientos bajo aislamiento transaccional estricto.
    """

    @classmethod
    def procesar_checkout(cls, usuario, metodo_pago=OrdenCompra.METODO_WEBPAY):
        """
        Ejecuta el proceso completo de confirmación y pago del carro de compras.

        GARANTÍAS Y REGLAS DE NEGOCIO:
        1. PERSISTENCIA: El carro se recupera desde PostgreSQL vinculado al ID del usuario.
        2. ATOMICIDAD: Se ejecuta dentro de un bloque `transaction.atomic()`.
        3. CONTROL DE CONCURRENCIA: Bloquea las filas de los asientos con `select_for_update()`
           para evitar condiciones de carrera (Race Conditions) entre múltiples pasajeros.
        4. VERIFICACIÓN DE INVENTARIO: Se valida que NINGÚN asiento esté ocupado por
           otra orden PAGADA con boleto activo.
        5. GENERACIÓN HISTÓRICA: Se crea la Orden de Compra (estado inicial PENDIENTE
           y posterior transición a PAGADO) con el método de pago seleccionado.
        6. EMISIÓN DE BOLETOS: Se genera un Boleto con UUID único para cada pasaje.
        7. VACIADO DEL CARRO: Se eliminan los ítems del carro persistente tras el éxito.
        """
        # 1. Obtener el carro persistente del usuario
        try:
            carro = CarroPasajes.objects.prefetch_related("items__servicio", "items__asiento").get(usuario=usuario)
        except CarroPasajes.DoesNotExist:
            raise ValidationError("No existe un carro de pasajes asociado al usuario.")

        items = list(carro.items.all())
        if not items:
            raise ValidationError("El carro de pasajes está vacío. Debe seleccionar al menos un asiento.")

        # 2. Iniciar bloque de transacción atómica
        with transaction.atomic():
            asiento_ids = [item.asiento_id for item in items]

            # Bloqueo a nivel de filas en PostgreSQL para evitar sobreventa concurrente
            asientos_bloqueados = list(
                Asiento.objects.select_for_update().filter(id__in=asiento_ids)
            )

            # Validar cada ítem del carro
            monto_total = Decimal("0.00")
            asientos_en_conflicto = []

            for item in items:
                servicio = item.servicio
                asiento = item.asiento

                # A. Verificar que el servicio siga programado
                if servicio.estado != Servicio.ESTADO_PROGRAMADO:
                    raise ValidationError(
                        f"El servicio #{servicio.id} ya no se encuentra disponible (Estado: {servicio.get_estado_display()})."
                    )

                # B. Comprobar si el asiento ya fue reservado/pagado por otra transacción
                asiento_ya_ocupado = Boleto.objects.filter(
                    servicio=servicio,
                    asiento=asiento,
                    orden__estado__in=[OrdenCompra.ESTADO_PAGADO, OrdenCompra.ESTADO_COMPLETADO],
                    activo=True,
                ).exists()

                if asiento_ya_ocupado:
                    asientos_en_conflicto.append(
                        f"Asiento #{asiento.numero} del servicio #{servicio.id} ({servicio.ruta})"
                    )

                # Sumar al monto total
                monto_total += item.precio_unitario

            # Si existe al menos un asiento en conflicto, rechazar compra con error 400
            if asientos_en_conflicto:
                detalle_conflicto = ", ".join(asientos_en_conflicto)
                raise ValidationError(
                    f"Transacción rechazada por inventario insuficiente: Los siguientes asientos ya fueron adquiridos por otro usuario: {detalle_conflicto}."
                )

            # 3. Generar la Orden histórica con estado inicial PENDIENTE
            if metodo_pago not in dict(OrdenCompra.METODOS_PAGO_CHOICES):
                metodo_pago = OrdenCompra.METODO_WEBPAY

            orden = OrdenCompra.objects.create(
                usuario=usuario,
                total=monto_total,
                estado=OrdenCompra.ESTADO_PENDIENTE,
                metodo_pago=metodo_pago,
            )

            # 4. Transición a estado PAGADO (se valida el pago exitoso del carro)
            orden.estado = OrdenCompra.ESTADO_PAGADO
            orden.save(update_fields=["estado", "fecha_actualizacion"])

            # 5. Emisión de boletos individuales con UUID irrepetible
            boletos_creados = []
            for item in items:
                boleto = Boleto.objects.create(
                    orden=orden,
                    servicio=item.servicio,
                    asiento=item.asiento,
                    nombre_pasajero=item.nombre_pasajero,
                    rut_pasajero=item.rut_pasajero,
                    precio_pagado=item.precio_unitario,
                    activo=True,
                )
                boletos_creados.append(boleto)

            # 6. Vaciar los ítems del carro persistente del usuario
            carro.items.all().delete()

            return orden


class GestionOrdenService:
    """
    Servicio administrativo para cambios de estado de órdenes y reversión de inventario.
    """

    @classmethod
    def cambiar_estado(cls, orden, nuevo_estado, usuario_admin):
        """
        Actualiza el estado de una orden.
        Si la orden pasa a 'CANCELADO', se aplica la reversión de inventario:
        los boletos se desactivan (activo=False), liberando inmediatamente
        los asientos en el catálogo público para nuevas compras.
        """
        with transaction.atomic():
            estado_anterior = orden.estado

            if nuevo_estado == estado_anterior:
                return orden

            # Caso: Cancelación de la Orden
            if nuevo_estado == OrdenCompra.ESTADO_CANCELADO:
                orden.estado = OrdenCompra.ESTADO_CANCELADO
                orden.save(update_fields=["estado", "fecha_actualizacion"])

                # Desactivar boletos para liberar asientos en el itinerario
                orden.boletos.update(activo=False)

            # Caso: Reactivación o cambio a Pagado / Completado
            elif nuevo_estado in [OrdenCompra.ESTADO_PAGADO, OrdenCompra.ESTADO_COMPLETADO]:
                # Si venía de cancelado, verificar disponibilidad antes de reactivar
                if estado_anterior == OrdenCompra.ESTADO_CANCELADO:
                    for boleto in orden.boletos.all():
                        ocupado = Boleto.objects.filter(
                            servicio=boleto.servicio,
                            asiento=boleto.asiento,
                            orden__estado__in=[OrdenCompra.ESTADO_PAGADO, OrdenCompra.ESTADO_COMPLETADO],
                            activo=True,
                        ).exclude(id=boleto.id).exists()

                        if ocupado:
                            raise ValidationError(
                                f"No se puede reactivar la orden: El asiento #{boleto.asiento.numero} ya fue adquirido por otro usuario."
                            )

                    # Reactivar boletos
                    orden.boletos.update(activo=True)

                orden.estado = nuevo_estado
                orden.save(update_fields=["estado", "fecha_actualizacion"])

            else:
                orden.estado = nuevo_estado
                orden.save(update_fields=["estado", "fecha_actualizacion"])

            return orden


class ConsultaServicioService:
    """
    Servicio de consulta para cálculo de disponibilidad de asientos en tiempo real.
    """

    @classmethod
    def obtener_asientos_disponibles(cls, servicio):
        """
        Retorna la lista de todos los asientos del bus con su estado de disponibilidad
        y precio dinámico según el tipo de asiento.
        """
        asientos_ocupados = set(servicio.get_asientos_ocupados_ids())
        asientos_bus = servicio.bus.asientos.all().order_by("piso", "numero")

        resultado = []
        for asiento in asientos_bus:
            precio = servicio.get_precio_por_asiento(asiento)
            disponible = asiento.id not in asientos_ocupados
            resultado.append({
                "id": asiento.id,
                "numero": asiento.numero,
                "tipo": asiento.get_tipo_display(),
                "piso": asiento.piso,
                "precio": precio,
                "disponible": disponible,
            })

        return resultado
