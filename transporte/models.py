"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
MÓDULO: MODELOS DE DATOS (models.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
================================================================================
Este archivo define la capa de persistencia ORM de Django con PostgreSQL,
garantizando normalización, integridad referencial (Foreign Keys, OneToOne),
definición explícita de CHOICES para estados y tipos, y modelos de soporte para:
1. Usuario con Roles (RBAC): 'PASAJERO' y 'ADMIN_FLOTA'.
2. Infraestructura: Ciudades/Terminales, Buses y Asientos (Semicama / Cama).
3. Operación: Rutas e Itinerarios/Servicios con horarios y tarifas.
4. Carro de Compras Persistente: OneToOne con Usuario, almacena asientos y pasajeros.
5. Ventas y Transacciones: Órdenes con estados y emisión de Boletos con UUID.
================================================================================
"""

import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone


# ==============================================================================
# 0. MODELO DE TENANT / EMPRESA DE TRANSPORTE (MULTI-TENANCY)
# ==============================================================================
class EmpresaTransporte(models.Model):
    """
    Representa a una Empresa u Operador de Transporte Interurbano (Tenant).
    Ejemplos reales: Turbus, Pullman Bus, EME Bus, Buses Bio-Bio.
    Permite arquitectura Multi-Tenant: cada empresa administra su propia flota
    y servicios de itinerario de forma organizada y diferenciada.
    """
    nombre = models.CharField(
        max_length=120,
        unique=True,
        verbose_name="Nombre de Empresa / Tenant",
        help_text="Ej: Turbus, Pullman Bus, EME Bus.",
    )
    rut = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="RUT Empresa",
        help_text="Identificador tributario único (ej: 76.123.456-7).",
    )
    slug = models.SlugField(
        max_length=60,
        unique=True,
        verbose_name="Identificador Tenant (Slug)",
        help_text="Identificador único para URLs o filtros (ej: 'turbus', 'pullman').",
    )
    color_hex = models.CharField(
        max_length=10,
        default="#1e3a8a",
        verbose_name="Color de Marca (HEX)",
        help_text="Color corporativo para el frontend (ej: '#0284c7').",
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="¿Empresa Operativa?",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Empresa de Transporte (Tenant)"
        verbose_name_plural = "Empresas de Transporte (Tenants)"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} [{self.slug}]"


# ==============================================================================
# 1. MODELO DE USUARIO Y CONTROL DE ROLES (RBAC)
# ==============================================================================
class Usuario(AbstractUser):
    """
    Modelo de Usuario personalizado que extiende AbstractUser.
    Permite asociar de forma directa el Rol del usuario dentro del sistema
    para gobernar permisos mediante SimpleJWT y Custom Permissions de DRF.
    En el caso de 'ADMIN_FLOTA', puede asociarse a una Empresa/Tenant específica.
    """
    ROL_PASAJERO = "PASAJERO"
    ROL_ADMIN_FLOTA = "ADMIN_FLOTA"

    ROLES_CHOICES = (
        (ROL_PASAJERO, "Pasajero"),
        (ROL_ADMIN_FLOTA, "Administrador de Flota"),
    )

    rol = models.CharField(
        max_length=20,
        choices=ROLES_CHOICES,
        default=ROL_PASAJERO,
        verbose_name="Rol de Usuario",
        help_text="Define si el usuario es un Pasajero (cliente) o un Administrador de Flota.",
    )
    rut = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name="RUT / Pasaporte",
        help_text="Identificador legal del usuario (ej: 12345678-9).",
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Teléfono de Contacto",
    )
    empresa = models.ForeignKey(
        EmpresaTransporte,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="administradores",
        verbose_name="Empresa Asignada (Tenant)",
        help_text="Si el usuario es Administrador de Flota, determina el Tenant al que pertenece.",
    )

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["username"]

    def __str__(self):
        return f"{self.username} [{self.get_rol_display()}]"

    @property
    def is_pasajero(self):
        """Retorna True si el usuario tiene rol de Pasajero."""
        return self.rol == self.ROL_PASAJERO

    @property
    def is_admin_flota(self):
        """Retorna True si el usuario tiene rol de Administrador de Flota o es staff/superuser."""
        return self.rol == self.ROL_ADMIN_FLOTA or self.is_staff or self.is_superuser


# ==============================================================================
# 2. MODELOS DE INFRAESTRUCTURA DE TRANSPORTE (CIUDADES, BUSES, ASIENTOS)
# ==============================================================================
class Ciudad(models.Model):
    """
    Representa una Ciudad y su Terminal de Buses asociado.
    Sirve como origen o destino dentro de las Rutas de transporte.
    """
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre de Ciudad",
        help_text="Ej: Santiago, Valparaíso, Concepción.",
    )
    terminal = models.CharField(
        max_length=150,
        verbose_name="Nombre del Terminal",
        help_text="Ej: Terminal Sur, Terminal Rodoviario, Terminal Collao.",
    )
    region = models.CharField(
        max_length=100,
        verbose_name="Región",
        help_text="Región administrativa en Chile.",
    )

    class Meta:
        verbose_name = "Ciudad / Terminal"
        verbose_name_plural = "Ciudades y Terminales"
        ordering = ["nombre"]
        unique_together = ("nombre", "terminal")

    def __str__(self):
        return f"{self.nombre} ({self.terminal})"


class Bus(models.Model):
    """
    Representa una unidad física de transporte (Bus) perteneciente a la flota.
    """
    ESTADO_OPERATIVO_DISPONIBLE = "DISPONIBLE"
    ESTADO_OPERATIVO_EN_RUTA = "EN_RUTA"
    ESTADO_OPERATIVO_MANTENIMIENTO = "MANTENIMIENTO"
    ESTADO_OPERATIVO_FUERA_SERVICIO = "FUERA_SERVICIO"

    ESTADOS_OPERATIVOS_CHOICES = (
        (ESTADO_OPERATIVO_DISPONIBLE, "Disponible en Terminal"),
        (ESTADO_OPERATIVO_EN_RUTA, "En Ruta / Asignado"),
        (ESTADO_OPERATIVO_MANTENIMIENTO, "En Mantenimiento Preventivo"),
        (ESTADO_OPERATIVO_FUERA_SERVICIO, "Fuera de Servicio"),
    )

    patente = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Patente (PPU)",
        help_text="Patente única del vehículo (ej: ABCD-12).",
    )
    modelo = models.CharField(
        max_length=100,
        verbose_name="Modelo del Bus",
        help_text="Ej: Marcopolo Paradiso 1800 DD.",
    )
    marca = models.CharField(
        max_length=100,
        default="Scania",
        verbose_name="Marca del Chasis/Carrocería",
    )
    capacidad_total = models.PositiveIntegerField(
        verbose_name="Capacidad Total de Asientos",
        help_text="Cantidad máxima física de asientos del bus.",
    )
    estado_operativo = models.CharField(
        max_length=20,
        choices=ESTADOS_OPERATIVOS_CHOICES,
        default=ESTADO_OPERATIVO_DISPONIBLE,
        verbose_name="Estado Operativo de la Máquina",
        help_text="Define si la máquina está disponible en terminal, en ruta, en mantenimiento o fuera de servicio.",
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="¿Bus Operativo?",
        help_text="Indica si el bus está habilitado para ser asignado a servicios.",
    )
    empresa = models.ForeignKey(
        EmpresaTransporte,
        on_delete=models.CASCADE,
        related_name="buses",
        null=True,
        blank=True,
        verbose_name="Empresa Propietaria (Tenant)",
    )

    class Meta:
        verbose_name = "Bus"
        verbose_name_plural = "Buses"
        ordering = ["patente"]

    def __str__(self):
        return f"Bus {self.patente} - {self.modelo} ({self.capacidad_total} as.)"


class Asiento(models.Model):
    """
    Representa un asiento físico ubicado dentro de un bus específico.
    Posee tipo con CHOICES ('SEMICAMA', 'CAMA') y número de piso.
    """
    TIPO_SEMICAMA = "SEMICAMA"
    TIPO_CAMA = "CAMA"

    TIPOS_ASIENTO_CHOICES = (
        (TIPO_SEMICAMA, "Semicama"),
        (TIPO_CAMA, "Cama"),
    )

    bus = models.ForeignKey(
        Bus,
        on_delete=models.CASCADE,
        related_name="asientos",
        verbose_name="Bus Asignado",
    )
    numero = models.PositiveIntegerField(
        verbose_name="Número de Asiento",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPOS_ASIENTO_CHOICES,
        default=TIPO_SEMICAMA,
        verbose_name="Tipo / Confort del Asiento",
    )
    piso = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Piso del Bus (1 o 2)",
    )

    class Meta:
        verbose_name = "Asiento"
        verbose_name_plural = "Asientos"
        ordering = ["bus", "piso", "numero"]
        unique_together = ("bus", "numero")

    def __str__(self):
        return f"Asiento #{self.numero} [{self.get_tipo_display()}] - Bus {self.bus.patente} (Piso {self.piso})"


# ==============================================================================
# 3. MODELOS DE OPERACIÓN Y LOGÍSTICA (RUTAS Y SERVICIOS/ITINERARIOS)
# ==============================================================================
class Ruta(models.Model):
    """
    Define el trayecto directo entre una ciudad origen y una ciudad destino.
    """
    origen = models.ForeignKey(
        Ciudad,
        on_delete=models.CASCADE,
        related_name="rutas_origen",
        verbose_name="Ciudad Origen",
    )
    destino = models.ForeignKey(
        Ciudad,
        on_delete=models.CASCADE,
        related_name="rutas_destino",
        verbose_name="Ciudad Destino",
    )
    distancia_km = models.PositiveIntegerField(
        verbose_name="Distancia en KM",
    )
    duracion_estimada_minutos = models.PositiveIntegerField(
        verbose_name="Duración Estimada (Minutos)",
    )

    class Meta:
        verbose_name = "Ruta"
        verbose_name_plural = "Rutas"
        unique_together = ("origen", "destino")
        ordering = ["origen__nombre", "destino__nombre"]

    def clean(self):
        if self.origen_id and self.destino_id and self.origen_id == self.destino_id:
            raise ValidationError("El origen y el destino de una ruta no pueden ser idénticos.")

    def __str__(self):
        return f"{self.origen.nombre} ({self.origen.terminal}) ➔ {self.destino.nombre} ({self.destino.terminal})"


class Servicio(models.Model):
    """
    Itinerario programado que vincula una Ruta con un Bus, fecha/hora de salida
    y llegada, con tarifas diferenciadas por tipo de asiento (Semicama / Cama).
    """
    ESTADO_PROGRAMADO = "PROGRAMADO"
    ESTADO_EN_RUTA = "EN_RUTA"
    ESTADO_FINALIZADO = "FINALIZADO"
    ESTADO_CANCELADO = "CANCELADO"

    ESTADOS_SERVICIO_CHOICES = (
        (ESTADO_PROGRAMADO, "Programado"),
        (ESTADO_EN_RUTA, "En Ruta"),
        (ESTADO_FINALIZADO, "Finalizado"),
        (ESTADO_CANCELADO, "Cancelado"),
    )

    ruta = models.ForeignKey(
        Ruta,
        on_delete=models.CASCADE,
        related_name="servicios",
        verbose_name="Ruta del Servicio",
    )
    bus = models.ForeignKey(
        Bus,
        on_delete=models.CASCADE,
        related_name="servicios",
        verbose_name="Bus Asignado",
    )
    fecha_hora_salida = models.DateTimeField(
        verbose_name="Fecha y Hora de Salida",
    )
    fecha_hora_llegada = models.DateTimeField(
        verbose_name="Fecha y Hora Estimada de Llegada",
    )
    precio_semicama = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio Tarifa Semicama (CLP)",
    )
    precio_cama = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio Tarifa Cama (CLP)",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_SERVICIO_CHOICES,
        default=ESTADO_PROGRAMADO,
        verbose_name="Estado Operativo del Servicio",
    )
    empresa = models.ForeignKey(
        EmpresaTransporte,
        on_delete=models.CASCADE,
        related_name="servicios",
        null=True,
        blank=True,
        verbose_name="Empresa Operadora (Tenant)",
    )

    class Meta:
        verbose_name = "Servicio / Itinerario"
        verbose_name_plural = "Servicios e Itinerarios"
        ordering = ["fecha_hora_salida"]

    def save(self, *args, **kwargs):
        # Si no se indica empresa explícita, se hereda la empresa del bus asignado
        if not self.empresa_id and self.bus_id and getattr(self.bus, "empresa_id", None):
            self.empresa_id = self.bus.empresa_id
        super().save(*args, **kwargs)

    def clean(self):
        if self.fecha_hora_salida and self.fecha_hora_llegada:
            if self.fecha_hora_llegada <= self.fecha_hora_salida:
                raise ValidationError("La hora estimada de llegada debe ser posterior a la de salida.")

    def __str__(self):
        salida_fmt = self.fecha_hora_salida.strftime("%d/%m/%Y %H:%M")
        return f"Servicio #{self.id}: {self.ruta} [{salida_fmt}] - Bus {self.bus.patente}"

    def get_precio_por_asiento(self, asiento):
        """Retorna el valor del pasaje según el tipo de asiento (Semicama o Cama)."""
        if asiento.tipo == Asiento.TIPO_CAMA:
            return self.precio_cama
        return self.precio_semicama

    def get_asientos_ocupados_ids(self):
        """
        Retorna la lista de IDs de asientos ocupados para este servicio.
        Un asiento está ocupado si posee un Boleto emitido en una Orden con
        estado 'PAGADO' o 'COMPLETADO', y con boleto.activo = True.
        Si la orden pasa a 'CANCELADO', el boleto se desactiva y el asiento se libera.
        """
        return list(
            self.boletos.filter(
                orden__estado__in=[OrdenCompra.ESTADO_PAGADO, OrdenCompra.ESTADO_COMPLETADO],
                activo=True,
            ).values_list("asiento_id", flat=True)
        )


# ==============================================================================
# 4. CARRO DE COMPRAS PERSISTENTE (POSTGRESQL POST-LOGOUT)
# ==============================================================================
class CarroPasajes(models.Model):
    """
    Carro de pasajes persistente en base de datos PostgreSQL.
    Relación 1 a 1 con el Usuario Pasajero.
    Garantiza que al cerrar sesión (logout) o cambiar de dispositivo/navegador,
    los pasajes previamente añadidos permanezcan guardados en PostgreSQL.
    """
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name="carro",
        verbose_name="Usuario Propietario",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Carro de Pasajes"
        verbose_name_plural = "Carros de Pasajes"

    def __str__(self):
        return f"Carro Activo de {self.usuario.username}"

    @property
    def total(self):
        """Calcula dinámicamente el monto total sumando los ítems actuales del carro."""
        return sum((item.precio_unitario for item in self.items.all()), Decimal("0.00"))


class ItemCarro(models.Model):
    """
    Ítem individual dentro del carro de pasajes del usuario.
    Almacena el servicio, el asiento seleccionado y los datos obligatorios
    del ocupante (Nombre Completo y RUT/Pasaporte).

    REGLA DE NEGOCIO CRÍTICA:
    El asiento NO se bloquea ni descuenta del inventario al agregarlo al carro.
    La persistencia es puramente de selección hasta ejecutar el checkout.
    """
    carro = models.ForeignKey(
        CarroPasajes,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Carro Asociado",
    )
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="items_en_carro",
        verbose_name="Servicio Seleccionado",
    )
    asiento = models.ForeignKey(
        Asiento,
        on_delete=models.CASCADE,
        related_name="items_en_carro",
        verbose_name="Asiento Seleccionado",
    )
    nombre_pasajero = models.CharField(
        max_length=150,
        verbose_name="Nombre Completo del Ocupante",
    )
    rut_pasajero = models.CharField(
        max_length=20,
        verbose_name="RUT / Pasaporte del Ocupante",
    )
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio Congelado al Agregar",
    )
    agregado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ítem de Carro"
        verbose_name_plural = "Ítems de Carro"
        ordering = ["agregado_en"]
        # Evita que el mismo usuario agregue el mismo asiento del mismo servicio dos veces
        unique_together = ("carro", "servicio", "asiento")

    def clean(self):
        # Valida que el asiento efectivamente pertenezca al bus asignado al servicio
        if self.asiento.bus_id != self.servicio.bus_id:
            raise ValidationError(
                f"El asiento #{self.asiento.numero} no pertenece al bus {self.servicio.bus.patente} asignado a este servicio."
            )

    def save(self, *args, **kwargs):
        # Fija el precio unitario según la tarifa del servicio y tipo de asiento
        if not self.precio_unitario:
            self.precio_unitario = self.servicio.get_precio_por_asiento(self.asiento)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Asiento #{self.asiento.numero} - {self.nombre_pasajero} (Servicio #{self.servicio.id})"


# ==============================================================================
# 5. MODELOS DE VENTA, ÓRDENES Y BOLETOS (TRANSACCIÓN ATÓMICA Y UUID)
# ==============================================================================
class OrdenCompra(models.Model):
    """
    Registro histórico de la transacción de compra de pasajes.
    Maneja el ciclo de vida del estado con CHOICES:
    - PENDIENTE: Orden generada inicialmente al iniciar checkout.
    - PAGADO: Transacción atómica validada exitosamente y asientos reservados.
    - CANCELADO: Orden anulada administrativamente; libera asientos automáticamente.
    - COMPLETADO: Servicio ejecutado o viaje finalizado.
    """
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_PAGADO = "PAGADO"
    ESTADO_CANCELADO = "CANCELADO"
    ESTADO_COMPLETADO = "COMPLETADO"

    ESTADOS_ORDEN_CHOICES = (
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_PAGADO, "Pagado"),
        (ESTADO_CANCELADO, "Cancelado"),
        (ESTADO_COMPLETADO, "Completado"),
    )

    METODO_WEBPAY = "WEBPAY"
    METODO_TRANSFERENCIA = "TRANSFERENCIA"
    METODO_EFECTIVO = "EFECTIVO"
    METODO_BANCO_ESTADO = "BANCO_ESTADO"

    METODOS_PAGO_CHOICES = (
        (METODO_WEBPAY, "Webpay Plus / Débito - Crédito"),
        (METODO_TRANSFERENCIA, "Transferencia Bancaria"),
        (METODO_EFECTIVO, "Efectivo en Boletería"),
        (METODO_BANCO_ESTADO, "CuentaRUT / BancoEstado"),
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="ordenes",
        verbose_name="Pasajero Comprador",
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Monto Total Pagado (CLP)",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_ORDEN_CHOICES,
        default=ESTADO_PENDIENTE,
        verbose_name="Estado de la Orden",
    )
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODOS_PAGO_CHOICES,
        default=METODO_WEBPAY,
        verbose_name="Método de Pago",
        help_text="Pasarela o medio de pago seleccionado por el cliente.",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Orden #{self.id} - {self.usuario.username} - [{self.get_estado_display()}] - Total: ${self.total}"


class Boleto(models.Model):
    """
    Boleto individual emitido tras el pago exitoso de una orden.
    Contiene un código UUID único e irrepetible para control de acceso y abordaje.
    Si la orden asociada es cancelada, el boleto se marca como activo=False,
    liberando de forma inmediata el asiento para nuevas reservas (reversión de inventario).
    """
    ESTADO_EMBARQUE_EMITIDO = "EMITIDO"
    ESTADO_EMBARQUE_EMBARCADO = "EMBARCADO"
    ESTADO_EMBARQUE_NO_SHOW = "NO_SHOW"

    ESTADOS_EMBARQUE_CHOICES = (
        (ESTADO_EMBARQUE_EMITIDO, "Boleto Emitido / Pendiente Abordaje"),
        (ESTADO_EMBARQUE_EMBARCADO, "Pasajero a Bordo"),
        (ESTADO_EMBARQUE_NO_SHOW, "No se Presentó (No Show)"),
    )

    codigo_uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Código Único de Boleto (UUID)",
    )
    orden = models.ForeignKey(
        OrdenCompra,
        on_delete=models.CASCADE,
        related_name="boletos",
        verbose_name="Orden de Compra",
    )
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.PROTECT,
        related_name="boletos",
        verbose_name="Servicio Itinerario",
    )
    asiento = models.ForeignKey(
        Asiento,
        on_delete=models.PROTECT,
        related_name="boletos",
        verbose_name="Asiento Asignado",
    )
    nombre_pasajero = models.CharField(
        max_length=150,
        verbose_name="Nombre Completo del Ocupante",
    )
    rut_pasajero = models.CharField(
        max_length=20,
        verbose_name="RUT / Pasaporte del Ocupante",
    )
    precio_pagado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio Pagado",
    )
    estado_embarque = models.CharField(
        max_length=20,
        choices=ESTADOS_EMBARQUE_CHOICES,
        default=ESTADO_EMBARQUE_EMITIDO,
        verbose_name="Estado de Embarque",
        help_text="Control de abordaje físico del pasajero en la máquina.",
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="¿Boleto Válido y Ocupando Asiento?",
        help_text="Si se cancela la orden, se desactiva para reponer el asiento al inventario.",
    )
    fecha_emision = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Boleto de Viaje"
        verbose_name_plural = "Boletos de Viaje"
        ordering = ["-fecha_emision"]

    def __str__(self):
        return f"Boleto {self.codigo_uuid} - Asiento #{self.asiento.numero} ({self.nombre_pasajero})"
