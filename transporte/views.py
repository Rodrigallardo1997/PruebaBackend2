"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
MÓDULO: CONTROLADORES Y VISTAS DE API (views.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
================================================================================
Este archivo define los controladores RESTful (APIViews, Generics y ViewSets):
1. Vista Base / Footer Info:
   - Renderiza visiblemente los datos del estudiante: Nombre, Sección y Año 2026.
2. Autenticación y Token JWT:
   - Login con generación de claims personalizados ('role', 'username', 'user_id').
   - Registro de pasajeros.
3. Catálogo y Búsqueda (Público):
   - GET /api/servicios/buscar/ con django-filter.
   - GET /api/servicios/{id}/asientos/ con disponibilidad en tiempo real.
4. Pasajero (IsAuthenticated & IsPasajero):
   - GET/POST /api/carro-pasajes/ (carro persistente en PostgreSQL).
   - DELETE /api/carro-pasajes/{item_id}/.
   - POST /api/ventas/checkout/ (transacción atómica ACID y emisión de boletos).
   - GET /api/mis-boletos/ (historial de pasajes con UUID).
5. Administrador de Flota (IsAuthenticated & IsAdminFlota):
   - CRUD completo de servicios e infraestructura.
   - PATCH /api/ventas/{id}/estado/ (cambio de estado y reversión de inventario).
================================================================================
"""

from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.shortcuts import render, get_object_or_404
from rest_framework import status, generics, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

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
from .serializers import (
    CustomTokenObtainPairSerializer,
    UsuarioRegistroSerializer,
    UsuarioAdminListSerializer,
    UsuarioAdminCreateSerializer,
    UsuarioPrivilegiosUpdateSerializer,
    EmpresaTransporteSerializer,
    CiudadSerializer,
    BusSerializer,
    AsientoSerializer,
    RutaSerializer,
    ServicioListSerializer,
    ServicioCreateUpdateSerializer,
    AsientoDisponibilidadSerializer,
    CarroPasajesSerializer,
    ItemCarroCreateSerializer,
    ItemCarroBulkCreateSerializer,
    ItemCarroListSerializer,
    OrdenCompraSerializer,
    BoletoSerializer,
    CambioEstadoOrdenSerializer,
    FooterBaseSerializer,
)
from .permissions import (
    IsPasajero,
    IsAdminFlota,
    IsAdminFlotaOrReadOnly,
    IsOwnerOrAdmin,
    IsSuperUser,
)
from .filters import ServicioFilter
from .services import (
    VentaService,
    GestionOrdenService,
    ConsultaServicioService,
)


# ==============================================================================
# 1. VISTA BASE / FOOTER INFORMATIVO DEL ALUMNO (REQUERIMIENTO EVALUACIÓN)
# ==============================================================================
class BaseFooterInfoView(APIView):
    """
    Endpoint base / pie de página informativo que contiene visibles
    los datos requeridos del estudiante:
    - Alumno: Rodrigo Gallardo
    - Sección: AP-N4-C2(E-F)/D
    - Año: 2026
    Soporta formato JSON para clientes API y renderizado HTML para navegación web.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Información Base y Footer del Alumno (EVA-2)",
        description="Retorna los datos de identificación del estudiante y enlaces a la documentación.",
        responses={200: FooterBaseSerializer},
    )
    def get(self, request, *args, **kwargs):
        student_info = getattr(
            settings,
            "STUDENT_INFO",
            {
                "ALUMNO": "Rodrigo Gallardo",
                "SECCION": "AP-N4-C2(E-F)/D",
                "ANIO": 2026,
                "ASIGNATURA": "Desarrollo Backend (Evaluación EVA-2)",
                "PROYECTO": "Proyecto 4 - Reservas de Pasajes de Buses Interurbanos",
                "VERSION": "1.0.0",
            },
        )

        data = {
            "alumno": student_info.get("ALUMNO"),
            "seccion": student_info.get("SECCION"),
            "anio": student_info.get("ANIO"),
            "asignatura": student_info.get("ASIGNATURA"),
            "proyecto": student_info.get("PROYECTO"),
            "version": student_info.get("VERSION"),
            "documentacion_swagger": "/api/docs/",
            "endpoints_principales": {
                "login_jwt": "/api/token/",
                "refresh_jwt": "/api/token/refresh/",
                "registro_pasajero": "/api/registro/",
                "buscar_servicios": "/api/servicios/buscar/",
                "ver_asientos_servicio": "/api/servicios/{id}/asientos/",
                "carro_pasajes": "/api/carro-pasajes/",
                "checkout_venta": "/api/ventas/checkout/",
                "mis_boletos": "/api/mis-boletos/",
                "gestion_servicios_admin": "/api/servicios/",
                "cambiar_estado_orden_admin": "/api/ventas/{id}/estado/",
            },
        }

        # Si el cliente solicita formato HTML o navega desde explorador web
        if request.accepted_renderer.format == "html" or "text/html" in request.META.get("HTTP_ACCEPT", ""):
            return render(request, "transporte/footer_base.html", {"info": data})

        return Response(data, status=status.HTTP_200_OK)


class FrontendAppView(APIView):
    """
    Vista de la Aplicación Frontend interactiva.
    Renderiza la interfaz web completa conectada en tiempo real a los endpoints de la API REST.
    Permite explorar viajes, seleccionar asientos visualmente en el bus, gestionar el carro
    persistente en PostgreSQL, ejecutar checkout atómico y emitir boletos con código UUID.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        student_info = getattr(
            settings,
            "STUDENT_INFO",
            {
                "ALUMNO": "Rodrigo Gallardo",
                "SECCION": "AP-N4-C2(E-F)/D",
                "ANIO": 2026,
                "PROYECTO": "Proyecto 4 - Reservas de Pasajes de Buses Interurbanos",
            },
        )
        return render(request, "transporte/app.html", {"info": student_info})


# ==============================================================================
# 2. AUTENTICACIÓN Y ROLES (SIMPLE JWT)
# ==============================================================================
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Endpoint para autenticación de usuarios.
    POST /api/token/
    Retorna access token y refresh token incorporando en el payload cifrado:
    - 'role': 'PASAJERO' o 'ADMIN_FLOTA'.
    - 'username': Nombre de usuario.
    - 'user_id': ID de base de datos.
    """
    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        summary="Iniciar Sesión y Obtener Tokens JWT con Claims de Rol",
        description="Recibe credenciales y emite tokens con claims obligatorios de 'role', 'username' y 'user_id'.",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RegistroUsuarioView(generics.CreateAPIView):
    """
    Endpoint para el autoregistro público de Pasajeros.
    POST /api/registro/
    Crea la cuenta de usuario con rol 'PASAJERO' e inicializa su carro persistente.
    """
    serializer_class = UsuarioRegistroSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Registro Público de Pasajeros",
        description="Permite a nuevos pasajeros registrarse para reservar pasajes e inicializar su carro en PostgreSQL.",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class SuperuserGestionUsuariosView(generics.ListCreateAPIView):
    """
    Endpoint para que el Superusuario consulte y cree usuarios y administradores.
    GET /api/superadmin/usuarios/ -> Listado de usuarios con roles y empresas
    POST /api/superadmin/usuarios/ -> Crear nuevo administrador o pasajero
    """
    queryset = Usuario.objects.all().select_related("empresa").order_by("-date_joined")
    permission_classes = [IsSuperUser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UsuarioAdminCreateSerializer
        return UsuarioAdminListSerializer

    @extend_schema(
        summary="Listar Usuarios del Sistema (Superusuario)",
        description="Obtiene la lista completa de usuarios con sus roles, empresas asociadas y estado.",
        responses={200: UsuarioAdminListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Crear Administrador o Usuario (Superusuario)",
        description="Crea un nuevo usuario asignándole rol (ADMIN_FLOTA o PASAJERO), empresa y permisos de staff.",
        request=UsuarioAdminCreateSerializer,
        responses={201: UsuarioAdminListSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = UsuarioAdminCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()
        return Response(
            UsuarioAdminListSerializer(usuario).data,
            status=status.HTTP_201_CREATED
        )


class SuperuserModificarPrivilegiosView(APIView):
    """
    Endpoint para que el Superusuario conceda o revoque privilegios (rol, empresa, is_staff, is_active).
    PATCH /api/superadmin/usuarios/{id}/privilegios/
    """
    permission_classes = [IsSuperUser]

    @extend_schema(
        summary="Conceder o Revocar Privilegios de Usuario (Superusuario)",
        description="Permite modificar rol (ADMIN_FLOTA / PASAJERO), empresa asignada, flag is_staff y estado is_active.",
        request=UsuarioPrivilegiosUpdateSerializer,
        responses={200: UsuarioAdminListSerializer},
    )
    def patch(self, request, pk, *args, **kwargs):
        try:
            usuario_target = Usuario.objects.get(pk=pk)
        except Usuario.DoesNotExist:
            return Response(
                {"detail": "Usuario no encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Regla de seguridad: el superusuario no puede quitarse sus propios privilegios ni desactivarse a sí mismo
        if usuario_target.id == request.user.id:
            if request.data.get("is_active") is False:
                return Response(
                    {"detail": "No puedes desactivar tu propia cuenta de superusuario."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if request.data.get("rol") and request.data.get("rol") != usuario_target.rol:
                return Response(
                    {"detail": "No puedes cambiar el rol de tu propia cuenta de superusuario desde aquí."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = UsuarioPrivilegiosUpdateSerializer(usuario_target, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        usuario_actualizado = serializer.save()

        if usuario_actualizado.rol == Usuario.ROL_PASAJERO:
            CarroPasajes.objects.get_or_create(usuario=usuario_actualizado)

        return Response(
            UsuarioAdminListSerializer(usuario_actualizado).data,
            status=status.HTTP_200_OK
        )


# ==============================================================================
# 3. CATÁLOGO Y BÚSQUEDA DE SERVICIOS (PÚBLICO)
# ==============================================================================
class ServiciosBuscarView(generics.ListAPIView):
    """
    Endpoint público para búsqueda y filtrado de itinerarios disponibles.
    GET /api/servicios/buscar/
    Utiliza django-filter para filtrar por:
    - origen (ID o nombre parcial)
    - destino (ID o nombre parcial)
    - fecha_salida (YYYY-MM-DD)
    - rango de fechas (fecha_desde, fecha_hasta)
    - precio_max (tarifa máxima)
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = ServicioListSerializer
    filterset_class = ServicioFilter

    def get_queryset(self):
        # Por defecto muestra servicios programados ordenados por hora de salida
        return (
            Servicio.objects.filter(estado=Servicio.ESTADO_PROGRAMADO)
            .select_related("ruta__origen", "ruta__destino", "bus")
            .prefetch_related("bus__asientos", "boletos")
            .order_by("fecha_hora_salida")
        )

    @extend_schema(
        summary="Buscar Catálogo de Servicios con Filtros",
        description="Permite buscar servicios por origen, destino y fecha de salida mediante django-filter.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ServicioAsientosView(APIView):
    """
    Endpoint público para consultar la disponibilidad de asientos de un servicio específico.
    GET /api/servicios/{id}/asientos/
    Calcula en tiempo real qué asientos están disponibles (True) o ya reservados (False).
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Mapa de Asientos y Disponibilidad en Tiempo Real",
        description="Retorna todos los asientos del bus del servicio indicando estado libre/ocupado y tarifa.",
        responses={200: AsientoDisponibilidadSerializer(many=True)},
    )
    def get(self, request, id, *args, **kwargs):
        servicio = get_object_or_404(
            Servicio.objects.select_related("bus", "ruta__origen", "ruta__destino"),
            id=id,
        )
        mapa = ConsultaServicioService.obtener_asientos_disponibles(servicio)
        serializer = AsientoDisponibilidadSerializer(mapa, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==============================================================================
# 4. CARRO DE PASAJES PERSISTENTE (ROL: PASAJERO)
# ==============================================================================
class CarroPasajesView(APIView):
    """
    Endpoint para gestionar el carro persistente del usuario pasajero.
    GET /api/carro-pasajes/: Retorna el carro del usuario, sus ítems y el total calculado.
    POST /api/carro-pasajes/: Agrega un nuevo pasaje (servicio, asiento, datos de ocupante).

    PERSISTENCIA POST-LOGOUT:
    El carro está ligado de forma 1 a 1 al ID del usuario en PostgreSQL,
    por lo que los ítems agregados se conservan intactos ante reconexiones.
    """
    permission_classes = [permissions.IsAuthenticated, IsPasajero]

    @extend_schema(
        summary="Ver Carro de Pasajes Persistente Actual",
        description="Obtiene el carro activo del usuario autenticado con sus ítems guardados en PostgreSQL.",
        responses={200: CarroPasajesSerializer},
    )
    def get(self, request, *args, **kwargs):
        carro, _ = CarroPasajes.objects.get_or_create(usuario=request.user)
        serializer = CarroPasajesSerializer(carro)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Agregar Asiento al Carro de Pasajes",
        description="Agrega un asiento seleccionado al carro con nombre y RUT del pasajero ocupante.",
        request=ItemCarroCreateSerializer,
        responses={201: ItemCarroListSerializer},
    )
    def post(self, request, *args, **kwargs):
        carro, _ = CarroPasajes.objects.get_or_create(usuario=request.user)

        serializer = ItemCarroCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        servicio = serializer.validated_data["servicio"]
        asiento = serializer.validated_data["asiento"]
        nombre = serializer.validated_data["nombre_pasajero"]
        rut = serializer.validated_data["rut_pasajero"]

        # Evitar duplicar el mismo asiento en el carro del usuario
        item_existente = ItemCarro.objects.filter(
            carro=carro,
            servicio=servicio,
            asiento=asiento,
        ).first()

        if item_existente:
            return Response(
                {"detail": "Este asiento ya se encuentra agregado en tu carro de compras."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Crear ítem con persistencia garantizada en PostgreSQL
        item = ItemCarro.objects.create(
            carro=carro,
            servicio=servicio,
            asiento=asiento,
            nombre_pasajero=nombre,
            rut_pasajero=rut,
        )

        salida_serializer = ItemCarroListSerializer(item)
        return Response(salida_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Vaciar Carro de Pasajes",
        description="Elimina todos los pasajes agregados actualmente en el carro persistente del usuario.",
    )
    def delete(self, request, *args, **kwargs):
        carro, _ = CarroPasajes.objects.get_or_create(usuario=request.user)
        eliminados, _ = carro.items.all().delete()
        return Response(
            {"detail": "Carro de pasajes vaciado exitosamente.", "eliminados": eliminados},
            status=status.HTTP_200_OK,
        )


class ItemCarroDeleteView(generics.DestroyAPIView):
    """
    Endpoint para eliminar un ítem específico del carro persistente.
    DELETE /api/carro-pasajes/{item_id}/
    """
    permission_classes = [permissions.IsAuthenticated, IsPasajero]

    def get_queryset(self):
        # Restringe la eliminación únicamente a ítems pertenecientes al carro del usuario
        return ItemCarro.objects.filter(carro__usuario=self.request.user)

    @extend_schema(
        summary="Eliminar Pasaje del Carro de Compras",
        description="Elimina un asiento previamente agregado al carro persistente.",
    )
    def delete(self, request, *args, **kwargs):
        item_id = kwargs.get("pk")
        item = get_object_or_404(self.get_queryset(), pk=item_id)
        item.delete()
        return Response(
            {"detail": "Pasaje eliminado exitosamente del carro de compras."},
            status=status.HTTP_200_OK,
        )


class CarroPasajesBulkView(APIView):
    """
    Endpoint para agregar múltiples pasajes en lote al carro persistente:
    POST /api/carro-pasajes/bulk/
    Permite seleccionar varios asientos (o todos los disponibles) y guardarlos en una sola transacción atómica.
    """
    permission_classes = [permissions.IsAuthenticated, IsPasajero]

    @extend_schema(
        summary="Agregar Múltiples Asientos en Lote al Carro",
        description="Recibe una lista de asientos y ocupantes para agregarlos al carro persistente de una sola vez.",
        request=ItemCarroBulkCreateSerializer,
        responses={201: CarroPasajesSerializer},
    )
    def post(self, request, *args, **kwargs):
        carro, _ = CarroPasajes.objects.get_or_create(usuario=request.user)

        serializer = ItemCarroBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items_data = serializer.validated_data["items"]
        if not items_data:
            return Response(
                {"detail": "No se enviaron asientos para agregar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        items_creados = []
        with transaction.atomic():
            for item_dict in items_data:
                servicio = item_dict["servicio"]
                asiento = item_dict["asiento"]
                nombre = item_dict["nombre_pasajero"]
                rut = item_dict["rut_pasajero"]

                item, _ = ItemCarro.objects.update_or_create(
                    carro=carro,
                    servicio=servicio,
                    asiento=asiento,
                    defaults={
                        "nombre_pasajero": nombre,
                        "rut_pasajero": rut,
                    }
                )
                items_creados.append(item)

        carro.refresh_from_db()
        carro_serializer = CarroPasajesSerializer(carro)
        return Response(
            {
                "mensaje": f"Se agregaron {len(items_creados)} asiento(s) exitosamente a tu carro.",
                "carro": carro_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class CarroLimpiarAgotadosView(APIView):
    """
    Endpoint para depurar asientos del carro que ya fueron comprados por otros usuarios:
    POST o DELETE /api/carro-pasajes/limpiar-agotados/
    """
    permission_classes = [permissions.IsAuthenticated, IsPasajero]

    @extend_schema(
        summary="Limpiar Asientos Agotados del Carro",
        description="Remueve del carro del usuario aquellos asientos que ya fueron adquiridos por otros clientes.",
    )
    def post(self, request, *args, **kwargs):
        return self._limpiar(request)

    def delete(self, request, *args, **kwargs):
        return self._limpiar(request)

    def _limpiar(self, request):
        carro, _ = CarroPasajes.objects.get_or_create(usuario=request.user)
        items = list(carro.items.all())
        eliminados = 0

        with transaction.atomic():
            for it in items:
                ocupado = Boleto.objects.filter(
                    servicio=it.servicio,
                    asiento=it.asiento,
                    orden__estado__in=[OrdenCompra.ESTADO_PAGADO, OrdenCompra.ESTADO_COMPLETADO],
                    activo=True,
                ).exists()

                if ocupado or it.servicio.estado != Servicio.ESTADO_PROGRAMADO:
                    it.delete()
                    eliminados += 1

        carro.refresh_from_db()
        carro_serializer = CarroPasajesSerializer(carro)
        return Response(
            {
                "mensaje": f"Se eliminaron {eliminados} asiento(s) agotados de tu carro.",
                "eliminados": eliminados,
                "carro": carro_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# 5. VENTAS, CHECKOUT ATÓMICO Y BOLETOS (ROL: PASAJERO)
# ==============================================================================
class CheckoutView(APIView):
    """
    Endpoint de confirmación de compra y pago de los pasajes del carro.
    POST /api/ventas/checkout/

    LÓGICA TRANSACCIONAL ACID:
    - Ejecuta `db.transaction.atomic()` con `select_for_update` sobre los asientos.
    - Valida que ninguno de los asientos esté ocupado por otra transacción completada.
    - Si todos están disponibles:
      * Genera la Orden histórica en estado PENDIENTE y la transiciona a PAGADO.
      * Emite los Boletos definitivos asignando a cada uno un código UUID único.
      * Vacía el carro persistente del usuario.
    - Si un asiento ya fue ocupado:
      * Revierte la transacción y retorna código HTTP 400.
    """
    permission_classes = [permissions.IsAuthenticated, IsPasajero]

    @extend_schema(
        summary="Confirmar Compra y Pagar (Checkout Atómico)",
        description="Ejecuta la compra atómica con select_for_update, valida stock, emite boletos con UUID y vacía el carro.",
        responses={201: OrdenCompraSerializer},
    )
    def post(self, request, *args, **kwargs):
        metodo_pago = request.data.get("metodo_pago", OrdenCompra.METODO_WEBPAY)
        orden = VentaService.procesar_checkout(usuario=request.user, metodo_pago=metodo_pago)
        serializer = OrdenCompraSerializer(orden)
        return Response(
            {
                "mensaje": f"¡Pago procesado con éxito vía {orden.get_metodo_pago_display()}! Se han emitido tus boletos de viaje.",
                "orden": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class MisBoletosView(generics.ListAPIView):
    """
    Endpoint para consultar el historial de boletos comprados por el usuario autenticado.
    GET /api/mis-boletos/
    Retorna boletos con su código UUID único, datos de ruta y asiento.
    """
    permission_classes = [permissions.IsAuthenticated, IsPasajero]
    serializer_class = BoletoSerializer

    def get_queryset(self):
        return (
            Boleto.objects.filter(orden__usuario=self.request.user)
            .select_related("orden", "servicio__ruta__origen", "servicio__ruta__destino", "servicio__bus", "asiento")
            .order_by("-fecha_emision")
        )

    @extend_schema(
        summary="Historial de Boletos Comprados por el Pasajero",
        description="Retorna todos los pasajes adquiridos por el usuario actual con sus códigos UUID.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ==============================================================================
# 6. GESTIÓN ADMINISTRATIVA DE FLOTA Y VENTAS (ROL: ADMIN_FLOTA)
# ==============================================================================
class ServiciosViewSet(viewsets.ModelViewSet):
    """
    ViewSet para la gestión administrativa de itinerarios y servicios:
    - POST /api/servicios/ (Crear servicio)
    - PUT/PATCH /api/servicios/{id}/ (Modificar servicio)
    - DELETE /api/servicios/{id}/ (Eliminar servicio)
    - GET /api/servicios/ (Listar servicios)
    - GET /api/servicios/{id}/ (Detalle del servicio)

    Permisos:
    - Lectura (GET): Pública o clientes autenticados.
    - Mutación (POST, PUT, DELETE): Exclusiva para Administradores de Flota.
    """
    permission_classes = [IsAdminFlotaOrReadOnly]

    def get_queryset(self):
        return (
            Servicio.objects.all()
            .select_related("ruta__origen", "ruta__destino", "bus")
            .prefetch_related("bus__asientos", "boletos")
            .order_by("-fecha_hora_salida")
        )

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return ServicioListSerializer
        return ServicioCreateUpdateSerializer

    @extend_schema(
        summary="Gestión de Servicios e Itinerarios (Admin Flota)",
        description="Permite a los administradores de flota crear, listar, modificar y eliminar itinerarios.",
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


class CambioEstadoOrdenView(APIView):
    """
    Endpoint administrativo para actualizar el estado de una orden:
    PATCH /api/ventas/{id}/estado/
    Permite cambiar a 'CANCELADO', 'COMPLETADO', 'PAGADO', etc.

    REVERSIÓN DE INVENTARIO:
    Al actualizar una orden a 'CANCELADO', los boletos asociados se desactivan
    de inmediato (activo=False), liberando los asientos en el catálogo público.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminFlota]

    @extend_schema(
        summary="Cambiar Estado de una Orden (Admin Flota)",
        description="Actualiza el estado de una orden. Si pasa a CANCELADO, libera automáticamente los asientos.",
        request=CambioEstadoOrdenSerializer,
        responses={200: OrdenCompraSerializer},
    )
    def patch(self, request, id, *args, **kwargs):
        orden = get_object_or_404(OrdenCompra, id=id)

        serializer = CambioEstadoOrdenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nuevo_estado = serializer.validated_data["estado"]

        orden_actualizada = GestionOrdenService.cambiar_estado(
            orden=orden,
            nuevo_estado=nuevo_estado,
            usuario_admin=request.user,
        )

        salida_serializer = OrdenCompraSerializer(orden_actualizada)
        return Response(
            {
                "mensaje": f"Estado de la orden #{orden.id} actualizado exitosamente a '{orden_actualizada.get_estado_display()}'.",
                "orden": salida_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ==============================================================================
# 7. VIEWSETS COMPLEMENTARIOS DE INFRAESTRUCTURA (CRUDs ADMIN DE FLOTA)
# ==============================================================================
class CiudadViewSet(viewsets.ModelViewSet):
    """CRUD para ciudades y terminales de origen y destino."""
    queryset = Ciudad.objects.all().order_by("nombre")
    serializer_class = CiudadSerializer
    permission_classes = [IsAdminFlotaOrReadOnly]


class BusViewSet(viewsets.ModelViewSet):
    """CRUD para buses de la flota de transporte."""
    queryset = Bus.objects.prefetch_related("asientos").all().order_by("patente")
    serializer_class = BusSerializer
    permission_classes = [IsAdminFlotaOrReadOnly]

    @action(detail=True, methods=["patch"], url_path="estado-operativo", permission_classes=[permissions.IsAuthenticated, IsAdminFlota])
    def cambiar_estado_operativo(self, request, pk=None):
        """Permite a un administrador cambiar el estado operativo de una máquina (Bus)."""
        bus = self.get_object()
        nuevo_estado = request.data.get("estado_operativo")
        if nuevo_estado not in dict(Bus.ESTADOS_OPERATIVOS_CHOICES):
            return Response(
                {"detail": f"Estado no válido. Opciones: {list(dict(Bus.ESTADOS_OPERATIVOS_CHOICES).keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bus.estado_operativo = nuevo_estado
        bus.save(update_fields=["estado_operativo"])
        return Response(
            {
                "mensaje": f"Estado de la máquina {bus.patente} actualizado a '{bus.get_estado_operativo_display()}'.",
                "bus": BusSerializer(bus).data,
            },
            status=status.HTTP_200_OK,
        )


class AsientoViewSet(viewsets.ModelViewSet):
    """CRUD para asientos asignados a cada bus."""
    queryset = Asiento.objects.select_related("bus").all().order_by("bus", "piso", "numero")
    serializer_class = AsientoSerializer
    permission_classes = [IsAdminFlotaOrReadOnly]


class RutaViewSet(viewsets.ModelViewSet):
    """CRUD para rutas de transporte."""
    queryset = Ruta.objects.select_related("origen", "destino").all().order_by("origen__nombre")
    serializer_class = RutaSerializer
    permission_classes = [IsAdminFlotaOrReadOnly]


class EmpresaTransporteViewSet(viewsets.ModelViewSet):
    """CRUD y panel analítico para Empresas de Transporte / Tenants."""
    queryset = EmpresaTransporte.objects.all().order_by("nombre")
    serializer_class = EmpresaTransporteSerializer
    permission_classes = [IsAdminFlotaOrReadOnly]

    @action(detail=True, methods=["get"], url_path="movimientos", permission_classes=[permissions.AllowAny])
    def movimientos(self, request, pk=None):
        """
        Retorna el reporte de movimientos de la empresa (Tenant):
        - Máquinas (buses): ocupadas (en ruta), disponibles (en terminal), en taller.
        - Asientos: ocupados vs disponibles por servicio.
        - Ventas y recaudación total.
        """
        empresa = self.get_object()
        return self._obtener_reporte_movimientos(empresa)

    @action(detail=False, methods=["get"], url_path="mi-empresa", permission_classes=[permissions.IsAuthenticated])
    def mi_empresa(self, request):
        """
        Retorna los movimientos de la empresa asignada al usuario actual (ADMIN_FLOTA).
        """
        empresa = getattr(request.user, "empresa", None)
        if not empresa:
            empresa = EmpresaTransporte.objects.filter(activo=True).first()
        if not empresa:
            return Response({"detail": "No hay empresas registradas."}, status=status.HTTP_404_NOT_FOUND)
        return self._obtener_reporte_movimientos(empresa)

    def _obtener_reporte_movimientos(self, empresa):
        # 1. Buses de la flota de la empresa
        buses = empresa.buses.all().prefetch_related("asientos", "servicios")
        buses_data = []
        conteo_estados = {
            Bus.ESTADO_OPERATIVO_DISPONIBLE: 0,
            Bus.ESTADO_OPERATIVO_EN_RUTA: 0,
            Bus.ESTADO_OPERATIVO_MANTENIMIENTO: 0,
            Bus.ESTADO_OPERATIVO_FUERA_SERVICIO: 0,
        }
        for b in buses:
            conteo_estados[b.estado_operativo] = conteo_estados.get(b.estado_operativo, 0) + 1
            serv_activo = b.servicios.filter(
                estado__in=[Servicio.ESTADO_PROGRAMADO, Servicio.ESTADO_EN_RUTA]
            ).order_by("fecha_hora_salida").first()

            servicio_desc = "Sin servicio asignado (En Terminal)"
            if serv_activo:
                salida_str = serv_activo.fecha_hora_salida.strftime("%d/%m %H:%M")
                servicio_desc = f"{serv_activo.ruta.origen.nombre} ➔ {serv_activo.ruta.destino.nombre} ({salida_str})"

            buses_data.append({
                "id": b.id,
                "patente": b.patente,
                "modelo": b.modelo,
                "marca": b.marca,
                "capacidad_total": b.capacidad_total,
                "estado_operativo": b.estado_operativo,
                "estado_operativo_display": b.get_estado_operativo_display(),
                "servicio_actual": servicio_desc,
                "activo": b.activo,
            })

        # 2. Servicios de la empresa y desglose de asientos
        servicios = (
            empresa.servicios.select_related("ruta__origen", "ruta__destino", "bus")
            .prefetch_related("boletos__asiento")
            .order_by("fecha_hora_salida")
        )
        servicios_data = []
        total_recaudacion = Decimal("0.00")
        total_boletos_vendidos = 0

        for s in servicios:
            asientos_totales = s.bus.capacidad_total
            boletos_activos = s.boletos.filter(
                orden__estado__in=[OrdenCompra.ESTADO_PAGADO, OrdenCompra.ESTADO_COMPLETADO],
                activo=True,
            )
            asientos_ocupados = boletos_activos.count()
            asientos_libres = max(0, asientos_totales - asientos_ocupados)
            porcentaje_ocupacion = round((asientos_ocupados / asientos_totales * 100), 1) if asientos_totales > 0 else 0
            recaudacion_servicio = sum((b.precio_pagado for b in boletos_activos), Decimal("0.00"))
            total_recaudacion += recaudacion_servicio
            total_boletos_vendidos += asientos_ocupados

            # Lista de pasajeros a bordo
            pasajeros_lista = []
            for bol in boletos_activos:
                pasajeros_lista.append({
                    "id": bol.id,
                    "asiento_numero": bol.asiento.numero,
                    "asiento_tipo": bol.asiento.get_tipo_display(),
                    "nombre_pasajero": bol.nombre_pasajero,
                    "rut_pasajero": bol.rut_pasajero,
                    "codigo_uuid": str(bol.codigo_uuid),
                    "precio_pagado": bol.precio_pagado,
                    "estado_embarque": bol.estado_embarque,
                    "estado_embarque_display": bol.get_estado_embarque_display(),
                })

            servicios_data.append({
                "id": s.id,
                "ruta": f"{s.ruta.origen.nombre} ➔ {s.ruta.destino.nombre}",
                "origen": s.ruta.origen.nombre,
                "destino": s.ruta.destino.nombre,
                "fecha_hora_salida": s.fecha_hora_salida.isoformat(),
                "fecha_hora_llegada": s.fecha_hora_llegada.isoformat() if s.fecha_hora_llegada else None,
                "bus_patente": s.bus.patente,
                "bus_modelo": s.bus.modelo,
                "estado": s.estado,
                "estado_display": s.get_estado_display(),
                "asientos_totales": asientos_totales,
                "asientos_ocupados": asientos_ocupados,
                "asientos_libres": asientos_libres,
                "porcentaje_ocupacion": porcentaje_ocupacion,
                "recaudacion_servicio": recaudacion_servicio,
                "pasajeros": pasajeros_lista,
            })

        return Response({
            "empresa": {
                "id": empresa.id,
                "nombre": empresa.nombre,
                "rut": empresa.rut,
                "slug": empresa.slug,
                "color_hex": empresa.color_hex,
                "activo": empresa.activo,
            },
            "kpis": {
                "total_buses": len(buses_data),
                "buses_disponibles": conteo_estados.get(Bus.ESTADO_OPERATIVO_DISPONIBLE, 0),
                "buses_en_ruta": conteo_estados.get(Bus.ESTADO_OPERATIVO_EN_RUTA, 0),
                "buses_mantenimiento": conteo_estados.get(Bus.ESTADO_OPERATIVO_MANTENIMIENTO, 0),
                "buses_fuera_servicio": conteo_estados.get(Bus.ESTADO_OPERATIVO_FUERA_SERVICIO, 0),
                "total_servicios": len(servicios_data),
                "total_boletos_vendidos": total_boletos_vendidos,
                "total_recaudado_clp": total_recaudacion,
            },
            "buses": buses_data,
            "servicios": servicios_data,
        }, status=status.HTTP_200_OK)


class BoletoEmbarqueView(APIView):
    """
    Endpoint administrativo para actualizar el estado de embarque de un boleto emitido:
    PATCH /api/boletos/{uuid}/embarque/
    Permite marcar al pasajero como 'EMBARCADO' o 'NO_SHOW'.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminFlota]

    def patch(self, request, codigo_uuid, *args, **kwargs):
        boleto = get_object_or_404(Boleto, codigo_uuid=codigo_uuid)
        nuevo_embarque = request.data.get("estado_embarque")
        if nuevo_embarque not in dict(Boleto.ESTADOS_EMBARQUE_CHOICES):
            return Response(
                {"detail": f"Estado de embarque no válido. Opciones: {list(dict(Boleto.ESTADOS_EMBARQUE_CHOICES).keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        boleto.estado_embarque = nuevo_embarque
        boleto.save(update_fields=["estado_embarque"])
        return Response(
            {
                "mensaje": f"Estado de embarque de {boleto.nombre_pasajero} actualizado a '{boleto.get_estado_embarque_display()}'.",
                "boleto": BoletoSerializer(boleto).data,
            },
            status=status.HTTP_200_OK,
        )

