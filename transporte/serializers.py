"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
MÓDULO: SERIALIZADORES DRF (serializers.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
================================================================================
Este archivo define los serializadores de Django REST Framework para:
1. Custom SimpleJWT Token: Incorpora claims obligatorios ('role', 'username', 'user_id').
2. Registro y Perfil de Usuarios.
3. Infraestructura y Catálogo: Ciudades, Rutas, Buses, Asientos y Servicios.
4. Consulta de Asientos con Disponibilidad en tiempo real (disponible: true/false).
5. Carro de Compras Persistente y Validación de Asientos.
6. Órdenes de Compra y Emisión de Boletos con identificador UUID.
7. Información institucional del estudiante (Footer / Base).
================================================================================
"""

from decimal import Decimal
from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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


# ==============================================================================
# 1. SERIALIZADOR DE AUTENTICACIÓN JWT CON CUSTOM CLAIMS
# ==============================================================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializador personalizado de SimpleJWT.
    Extiende la generación de tokens para inyectar obligatoriamente en el payload:
    - 'role': Rol del usuario ('PASAJERO' o 'ADMIN_FLOTA').
    - 'username': Nombre de usuario.
    - 'user_id': Identificador primario de base de datos.
    - 'email': Correo electrónico institucional.
    - Claims de Tenant (Multi-Tenancy): 'tenant_id', 'tenant_nombre', 'tenant_slug'.

    También devuelve estos atributos en el cuerpo JSON de respuesta para conveniencia
    del cliente frontend / evaluador.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Inyección de claims personalizados en el payload cifrado del JWT
        token["role"] = user.rol
        token["username"] = user.username
        token["user_id"] = user.id
        token["email"] = user.email or ""

        # Multi-Tenancy: Si el usuario está asignado a un Tenant / Empresa
        if getattr(user, "empresa", None):
            token["tenant_id"] = user.empresa.id
            token["tenant_nombre"] = user.empresa.nombre
            token["tenant_slug"] = user.empresa.slug

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # Inyección de atributos informativos directos en la respuesta HTTP
        data["user_id"] = self.user.id
        data["username"] = self.user.username
        data["email"] = self.user.email or ""
        data["role"] = self.user.rol
        data["is_staff"] = bool(self.user.is_staff)
        data["is_superuser"] = bool(self.user.is_superuser)
        data["nombre_completo"] = f"{self.user.first_name} {self.user.last_name}".strip()

        if getattr(self.user, "empresa", None):
            data["tenant_id"] = self.user.empresa.id
            data["tenant_nombre"] = self.user.empresa.nombre
            data["tenant_slug"] = self.user.empresa.slug

        return data


class UsuarioRegistroSerializer(serializers.ModelSerializer):
    """
    Serializador para el autoregistro público de usuarios Pasajeros.
    Valida formato y encripta contraseñas con el algoritmo PBKDF2/Argon2 nativo de Django.
    """
    password = serializers.CharField(write_only=True, min_length=6, style={"input_type": "password"})

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "password",
            "email",
            "first_name",
            "last_name",
            "rut",
            "telefono",
            "rol",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        # Por defecto, usuarios creados por este endpoint público son PASAJERO
        rol = validated_data.get("rol", Usuario.ROL_PASAJERO)
        user = Usuario.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            rut=validated_data.get("rut", ""),
            telefono=validated_data.get("telefono", ""),
            rol=rol,
        )
        # Se inicializa inmediatamente su carro persistente en base de datos
        CarroPasajes.objects.get_or_create(usuario=user)
        return user


# ==============================================================================
# 2. SERIALIZADORES DE INFRAESTRUCTURA (EMPRESA/TENANT, CIUDAD, BUS, ASIENTO)
# ==============================================================================
class EmpresaTransporteSerializer(serializers.ModelSerializer):
    """Serializador para Empresas de Transporte / Tenants."""
    class Meta:
        model = EmpresaTransporte
        fields = ["id", "nombre", "rut", "slug", "color_hex", "activo"]


class CiudadSerializer(serializers.ModelSerializer):
    """Serializador para ciudades y terminales de origen y destino."""
    class Meta:
        model = Ciudad
        fields = ["id", "nombre", "terminal", "region"]


class AsientoSerializer(serializers.ModelSerializer):
    """Serializador estándar de asientos físicos."""
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Asiento
        fields = ["id", "bus", "numero", "tipo", "tipo_display", "piso"]


class BusSerializer(serializers.ModelSerializer):
    """Serializador de buses pertenecientes a la flota con soporte Multi-Tenant."""
    asientos = AsientoSerializer(many=True, read_only=True)
    empresa_detalle = EmpresaTransporteSerializer(source="empresa", read_only=True)
    estado_operativo_display = serializers.CharField(source="get_estado_operativo_display", read_only=True)

    class Meta:
        model = Bus
        fields = [
            "id",
            "empresa",
            "empresa_detalle",
            "patente",
            "modelo",
            "marca",
            "capacidad_total",
            "estado_operativo",
            "estado_operativo_display",
            "activo",
            "asientos",
        ]


# ==============================================================================
# 3. SERIALIZADORES DE RUTAS Y SERVICIOS / ITINERARIOS
# ==============================================================================
class RutaSerializer(serializers.ModelSerializer):
    """Serializador de Rutas con detalles anidados de origen y destino."""
    origen_detalle = CiudadSerializer(source="origen", read_only=True)
    destino_detalle = CiudadSerializer(source="destino", read_only=True)

    class Meta:
        model = Ruta
        fields = [
            "id",
            "origen",
            "destino",
            "origen_detalle",
            "destino_detalle",
            "distancia_km",
            "duracion_estimada_minutos",
        ]


class ServicioListSerializer(serializers.ModelSerializer):
    """
    Serializador optimizado de lectura para catálogo y búsquedas de servicios.
    Calcula asientos disponibles e incluye detalles del Tenant / Empresa de transporte.
    """
    ruta_detalle = RutaSerializer(source="ruta", read_only=True)
    empresa_detalle = EmpresaTransporteSerializer(source="empresa", read_only=True)
    bus_patente = serializers.CharField(source="bus.patente", read_only=True)
    bus_modelo = serializers.CharField(source="bus.modelo", read_only=True)
    total_asientos = serializers.IntegerField(source="bus.capacidad_total", read_only=True)
    asientos_disponibles_count = serializers.SerializerMethodField()
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = Servicio
        fields = [
            "id",
            "empresa",
            "empresa_detalle",
            "ruta",
            "ruta_detalle",
            "bus",
            "bus_patente",
            "bus_modelo",
            "fecha_hora_salida",
            "fecha_hora_llegada",
            "precio_semicama",
            "precio_cama",
            "estado",
            "estado_display",
            "total_asientos",
            "asientos_disponibles_count",
        ]

    def get_asientos_disponibles_count(self, obj):
        total = obj.bus.asientos.count()
        ocupados = len(obj.get_asientos_ocupados_ids())
        return max(0, total - ocupados)


class ServicioCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializador de escritura para creación y edición de servicios por el Administrador de Flota.
    """
    class Meta:
        model = Servicio
        fields = [
            "id",
            "empresa",
            "ruta",
            "bus",
            "fecha_hora_salida",
            "fecha_hora_llegada",
            "precio_semicama",
            "precio_cama",
            "estado",
        ]

    def validate(self, attrs):
        salida = attrs.get("fecha_hora_salida", getattr(self.instance, "fecha_hora_salida", None))
        llegada = attrs.get("fecha_hora_llegada", getattr(self.instance, "fecha_hora_llegada", None))
        if salida and llegada and llegada <= salida:
            raise serializers.ValidationError(
                {"fecha_hora_llegada": "La hora estimada de llegada debe ser posterior a la de salida."}
            )
        return attrs


class AsientoDisponibilidadSerializer(serializers.Serializer):
    """
    Serializador especializado para el endpoint público:
    GET /api/servicios/{id}/asientos/
    Proporciona el mapa completo de asientos indicando si cada asiento
    está 'disponible' (True) o ya reservado con boleto activo (False).
    """
    id = serializers.IntegerField()
    numero = serializers.IntegerField()
    tipo = serializers.CharField()
    piso = serializers.IntegerField()
    precio = serializers.DecimalField(max_digits=10, decimal_places=2)
    disponible = serializers.BooleanField()


# ==============================================================================
# 4. SERIALIZADORES DEL CARRO DE PASAJES PERSISTENTE
# ==============================================================================
class ItemCarroCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para agregar un asiento al carro persistente del usuario:
    POST /api/carro-pasajes/
    Aplica validaciones de negocio:
    - El asiento debe existir y pertenecer al bus del servicio.
    - El servicio debe estar en estado 'PROGRAMADO'.
    - El asiento no debe estar ocupado actualmente por otro boleto pagado.
    - El usuario no puede agregar dos veces el mismo asiento en el mismo servicio.
    """
    class Meta:
        model = ItemCarro
        fields = [
            "id",
            "servicio",
            "asiento",
            "nombre_pasajero",
            "rut_pasajero",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        servicio = attrs.get("servicio")
        asiento = attrs.get("asiento")

        # 1. Validar estado del servicio
        if servicio.estado != Servicio.ESTADO_PROGRAMADO:
            raise serializers.ValidationError(
                f"No es posible reservar pasajes para un servicio en estado '{servicio.get_estado_display()}'."
            )

        # 2. Validar que el asiento pertenezca al bus del servicio
        if asiento.bus_id != servicio.bus_id:
            raise serializers.ValidationError(
                f"El asiento #{asiento.numero} no pertenece al bus del servicio #{servicio.id}."
            )

        # 3. Advertencia si el asiento ya se encuentra ocupado por un boleto pagado activo
        if asiento.id in servicio.get_asientos_ocupados_ids():
            raise serializers.ValidationError(
                f"El asiento #{asiento.numero} ya se encuentra ocupado para este servicio."
            )

        return attrs


class ItemCarroBulkCreateSerializer(serializers.Serializer):
    """
    Serializador para agregar múltiples asientos en lote al carro persistente:
    POST /api/carro-pasajes/bulk/
    """
    items = ItemCarroCreateSerializer(many=True)


class ItemCarroListSerializer(serializers.ModelSerializer):
    """Serializador de lectura para ítems del carro con detección de disponibilidad."""
    servicio_id = serializers.IntegerField(source="servicio.id", read_only=True)
    origen = serializers.CharField(source="servicio.ruta.origen.nombre", read_only=True)
    destino = serializers.CharField(source="servicio.ruta.destino.nombre", read_only=True)
    fecha_hora_salida = serializers.DateTimeField(source="servicio.fecha_hora_salida", read_only=True)
    asiento_numero = serializers.IntegerField(source="asiento.numero", read_only=True)
    asiento_tipo = serializers.CharField(source="asiento.get_tipo_display", read_only=True)
    asiento_piso = serializers.IntegerField(source="asiento.piso", read_only=True)
    esta_disponible = serializers.SerializerMethodField()
    motivo_no_disponible = serializers.SerializerMethodField()

    class Meta:
        model = ItemCarro
        fields = [
            "id",
            "servicio_id",
            "origen",
            "destino",
            "fecha_hora_salida",
            "asiento_id",
            "asiento_numero",
            "asiento_tipo",
            "asiento_piso",
            "nombre_pasajero",
            "rut_pasajero",
            "precio_unitario",
            "agregado_en",
            "esta_disponible",
            "motivo_no_disponible",
        ]

    def get_esta_disponible(self, obj):
        # Asiento no disponible si ya fue adquirido por otro usuario o el servicio cambió de estado
        asiento_ocupado = Boleto.objects.filter(
            servicio=obj.servicio,
            asiento=obj.asiento,
            orden__estado__in=[OrdenCompra.ESTADO_PAGADO, OrdenCompra.ESTADO_COMPLETADO],
            activo=True,
        ).exists()
        if asiento_ocupado or obj.servicio.estado != Servicio.ESTADO_PROGRAMADO:
            return False
        return True

    def get_motivo_no_disponible(self, obj):
        asiento_ocupado = Boleto.objects.filter(
            servicio=obj.servicio,
            asiento=obj.asiento,
            orden__estado__in=[OrdenCompra.ESTADO_PAGADO, OrdenCompra.ESTADO_COMPLETADO],
            activo=True,
        ).exists()
        if asiento_ocupado:
            return "Asiento ya comprado por otro usuario"
        if obj.servicio.estado != Servicio.ESTADO_PROGRAMADO:
            return f"Servicio en estado {obj.servicio.get_estado_display()}"
        return None


class CarroPasajesSerializer(serializers.ModelSerializer):
    """
    Serializador completo del carro de compras persistente.
    Muestra la lista de ítems, el conteo total de pasajes y el monto total en CLP,
    e informa si existen ítems que se hayan agotado por compras de otros usuarios.
    """
    items = ItemCarroListSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    cantidad_items = serializers.SerializerMethodField()
    tiene_items_agotados = serializers.SerializerMethodField()
    cantidad_items_agotados = serializers.SerializerMethodField()

    class Meta:
        model = CarroPasajes
        fields = [
            "id",
            "usuario",
            "cantidad_items",
            "tiene_items_agotados",
            "cantidad_items_agotados",
            "total",
            "items",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "usuario", "creado_en", "actualizado_en"]

    def get_cantidad_items(self, obj):
        return obj.items.count()

    def get_tiene_items_agotados(self, obj):
        for item in obj.items.all():
            ocupado = Boleto.objects.filter(
                servicio=item.servicio,
                asiento=item.asiento,
                orden__estado__in=[OrdenCompra.ESTADO_PAGADO, OrdenCompra.ESTADO_COMPLETADO],
                activo=True,
            ).exists()
            if ocupado or item.servicio.estado != Servicio.ESTADO_PROGRAMADO:
                return True
        return False

    def get_cantidad_items_agotados(self, obj):
        count = 0
        for item in obj.items.all():
            ocupado = Boleto.objects.filter(
                servicio=item.servicio,
                asiento=item.asiento,
                orden__estado__in=[OrdenCompra.ESTADO_PAGADO, OrdenCompra.ESTADO_COMPLETADO],
                activo=True,
            ).exists()
            if ocupado or item.servicio.estado != Servicio.ESTADO_PROGRAMADO:
                count += 1
        return count


# ==============================================================================
# 5. SERIALIZADORES DE BOLETOS, ÓRDENES Y VENTAS
# ==============================================================================
class BoletoSerializer(serializers.ModelSerializer):
    """
    Serializador de Boletos emitidos. Expone el código UUID único e información del viaje.
    """
    servicio_id = serializers.IntegerField(source="servicio.id", read_only=True)
    origen = serializers.CharField(source="servicio.ruta.origen.nombre", read_only=True)
    terminal_origen = serializers.CharField(source="servicio.ruta.origen.terminal", read_only=True)
    destino = serializers.CharField(source="servicio.ruta.destino.nombre", read_only=True)
    terminal_destino = serializers.CharField(source="servicio.ruta.destino.terminal", read_only=True)
    fecha_hora_salida = serializers.DateTimeField(source="servicio.fecha_hora_salida", read_only=True)
    bus_patente = serializers.CharField(source="servicio.bus.patente", read_only=True)
    asiento_numero = serializers.IntegerField(source="asiento.numero", read_only=True)
    asiento_tipo = serializers.CharField(source="asiento.get_tipo_display", read_only=True)
    estado_embarque_display = serializers.CharField(source="get_estado_embarque_display", read_only=True)

    class Meta:
        model = Boleto
        fields = [
            "codigo_uuid",
            "orden_id",
            "servicio_id",
            "origen",
            "terminal_origen",
            "destino",
            "terminal_destino",
            "fecha_hora_salida",
            "bus_patente",
            "asiento_numero",
            "asiento_tipo",
            "nombre_pasajero",
            "rut_pasajero",
            "precio_pagado",
            "estado_embarque",
            "estado_embarque_display",
            "activo",
            "fecha_emision",
        ]


class OrdenCompraSerializer(serializers.ModelSerializer):
    """
    Serializador de Orden de Compra histórica.
    Incluye los boletos emitidos tras la confirmación del pago.
    """
    usuario_username = serializers.CharField(source="usuario.username", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    metodo_pago_display = serializers.CharField(source="get_metodo_pago_display", read_only=True)
    boletos = BoletoSerializer(many=True, read_only=True)

    class Meta:
        model = OrdenCompra
        fields = [
            "id",
            "usuario",
            "usuario_username",
            "total",
            "estado",
            "estado_display",
            "metodo_pago",
            "metodo_pago_display",
            "boletos",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = ["id", "usuario", "total", "fecha_creacion", "fecha_actualizacion"]


class CambioEstadoOrdenSerializer(serializers.Serializer):
    """
    Serializador para el cambio administrativo de estado de una orden:
    PATCH /api/ventas/{id}/estado/
    Acepta estados válidos ('PENDIENTE', 'PAGADO', 'CANCELADO', 'COMPLETADO').
    """
    estado = serializers.ChoiceField(choices=OrdenCompra.ESTADOS_ORDEN_CHOICES)


# ==============================================================================
# 6. SERIALIZADOR DE INFORMACIÓN BASE Y FOOTER DEL ALUMNO
# ==============================================================================
class FooterBaseSerializer(serializers.Serializer):
    """
    Serializador para renderizar los datos del alumno y contexto de la evaluación.
    Cumple el requisito de datos visibles de alumno, sección y año 2026.
    """
    alumno = serializers.CharField()
    seccion = serializers.CharField()
    anio = serializers.IntegerField()
    asignatura = serializers.CharField()
    proyecto = serializers.CharField()
    version = serializers.CharField()
    documentacion_swagger = serializers.CharField()
