"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
MÓDULO: PRUEBAS AUTOMATIZADAS UNITARIAS Y DE INTEGRACIÓN (tests.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
================================================================================
Esta suite de pruebas valida formalmente los 6 criterios clave de la pauta:
1. Autenticación SimpleJWT y Claims de Rol en el Token ('role', 'username', 'user_id').
2. Permisos y Control de Acceso Basado en Roles (RBAC: Pasajero vs Administrador).
3. Búsqueda y Filtrado de Catálogo con django-filter.
4. Carro de Compras Persistente en Base de Datos (post-logout).
5. Transacción Atómica de Checkout con Emisión de Boletos con UUID.
6. Reversión Automática de Inventario (liberación de asientos) ante CANCELADO.
7. Endpoint Informativo y Footer del Estudiante (Año 2026).
================================================================================
"""

from decimal import Decimal
from datetime import timedelta
import jwt
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from transporte.models import (
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


class SistemaBusesTestCase(APITestCase):
    """
    Suite integral de pruebas para la evaluación EVA-2.
    """

    def setUp(self):
        # 1. Crear usuarios de prueba con roles explícitos
        self.usuario_admin = Usuario.objects.create_user(
            username="admin_test",
            password="password123",
            email="admin@test.cl",
            first_name="Admin",
            last_name="Flota",
            rol=Usuario.ROL_ADMIN_FLOTA,
            is_staff=True,
        )

        self.usuario_pasajero1 = Usuario.objects.create_user(
            username="pasajero_test1",
            password="password123",
            email="pasajero1@test.cl",
            first_name="Juan",
            last_name="Perez",
            rut="18.111.222-3",
            rol=Usuario.ROL_PASAJERO,
        )

        self.usuario_pasajero2 = Usuario.objects.create_user(
            username="pasajero_test2",
            password="password123",
            email="pasajero2@test.cl",
            first_name="Maria",
            last_name="Lopez",
            rut="19.444.555-6",
            rol=Usuario.ROL_PASAJERO,
        )

        # Superusuario de prueba
        self.superuser = Usuario.objects.create_superuser(
            username="superadmin_test",
            password="password123",
            email="superadmin@test.cl",
            first_name="Super",
            last_name="User",
            rol=Usuario.ROL_ADMIN_FLOTA,
        )

        # Empresa / Tenant de prueba
        self.empresa_turbus = EmpresaTransporte.objects.create(
            nombre="Empresa Setup Test",
            rut="76.111.222-3",
            slug="empresa-setup-test",
            color_hex="#16a34a",
            activo=True,
        )

        # 2. Ciudades y Rutas
        self.ciudad_stgo = Ciudad.objects.create(
            nombre="Santiago", terminal="Terminal Sur", region="Metropolitana"
        )
        self.ciudad_valpo = Ciudad.objects.create(
            nombre="Valparaíso", terminal="Terminal Rodoviario", region="Valparaíso"
        )
        self.ruta_stgo_valpo = Ruta.objects.create(
            origen=self.ciudad_stgo,
            destino=self.ciudad_valpo,
            distancia_km=120,
            duracion_estimada_minutos=90,
        )

        # 3. Bus y Asientos
        self.bus = Bus.objects.create(
            patente="TEST-99",
            modelo="Marcopolo DD",
            marca="Scania",
            capacidad_total=4,
            activo=True,
        )
        self.asiento_1 = Asiento.objects.create(
            bus=self.bus, numero=1, tipo=Asiento.TIPO_CAMA, piso=1
        )
        self.asiento_2 = Asiento.objects.create(
            bus=self.bus, numero=2, tipo=Asiento.TIPO_CAMA, piso=1
        )
        self.asiento_3 = Asiento.objects.create(
            bus=self.bus, numero=3, tipo=Asiento.TIPO_SEMICAMA, piso=2
        )
        self.asiento_4 = Asiento.objects.create(
            bus=self.bus, numero=4, tipo=Asiento.TIPO_SEMICAMA, piso=2
        )

        # 4. Servicio / Itinerario Programado
        self.hora_salida = timezone.now().replace(microsecond=0) + timedelta(days=2)
        self.hora_llegada = self.hora_salida + timedelta(hours=2)
        self.servicio = Servicio.objects.create(
            ruta=self.ruta_stgo_valpo,
            bus=self.bus,
            fecha_hora_salida=self.hora_salida,
            fecha_hora_llegada=self.hora_llegada,
            precio_semicama=Decimal("6000.00"),
            precio_cama=Decimal("9000.00"),
            estado=Servicio.ESTADO_PROGRAMADO,
        )

    # ==========================================================================
    # TEST 1: AUTENTICACIÓN JWT Y CUSTOM CLAIMS DE ROL
    # ==========================================================================
    def test_01_login_jwt_contiene_claims_obligatorios_de_rol(self):
        """Verifica que el login retorne tokens con claims 'role', 'username' y 'user_id'."""
        url = reverse("token-obtain-pair")
        payload = {"username": "pasajero_test1", "password": "password123"}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["role"], "PASAJERO")
        self.assertEqual(response.data["username"], "pasajero_test1")

        # Decodificar el token de acceso para comprobar el payload criptográfico
        token_decoded = jwt.decode(
            response.data["access"],
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_signature": True},
        )
        self.assertEqual(token_decoded["role"], "PASAJERO")
        self.assertEqual(token_decoded["username"], "pasajero_test1")
        self.assertEqual(token_decoded["user_id"], self.usuario_pasajero1.id)

    # ==========================================================================
    # TEST 2: CATÁLOGO PÚBLICO Y FILTRADO CON DJANGO-FILTER
    # ==========================================================================
    def test_02_buscar_servicios_publico_con_django_filter(self):
        """Verifica la búsqueda pública de servicios por origen, destino y fecha."""
        url = reverse("servicios-buscar")

        # Búsqueda general sin autenticación (pública)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

        # Búsqueda filtrada por ID de origen
        response_filtro = self.client.get(f"{url}?origen={self.ciudad_stgo.id}&destino={self.ciudad_valpo.id}")
        self.assertEqual(response_filtro.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_filtro.data["results"]), 1)

    # ==========================================================================
    # TEST 3: DISPONIBILIDAD DE ASIENTOS EN TIEMPO REAL
    # ==========================================================================
    def test_03_mapa_disponibilidad_asientos(self):
        """Verifica el cálculo de disponibilidad de asientos libres para un servicio."""
        url = reverse("servicio-asientos", kwargs={"id": self.servicio.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)
        for asiento in response.data:
            self.assertTrue(asiento["disponible"])

    # ==========================================================================
    # TEST 4: CARRO PERSISTENTE (RELACIÓN 1 A 1 EN POSTGRESQL POST-LOGOUT)
    # ==========================================================================
    def test_04_carro_pasajes_persistente_en_base_de_datos(self):
        """Verifica que los asientos agregados al carro persisten en base de datos."""
        self.client.force_authenticate(user=self.usuario_pasajero1)

        url = reverse("carro-pasajes")
        item_data = {
            "servicio": self.servicio.id,
            "asiento": self.asiento_1.id,
            "nombre_pasajero": "Juan Pérez",
            "rut_pasajero": "18.111.222-3",
        }
        res_post = self.client.post(url, item_data, format="json")
        self.assertEqual(res_post.status_code, status.HTTP_201_CREATED)

        # Simular logout (desautenticación) y posterior reconexión
        self.client.force_authenticate(user=None)
        self.client.force_authenticate(user=self.usuario_pasajero1)

        # Consultar el carro: debe persistir en base de datos
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_get.data["items"]), 1)
        self.assertEqual(Decimal(str(res_get.data["total"])), Decimal("9000.00"))

        # El asiento NO debe estar bloqueado en el catálogo solo por estar en el carro
        url_asientos = reverse("servicio-asientos", kwargs={"id": self.servicio.id})
        res_asientos = self.client.get(url_asientos)
        asiento_1_info = next(a for a in res_asientos.data if a["id"] == self.asiento_1.id)
        self.assertTrue(asiento_1_info["disponible"], "El asiento no debe bloquearse al estar en el carro.")

    # ==========================================================================
    # TEST 5: CHECKOUT ATÓMICO, VALIDACIÓN DE CONCURRENCIA Y BOLETOS CON UUID
    # ==========================================================================
    def test_05_checkout_atomico_emision_boletos_uuid_y_descuento_inventario(self):
        """Verifica la transacción de checkout: descuento de stock, emisión de UUID y vaciado de carro."""
        self.client.force_authenticate(user=self.usuario_pasajero1)

        # 1. Agregar asiento al carro
        self.client.post(
            reverse("carro-pasajes"),
            {
                "servicio": self.servicio.id,
                "asiento": self.asiento_1.id,
                "nombre_pasajero": "Juan Pérez",
                "rut_pasajero": "18.111.222-3",
            },
            format="json",
        )

        # 2. Ejecutar checkout
        url_checkout = reverse("ventas-checkout")
        res_checkout = self.client.post(url_checkout, format="json")
        self.assertEqual(res_checkout.status_code, status.HTTP_201_CREATED)

        orden_id = res_checkout.data["orden"]["id"]
        orden = OrdenCompra.objects.get(id=orden_id)
        self.assertEqual(orden.estado, OrdenCompra.ESTADO_PAGADO)
        self.assertEqual(orden.boletos.count(), 1)

        # Verificar emisión de UUID irrepetible
        boleto = orden.boletos.first()
        self.assertIsNotNone(boleto.codigo_uuid)
        self.assertTrue(boleto.activo)

        # 3. El carro ahora debe estar vacío
        res_carro = self.client.get(reverse("carro-pasajes"))
        self.assertEqual(len(res_carro.data["items"]), 0)

        # 4. El asiento ahora SÍ debe figurar como OCUPADO (disponible = False)
        res_asientos = self.client.get(reverse("servicio-asientos", kwargs={"id": self.servicio.id}))
        asiento_1_info = next(a for a in res_asientos.data if a["id"] == self.asiento_1.id)
        self.assertFalse(asiento_1_info["disponible"], "El asiento debe figurar ocupado tras el pago.")

        # 5. INTENTO DE COMPRA CONCURRENTE DEL MISMO ASIENTO POR OTRO USUARIO
        self.client.force_authenticate(user=self.usuario_pasajero2)
        # Meter al carro (el usuario 2 lo tenía previamente en su carro)
        carro2, _ = CarroPasajes.objects.get_or_create(usuario=self.usuario_pasajero2)
        ItemCarro.objects.create(
            carro=carro2,
            servicio=self.servicio,
            asiento=self.asiento_1,
            nombre_pasajero="María López",
            rut_pasajero="19.444.555-6",
            precio_unitario=Decimal("9000.00"),
        )
        # Al ejecutar el checkout debe ser rechazado con 400
        res_checkout_duplicado = self.client.post(url_checkout, format="json")
        self.assertEqual(res_checkout_duplicado.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("fueron adquiridos", str(res_checkout_duplicado.data))

    # ==========================================================================
    # TEST 6: CANCELACIÓN DE ORDEN Y REVERSIÓN AUTOMÁTICA DE INVENTARIO
    # ==========================================================================
    def test_06_cancelacion_orden_libera_asientos_automaticamente(self):
        """Verifica que al cancelar una orden, los asientos se restituyan al inventario."""
        # Comprar asiento 2
        self.client.force_authenticate(user=self.usuario_pasajero1)
        self.client.post(
            reverse("carro-pasajes"),
            {
                "servicio": self.servicio.id,
                "asiento": self.asiento_2.id,
                "nombre_pasajero": "Pedro Perez",
                "rut_pasajero": "18.333.444-5",
            },
            format="json",
        )
        res_chk = self.client.post(reverse("ventas-checkout"), format="json")
        orden_id = res_chk.data["orden"]["id"]

        # Verificar que el asiento 2 no está disponible
        res_asientos = self.client.get(reverse("servicio-asientos", kwargs={"id": self.servicio.id}))
        asiento_2_info = next(a for a in res_asientos.data if a["id"] == self.asiento_2.id)
        self.assertFalse(asiento_2_info["disponible"])

        # Administrador de flota cancela la orden: PATCH /api/ventas/{id}/estado/
        self.client.force_authenticate(user=self.usuario_admin)
        url_estado = reverse("orden-cambio-estado", kwargs={"id": orden_id})
        res_patch = self.client.patch(url_estado, {"estado": "CANCELADO"}, format="json")
        self.assertEqual(res_patch.status_code, status.HTTP_200_OK)

        # REVERSIÓN DE INVENTARIO: El asiento 2 vuelve a estar inmediatamente disponible
        res_asientos_post = self.client.get(reverse("servicio-asientos", kwargs={"id": self.servicio.id}))
        asiento_2_info_post = next(a for a in res_asientos_post.data if a["id"] == self.asiento_2.id)
        self.assertTrue(asiento_2_info_post["disponible"], "El asiento debe quedar disponible tras cancelar la orden.")

    # ==========================================================================
    # TEST 7: MATRIZ DE PERMISOS RBAC (RESTRICCIÓN POR ROL)
    # ==========================================================================
    def test_07_restriccion_de_permisos_rbac(self):
        """Verifica que un Pasajero NO pueda crear servicios ni cambiar estados de orden."""
        self.client.force_authenticate(user=self.usuario_pasajero1)

        # Pasajero intentando crear un servicio
        url_servicios = reverse("servicio-admin-list")
        res_crear = self.client.post(url_servicios, {"precio_semicama": 5000}, format="json")
        self.assertEqual(res_crear.status_code, status.HTTP_403_FORBIDDEN)

        # Pasajero intentando cambiar estado de una orden
        url_estado = reverse("orden-cambio-estado", kwargs={"id": 1})
        res_estado = self.client.patch(url_estado, {"estado": "CANCELADO"}, format="json")
        self.assertEqual(res_estado.status_code, status.HTTP_403_FORBIDDEN)

    # ==========================================================================
    # TEST 8: FOOTER BASE Y DATOS VISIBLES DEL ALUMNO (EVA-2)
    # ==========================================================================
    def test_08_footer_base_con_datos_del_alumno(self):
        """Verifica que la vista base exponga los datos del alumno y año 2026."""
        url = reverse("api-info-footer")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("alumno", response.data)
        self.assertIn("seccion", response.data)
        self.assertEqual(response.data["anio"], 2026)
        self.assertEqual(response.data["documentacion_swagger"], "/api/docs/")

    # ==========================================================================
    # TEST 9: REGISTRO DE CUENTA DE CLIENTE Y COMPRA INMEDIATA
    # ==========================================================================
    def test_09_registro_cliente_publico_e_inicio_sesion(self):
        """Verifica que un nuevo cliente pueda registrarse e iniciar sesión de inmediato."""
        url_reg = reverse("registro-pasajero")
        payload = {
            "username": "cliente_nuevo_2026",
            "password": "passwordSeguro123",
            "email": "cliente@chile.cl",
            "first_name": "Nuevo",
            "last_name": "Pasajero",
            "rut": "20.123.456-7",
            "telefono": "+56987654321",
        }
        res_reg = self.client.post(url_reg, payload, format="json")
        self.assertEqual(res_reg.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_reg.data["username"], "cliente_nuevo_2026")
        self.assertEqual(res_reg.data["rol"], "PASAJERO")

        # Verificar que su carro persistente fue creado en PostgreSQL
        usuario_creado = Usuario.objects.get(username="cliente_nuevo_2026")
        self.assertTrue(CarroPasajes.objects.filter(usuario=usuario_creado).exists())

        # Iniciar sesión inmediatamente con las credenciales creadas
        url_token = reverse("token-obtain-pair")
        res_login = self.client.post(
            url_token,
            {"username": "cliente_nuevo_2026", "password": "passwordSeguro123"},
            format="json",
        )
        self.assertEqual(res_login.status_code, status.HTTP_200_OK)
        self.assertIn("access", res_login.data)
        self.assertEqual(res_login.data["role"], "PASAJERO")

    # ==========================================================================
    # TEST 10: MOVIMIENTOS DE TENANT (MÁQUINAS OCUPADAS, ASIENTOS Y RECAUDACIÓN)
    # ==========================================================================
    def test_10_movimientos_tenant_empresa_y_estados_operativos(self):
        """Verifica el endpoint de movimientos de la compañía de viajes (Multi-Tenant)."""
        empresa = EmpresaTransporte.objects.create(
            nombre="Turbus Test",
            rut="76.999.888-1",
            slug="turbus-test",
            color_hex="#16a34a",
        )
        self.bus.empresa = empresa
        self.bus.estado_operativo = Bus.ESTADO_OPERATIVO_EN_RUTA
        self.bus.save()

        self.servicio.empresa = empresa
        self.servicio.save()

        # Emitir un boleto para simular ocupación y ventas
        orden = OrdenCompra.objects.create(
            usuario=self.usuario_pasajero1,
            total=self.servicio.precio_cama,
            estado=OrdenCompra.ESTADO_PAGADO,
            metodo_pago=OrdenCompra.METODO_WEBPAY,
        )
        Boleto.objects.create(
            orden=orden,
            servicio=self.servicio,
            asiento=self.asiento_1,
            nombre_pasajero="Pasajero Test",
            rut_pasajero="18.999.888-7",
            precio_pagado=self.servicio.precio_cama,
            estado_embarque=Boleto.ESTADO_EMBARQUE_EMBARCADO,
            activo=True,
        )

        # Consultar endpoint de movimientos de la empresa
        url = reverse("empresa-movimientos", kwargs={"pk": empresa.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["empresa"]["slug"], "turbus-test")

        # Comprobar KPIs de máquinas y asientos
        kpis = response.data["kpis"]
        self.assertEqual(kpis["total_buses"], 1)
        self.assertEqual(kpis["buses_en_ruta"], 1)
        self.assertEqual(kpis["total_boletos_vendidos"], 1)
        self.assertEqual(Decimal(str(kpis["total_recaudado_clp"])), Decimal("9000.00"))

        # Comprobar detalle de servicios y pasajeros a bordo
        servicios_list = response.data["servicios"]
        self.assertEqual(len(servicios_list), 1)
        self.assertEqual(servicios_list[0]["asientos_ocupados"], 1)
        self.assertEqual(servicios_list[0]["asientos_libres"], 3)
        self.assertEqual(servicios_list[0]["pasajeros"][0]["estado_embarque"], "EMBARCADO")

    # ==========================================================================
    # TEST 11: CHOICES ADICIONALES DE MÉTODO DE PAGO Y EMBARQUE
    # ==========================================================================
    def test_11_choices_adicionales_metodo_pago_y_embarque(self):
        """Verifica la persistencia de los nuevos CHOICES en OrdenCompra y Boleto."""
        orden = OrdenCompra.objects.create(
            usuario=self.usuario_pasajero1,
            total=Decimal("15000.00"),
            estado=OrdenCompra.ESTADO_PAGADO,
            metodo_pago=OrdenCompra.METODO_TRANSFERENCIA,
        )
        self.assertEqual(orden.metodo_pago, "TRANSFERENCIA")
        self.assertEqual(orden.get_metodo_pago_display(), "Transferencia Bancaria")

        boleto = Boleto.objects.create(
            orden=orden,
            servicio=self.servicio,
            asiento=self.asiento_2,
            nombre_pasajero="Test Pasajero",
            rut_pasajero="17.222.333-4",
            precio_pagado=Decimal("15000.00"),
            estado_embarque=Boleto.ESTADO_EMBARQUE_NO_SHOW,
            activo=True,
        )
        self.assertEqual(boleto.estado_embarque, "NO_SHOW")
        self.assertEqual(boleto.get_estado_embarque_display(), "No se Presentó (No Show)")

    # ==========================================================================
    # TEST 12: SELECCIÓN MÚLTIPLE DE ASIENTOS Y AGREGADO EN LOTE (BULK)
    # ==========================================================================
    def test_12_seleccion_multiple_bulk_carro(self):
        """Verifica que un usuario pueda agregar múltiples asientos al carro en una sola petición."""
        self.client.force_authenticate(user=self.usuario_pasajero1)
        url_bulk = reverse("carro-pasajes-bulk")

        payload = {
            "items": [
                {
                    "servicio": self.servicio.id,
                    "asiento": self.asiento_1.id,
                    "nombre_pasajero": "Rodrigo Gallardo",
                    "rut_pasajero": "19.876.543-2",
                },
                {
                    "servicio": self.servicio.id,
                    "asiento": self.asiento_2.id,
                    "nombre_pasajero": "Pasajero Acompañante",
                    "rut_pasajero": "18.111.222-3",
                },
            ]
        }
        res = self.client.post(url_bulk, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["carro"]["cantidad_items"], 2)
        self.assertFalse(res.data["carro"]["tiene_items_agotados"])

    # ==========================================================================
    # TEST 13: DETECCIÓN DE ASIENTOS AGOTADOS EN CARRO Y LIMPIEZA AUTOMÁTICA
    # ==========================================================================
    def test_13_deteccion_asientos_agotados_en_carro_y_limpieza(self):
        """
        Verifica el escenario de concurrencia:
        1. Pasajero 1 agrega un asiento a su carro.
        2. Pasajero 2 compra ese asiento directamente.
        3. El carro del Pasajero 1 detecta 'esta_disponible: False' y 'tiene_items_agotados: True'.
        4. Pasajero 1 invoca 'limpiar-agotados' y su carro queda saneado.
        """
        # 1. Pasajero 1 agrega asiento 1 a su carro persistente
        self.client.force_authenticate(user=self.usuario_pasajero1)
        self.client.post(
            reverse("carro-pasajes"),
            {
                "servicio": self.servicio.id,
                "asiento": self.asiento_1.id,
                "nombre_pasajero": "Rodrigo Gallardo",
                "rut_pasajero": "19.876.543-2",
            },
            format="json",
        )

        # 2. Pasajero 2 compra y paga ese mismo asiento 1 directamente
        self.client.force_authenticate(user=self.usuario_pasajero2)
        self.client.post(
            reverse("carro-pasajes"),
            {
                "servicio": self.servicio.id,
                "asiento": self.asiento_1.id,
                "nombre_pasajero": "Comprador Veloz",
                "rut_pasajero": "15.999.888-7",
            },
            format="json",
        )
        res_chk = self.client.post(reverse("ventas-checkout"), format="json")
        self.assertEqual(res_chk.status_code, status.HTTP_201_CREATED)

        # 3. Pasajero 1 consulta su carro: debe marcar que el asiento ya está agotado / ocupado por otro
        self.client.force_authenticate(user=self.usuario_pasajero1)
        res_carro = self.client.get(reverse("carro-pasajes"))
        self.assertEqual(res_carro.status_code, status.HTTP_200_OK)
        self.assertTrue(res_carro.data["tiene_items_agotados"])
        self.assertEqual(res_carro.data["cantidad_items_agotados"], 1)
        item_conflicto = res_carro.data["items"][0]
        self.assertFalse(item_conflicto["esta_disponible"])
        self.assertIn("ya comprado", item_conflicto["motivo_no_disponible"])

        # 4. Pasajero 1 ejecuta la limpieza de agotados
        res_limpiar = self.client.post(reverse("carro-limpiar-agotados"))
        self.assertEqual(res_limpiar.status_code, status.HTTP_200_OK)
        self.assertEqual(res_limpiar.data["eliminados"], 1)
        self.assertEqual(res_limpiar.data["carro"]["cantidad_items"], 0)

    # ==========================================================================
    # TEST 14: VACIAR CARRO DE PASAJES COMPLETO (DELETE /api/carro-pasajes/)
    # ==========================================================================
    def test_14_vaciar_carro_completo_con_delete(self):
        """Verifica que un pasajero pueda vaciar todo su carro con DELETE /api/carro-pasajes/."""
        self.client.force_authenticate(user=self.usuario_pasajero1)
        self.client.post(
            reverse("carro-pasajes"),
            {
                "servicio": self.servicio.id,
                "asiento": self.asiento_1.id,
                "nombre_pasajero": "Rodrigo Gallardo",
                "rut_pasajero": "19.876.543-2",
            },
            format="json",
        )
        res_del = self.client.delete(reverse("carro-pasajes"))
        self.assertEqual(res_del.status_code, status.HTTP_200_OK)
        self.assertEqual(res_del.data["eliminados"], 1)
        res_carro = self.client.get(reverse("carro-pasajes"))
        self.assertEqual(res_carro.data["cantidad_items"], 0)

    # ==========================================================================
    # TEST 15: SUPERUSUARIO CREA ADMINISTRADOR DE FLOTA
    # ==========================================================================
    def test_15_superuser_crear_administrador_desde_aplicacion(self):
        """Verifica que el superusuario pueda registrar un Administrador de Flota con empresa asignada."""
        self.client.force_authenticate(user=self.superuser)
        url = reverse("superadmin-usuarios")
        payload = {
            "username": "nuevo_admin_flota",
            "password": "PasswordSegura123",
            "email": "nuevo_admin@turbus.cl",
            "first_name": "Carlos",
            "last_name": "Méndez",
            "rut": "14.555.666-7",
            "rol": Usuario.ROL_ADMIN_FLOTA,
            "empresa": self.empresa_turbus.id,
            "is_staff": True,
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["username"], "nuevo_admin_flota")
        self.assertEqual(res.data["rol"], Usuario.ROL_ADMIN_FLOTA)
        self.assertEqual(res.data["empresa"], self.empresa_turbus.id)
        self.assertTrue(res.data["is_staff"])

        # Verificar en base de datos
        user_creado = Usuario.objects.get(username="nuevo_admin_flota")
        self.assertEqual(user_creado.rol, Usuario.ROL_ADMIN_FLOTA)
        self.assertEqual(user_creado.empresa, self.empresa_turbus)
        self.assertTrue(user_creado.is_staff)

    # ==========================================================================
    # TEST 16: SUPERUSUARIO CONCEDE Y REVOCA PRIVILEGIOS DE ROL
    # ==========================================================================
    def test_16_superuser_conceder_y_revocar_privilegios(self):
        """Verifica que el superusuario pueda ascender un pasajero a admin y luego revocar privilegios."""
        self.client.force_authenticate(user=self.superuser)
        url = reverse("superadmin-usuario-privilegios", kwargs={"pk": self.usuario_pasajero1.id})

        # 1. Conceder privilegios: ascender a Administrador de Flota con empresa
        res_ascender = self.client.patch(
            url,
            {
                "rol": Usuario.ROL_ADMIN_FLOTA,
                "empresa": self.empresa_turbus.id,
                "is_staff": True,
            },
            format="json",
        )
        self.assertEqual(res_ascender.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ascender.data["rol"], Usuario.ROL_ADMIN_FLOTA)
        self.assertEqual(res_ascender.data["empresa"], self.empresa_turbus.id)

        self.usuario_pasajero1.refresh_from_db()
        self.assertEqual(self.usuario_pasajero1.rol, Usuario.ROL_ADMIN_FLOTA)
        self.assertEqual(self.usuario_pasajero1.empresa, self.empresa_turbus)

        # 2. Revocar privilegios: degradar nuevamente a Pasajero y quitar empresa
        res_revocar = self.client.patch(
            url,
            {
                "rol": Usuario.ROL_PASAJERO,
                "empresa": None,
                "is_staff": False,
            },
            format="json",
        )
        self.assertEqual(res_revocar.status_code, status.HTTP_200_OK)
        self.assertEqual(res_revocar.data["rol"], Usuario.ROL_PASAJERO)
        self.assertIsNone(res_revocar.data["empresa"])

        self.usuario_pasajero1.refresh_from_db()
        self.assertEqual(self.usuario_pasajero1.rol, Usuario.ROL_PASAJERO)
        self.assertIsNone(self.usuario_pasajero1.empresa)

    # ==========================================================================
    # TEST 17: USUARIOS NO SUPERUSER TIENEN ACCESO DENEGADO A GESTIÓN DE ROLES
    # ==========================================================================
    def test_17_usuarios_no_superuser_denegados_a_gestion_usuarios(self):
        """Verifica que ni pasajeros ni administradores de flota comunes puedan acceder a la gestión de usuarios."""
        url_lista = reverse("superadmin-usuarios")
        url_privilegios = reverse("superadmin-usuario-privilegios", kwargs={"pk": self.usuario_pasajero2.id})

        # Pasajero
        self.client.force_authenticate(user=self.usuario_pasajero1)
        self.assertEqual(self.client.get(url_lista).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.patch(url_privilegios, {"rol": Usuario.ROL_ADMIN_FLOTA}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Administrador de Flota
        self.client.force_authenticate(user=self.usuario_admin)
        self.assertEqual(self.client.get(url_lista).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.patch(url_privilegios, {"rol": Usuario.ROL_ADMIN_FLOTA}).status_code,
            status.HTTP_403_FORBIDDEN,
        )


