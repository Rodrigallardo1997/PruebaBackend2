"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
COMANDO DE GESTIÓN: POBLAR DATOS DE PRUEBA (poblar_datos.py)
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2) - AÑO: 2026
ALUMNO: RODRIGO GALLARDO | SECCIÓN: AP-N4-C2(E-F)/D
================================================================================
Uso:
    python manage.py poblar_datos

Este comando inicializa la base de datos con un set integral de datos de prueba:
1. Empresas de Transporte / Tenants (Turbus, Pullman Bus, EME Bus).
2. Cuentas de Administrador por cada Empresa (admin_turbus, admin_pullman, admin_eme).
3. Cuentas de Pasajeros (pasajero1, pasajero2) con Carrito Persistente en PostgreSQL.
4. Flotas de Buses diferenciadas con Estados Operativos (DISPONIBLE, EN_RUTA, MANTENIMIENTO).
5. Rutas e Itinerarios interurbanos con asientos y tarifas.
6. Transacciones y Boletos con UUID, métodos de pago (Webpay, Transferencia, BancoEstado)
   y estados de embarque para visualizar movimientos de cada empresa.
================================================================================
"""

from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
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


class Command(BaseCommand):
    help = "Puebla la base de datos con información inicial para la evaluación EVA-2."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("==> Iniciando poblacion de datos para Buses Chile..."))

        # 0. CREACIÓN DE EMPRESAS DE TRANSPORTE / TENANTS (MULTI-TENANCY)
        emp_turbus, _ = EmpresaTransporte.objects.get_or_create(
            slug="turbus",
            defaults={
                "nombre": "Turbus",
                "rut": "76.111.222-3",
                "color_hex": "#16a34a",
                "activo": True,
            },
        )

        emp_pullman, _ = EmpresaTransporte.objects.get_or_create(
            slug="pullman",
            defaults={
                "nombre": "Pullman Bus",
                "rut": "77.444.555-6",
                "color_hex": "#ea580c",
                "activo": True,
            },
        )

        emp_eme, _ = EmpresaTransporte.objects.get_or_create(
            slug="eme-bus",
            defaults={
                "nombre": "EME Bus",
                "rut": "78.777.888-9",
                "color_hex": "#2563eb",
                "activo": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("[OK] 3 Tenants creados: Turbus, Pullman Bus, EME Bus."))

        # 1. CREACIÓN DE USUARIOS
        # Administrador General / Superusuario
        admin_user, _ = Usuario.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@buseschile.cl",
                "first_name": "Administrador",
                "last_name": "General",
                "rol": Usuario.ROL_ADMIN_FLOTA,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin_user.set_password("admin123")
        admin_user.save()

        # Administrador Turbus
        admin_turbus, _ = Usuario.objects.get_or_create(
            username="admin_turbus",
            defaults={
                "email": "flota@turbus.cl",
                "first_name": "Carlos",
                "last_name": "Gestor Turbus",
                "rol": Usuario.ROL_ADMIN_FLOTA,
                "empresa": emp_turbus,
                "is_staff": True,
            },
        )
        admin_turbus.empresa = emp_turbus
        admin_turbus.set_password("admin123")
        admin_turbus.save()

        # Alias histórico admin_flota1 (Turbus)
        admin_flota1, _ = Usuario.objects.get_or_create(
            username="admin_flota1",
            defaults={
                "email": "flota1@turbus.cl",
                "first_name": "Carlos",
                "last_name": "Gestor Flota",
                "rol": Usuario.ROL_ADMIN_FLOTA,
                "empresa": emp_turbus,
                "is_staff": True,
            },
        )
        admin_flota1.empresa = emp_turbus
        admin_flota1.set_password("admin123")
        admin_flota1.save()

        # Administrador Pullman Bus
        admin_pullman, _ = Usuario.objects.get_or_create(
            username="admin_pullman",
            defaults={
                "email": "operaciones@pullman.cl",
                "first_name": "Roberto",
                "last_name": "Gestor Pullman",
                "rol": Usuario.ROL_ADMIN_FLOTA,
                "empresa": emp_pullman,
                "is_staff": True,
            },
        )
        admin_pullman.empresa = emp_pullman
        admin_pullman.set_password("admin123")
        admin_pullman.save()

        # Administrador EME Bus
        admin_eme, _ = Usuario.objects.get_or_create(
            username="admin_eme",
            defaults={
                "email": "flota@emebus.cl",
                "first_name": "Valeria",
                "last_name": "Gestora EME",
                "rol": Usuario.ROL_ADMIN_FLOTA,
                "empresa": emp_eme,
                "is_staff": True,
            },
        )
        admin_eme.empresa = emp_eme
        admin_eme.set_password("admin123")
        admin_eme.save()

        # Pasajero 1 (Juan Pérez)
        pasajero1, _ = Usuario.objects.get_or_create(
            username="pasajero1",
            defaults={
                "email": "juan.perez@correo.cl",
                "first_name": "Juan",
                "last_name": "Pérez",
                "rut": "18.345.678-9",
                "telefono": "+56911223344",
                "rol": Usuario.ROL_PASAJERO,
            },
        )
        pasajero1.set_password("pasajero123")
        pasajero1.save()
        carro1, _ = CarroPasajes.objects.get_or_create(usuario=pasajero1)

        # Pasajero 2 (María González)
        pasajero2, _ = Usuario.objects.get_or_create(
            username="pasajero2",
            defaults={
                "email": "maria.gonzalez@correo.cl",
                "first_name": "María",
                "last_name": "González",
                "rut": "19.876.543-2",
                "telefono": "+56999887766",
                "rol": Usuario.ROL_PASAJERO,
            },
        )
        pasajero2.set_password("pasajero123")
        pasajero2.save()
        carro2, _ = CarroPasajes.objects.get_or_create(usuario=pasajero2)

        self.stdout.write(self.style.SUCCESS("[OK] Usuarios administradores y pasajeros creados."))

        # 2. CREACIÓN DE CIUDADES Y TERMINALES
        ciudades_datos = [
            ("Santiago", "Terminal Sur", "Región Metropolitana"),
            ("Valparaíso", "Terminal Rodoviario", "Región de Valparaíso"),
            ("Viña del Mar", "Terminal Viña del Mar", "Región de Valparaíso"),
            ("Concepción", "Terminal Collao", "Región del Biobío"),
            ("La Serena", "Terminal de Buses La Serena", "Región de Coquimbo"),
            ("Puerto Montt", "Terminal Municipal Puerto Montt", "Región de Los Lagos"),
        ]

        ciudades_dict = {}
        for nombre, term, reg in ciudades_datos:
            ciudad, _ = Ciudad.objects.get_or_create(
                nombre=nombre,
                terminal=term,
                defaults={"region": reg},
            )
            ciudades_dict[nombre] = ciudad

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(ciudades_dict)} Ciudades y Terminales registradas."))

        # 3. CREACIÓN DE RUTAS
        rutas_datos = [
            ("Santiago", "Valparaíso", 120, 90),
            ("Valparaíso", "Santiago", 120, 90),
            ("Santiago", "Viña del Mar", 125, 95),
            ("Viña del Mar", "Santiago", 125, 95),
            ("Santiago", "Concepción", 500, 360),
            ("Concepción", "Santiago", 500, 360),
            ("Santiago", "La Serena", 470, 330),
        ]

        rutas_dict = {}
        for orig, dest, dist, dur in rutas_datos:
            ruta, _ = Ruta.objects.get_or_create(
                origen=ciudades_dict[orig],
                destino=ciudades_dict[dest],
                defaults={"distancia_km": dist, "duracion_estimada_minutos": dur},
            )
            rutas_dict[f"{orig}->{dest}"] = ruta

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(rutas_dict)} Rutas interurbanas configuradas."))

        # 4. CREACIÓN DE FLOTA DE BUSES CON ESTADOS OPERATIVOS Y ASIENTOS
        # Función auxiliar para crear asientos
        def configurar_asientos(bus, cant_cama, cant_semi):
            if bus.asientos.count() == 0:
                for i in range(1, cant_cama + 1):
                    Asiento.objects.create(bus=bus, numero=i, tipo=Asiento.TIPO_CAMA, piso=1)
                for i in range(cant_cama + 1, cant_cama + cant_semi + 1):
                    Asiento.objects.create(bus=bus, numero=i, tipo=Asiento.TIPO_SEMICAMA, piso=2)

        # Flota TURBUS
        bus1, _ = Bus.objects.get_or_create(
            patente="ABCD-12",
            defaults={
                "empresa": emp_turbus,
                "modelo": "Marcopolo Paradiso 1800 DD",
                "marca": "Scania",
                "capacidad_total": 44,
                "estado_operativo": Bus.ESTADO_OPERATIVO_EN_RUTA,
                "activo": True,
            },
        )
        bus1.estado_operativo = Bus.ESTADO_OPERATIVO_EN_RUTA
        bus1.save()
        configurar_asientos(bus1, 12, 32)

        bus_turbus_2, _ = Bus.objects.get_or_create(
            patente="TURB-88",
            defaults={
                "empresa": emp_turbus,
                "modelo": "Marcopolo Viaggio 1050",
                "marca": "Mercedes-Benz",
                "capacidad_total": 44,
                "estado_operativo": Bus.ESTADO_OPERATIVO_DISPONIBLE,
                "activo": True,
            },
        )
        bus_turbus_2.estado_operativo = Bus.ESTADO_OPERATIVO_DISPONIBLE
        bus_turbus_2.save()
        configurar_asientos(bus_turbus_2, 12, 32)

        bus_turbus_3, _ = Bus.objects.get_or_create(
            patente="TURB-99",
            defaults={
                "empresa": emp_turbus,
                "modelo": "Scania Touring HD",
                "marca": "Scania",
                "capacidad_total": 40,
                "estado_operativo": Bus.ESTADO_OPERATIVO_MANTENIMIENTO,
                "activo": True,
            },
        )
        bus_turbus_3.estado_operativo = Bus.ESTADO_OPERATIVO_MANTENIMIENTO
        bus_turbus_3.save()
        configurar_asientos(bus_turbus_3, 10, 30)

        # Flota PULLMAN BUS
        bus2, _ = Bus.objects.get_or_create(
            patente="EFGH-34",
            defaults={
                "empresa": emp_pullman,
                "modelo": "Irizar i8 Premium",
                "marca": "Mercedes-Benz",
                "capacidad_total": 40,
                "estado_operativo": Bus.ESTADO_OPERATIVO_EN_RUTA,
                "activo": True,
            },
        )
        bus2.estado_operativo = Bus.ESTADO_OPERATIVO_EN_RUTA
        bus2.save()
        configurar_asientos(bus2, 10, 30)

        bus_pullman_2, _ = Bus.objects.get_or_create(
            patente="PULL-22",
            defaults={
                "empresa": emp_pullman,
                "modelo": "Marcopolo Paradiso G7",
                "marca": "Volvo",
                "capacidad_total": 40,
                "estado_operativo": Bus.ESTADO_OPERATIVO_DISPONIBLE,
                "activo": True,
            },
        )
        bus_pullman_2.estado_operativo = Bus.ESTADO_OPERATIVO_DISPONIBLE
        bus_pullman_2.save()
        configurar_asientos(bus_pullman_2, 10, 30)

        bus_pullman_3, _ = Bus.objects.get_or_create(
            patente="PULL-55",
            defaults={
                "empresa": emp_pullman,
                "modelo": "Volvo 9700 Grand",
                "marca": "Volvo",
                "capacidad_total": 40,
                "estado_operativo": Bus.ESTADO_OPERATIVO_MANTENIMIENTO,
                "activo": True,
            },
        )
        bus_pullman_3.estado_operativo = Bus.ESTADO_OPERATIVO_MANTENIMIENTO
        bus_pullman_3.save()
        configurar_asientos(bus_pullman_3, 10, 30)

        # Flota EME BUS
        bus3, _ = Bus.objects.get_or_create(
            patente="IJKL-56",
            defaults={
                "empresa": emp_eme,
                "modelo": "Marcopolo Paradiso G8 DD",
                "marca": "Volvo",
                "capacidad_total": 44,
                "estado_operativo": Bus.ESTADO_OPERATIVO_EN_RUTA,
                "activo": True,
            },
        )
        bus3.estado_operativo = Bus.ESTADO_OPERATIVO_EN_RUTA
        bus3.save()
        configurar_asientos(bus3, 12, 32)

        bus_eme_2, _ = Bus.objects.get_or_create(
            patente="EMEB-77",
            defaults={
                "empresa": emp_eme,
                "modelo": "Scania Touring VIP",
                "marca": "Scania",
                "capacidad_total": 44,
                "estado_operativo": Bus.ESTADO_OPERATIVO_DISPONIBLE,
                "activo": True,
            },
        )
        bus_eme_2.estado_operativo = Bus.ESTADO_OPERATIVO_DISPONIBLE
        bus_eme_2.save()
        configurar_asientos(bus_eme_2, 12, 32)

        bus_eme_3, _ = Bus.objects.get_or_create(
            patente="EMEB-99",
            defaults={
                "empresa": emp_eme,
                "modelo": "Marcopolo Viaggio G8",
                "marca": "Volvo",
                "capacidad_total": 40,
                "estado_operativo": Bus.ESTADO_OPERATIVO_MANTENIMIENTO,
                "activo": True,
            },
        )
        bus_eme_3.estado_operativo = Bus.ESTADO_OPERATIVO_MANTENIMIENTO
        bus_eme_3.save()
        configurar_asientos(bus_eme_3, 10, 30)

        self.stdout.write(self.style.SUCCESS("[OK] Flotas creadas con estados operativos: DISPONIBLE, EN_RUTA, MANTENIMIENTO."))

        # 5. CREACIÓN DE SERVICIOS / ITINERARIOS
        ahora = timezone.now().replace(minute=0, second=0, microsecond=0)

        servicios_datos = [
            (
                emp_turbus,
                rutas_dict["Santiago->Valparaíso"],
                bus1,
                ahora + timedelta(hours=3),
                ahora + timedelta(hours=4, minutes=30),
                Decimal("6500.00"),
                Decimal("9500.00"),
            ),
            (
                emp_pullman,
                rutas_dict["Santiago->Valparaíso"],
                bus2,
                ahora + timedelta(hours=6),
                ahora + timedelta(hours=7, minutes=30),
                Decimal("6800.00"),
                Decimal("9800.00"),
            ),
            (
                emp_turbus,
                rutas_dict["Valparaíso->Santiago"],
                bus1,
                ahora + timedelta(hours=8),
                ahora + timedelta(hours=9, minutes=30),
                Decimal("6500.00"),
                Decimal("9500.00"),
            ),
            (
                emp_eme,
                rutas_dict["Santiago->Concepción"],
                bus3,
                ahora + timedelta(days=1, hours=8),
                ahora + timedelta(days=1, hours=14),
                Decimal("15500.00"),
                Decimal("23000.00"),
            ),
            (
                emp_pullman,
                rutas_dict["Santiago->La Serena"],
                bus2,
                ahora + timedelta(days=1, hours=10),
                ahora + timedelta(days=1, hours=15, minutes=30),
                Decimal("14000.00"),
                Decimal("20000.00"),
            ),
            (
                emp_eme,
                rutas_dict["Concepción->Santiago"],
                bus3,
                ahora + timedelta(days=2, hours=9),
                ahora + timedelta(days=2, hours=15),
                Decimal("15500.00"),
                Decimal("23000.00"),
            ),
        ]

        servicios_instancias = []
        for empresa, ruta, bus, salida, llegada, p_semi, p_cama in servicios_datos:
            s, _ = Servicio.objects.get_or_create(
                ruta=ruta,
                bus=bus,
                fecha_hora_salida=salida,
                defaults={
                    "empresa": empresa,
                    "fecha_hora_llegada": llegada,
                    "precio_semicama": p_semi,
                    "precio_cama": p_cama,
                    "estado": Servicio.ESTADO_PROGRAMADO,
                },
            )
            s.empresa = empresa
            s.save()
            servicios_instancias.append(s)

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(servicios_instancias)} Servicios e Itinerarios programados."))

        # 6. CREACIÓN DE VENTAS Y BOLETOS CON UUID PARA CADA EMPRESA (MOVIMIENTOS)
        # Servicio 1 (Turbus): 3 boletos emitidos
        s1 = servicios_instancias[0]
        if s1.boletos.count() == 0:
            asiento_s1_1 = s1.bus.asientos.get(numero=1)
            asiento_s1_2 = s1.bus.asientos.get(numero=2)
            asiento_s1_14 = s1.bus.asientos.get(numero=14)

            orden_turbus = OrdenCompra.objects.create(
                usuario=pasajero2,
                total=s1.precio_cama * 2 + s1.precio_semicama,
                estado=OrdenCompra.ESTADO_PAGADO,
                metodo_pago=OrdenCompra.METODO_WEBPAY,
            )
            Boleto.objects.create(
                orden=orden_turbus,
                servicio=s1,
                asiento=asiento_s1_1,
                nombre_pasajero="Claudio Bravo",
                rut_pasajero="14.234.567-8",
                precio_pagado=s1.precio_cama,
                estado_embarque=Boleto.ESTADO_EMBARQUE_EMBARCADO,
                activo=True,
            )
            Boleto.objects.create(
                orden=orden_turbus,
                servicio=s1,
                asiento=asiento_s1_2,
                nombre_pasajero="Alexis Sánchez",
                rut_pasajero="16.345.678-9",
                precio_pagado=s1.precio_cama,
                estado_embarque=Boleto.ESTADO_EMBARQUE_EMITIDO,
                activo=True,
            )
            Boleto.objects.create(
                orden=orden_turbus,
                servicio=s1,
                asiento=asiento_s1_14,
                nombre_pasajero="Arturo Vidal",
                rut_pasajero="15.876.543-2",
                precio_pagado=s1.precio_semicama,
                estado_embarque=Boleto.ESTADO_EMBARQUE_EMITIDO,
                activo=True,
            )

        # Servicio 2 (Pullman Bus): 2 boletos emitidos
        s2 = servicios_instancias[1]
        if s2.boletos.count() == 0:
            asiento_s2_1 = s2.bus.asientos.get(numero=1)
            asiento_s2_2 = s2.bus.asientos.get(numero=2)

            orden_pullman = OrdenCompra.objects.create(
                usuario=pasajero2,
                total=s2.precio_cama * 2,
                estado=OrdenCompra.ESTADO_PAGADO,
                metodo_pago=OrdenCompra.METODO_TRANSFERENCIA,
            )
            Boleto.objects.create(
                orden=orden_pullman,
                servicio=s2,
                asiento=asiento_s2_1,
                nombre_pasajero="Gary Medel",
                rut_pasajero="16.987.654-3",
                precio_pagado=s2.precio_cama,
                estado_embarque=Boleto.ESTADO_EMBARQUE_EMBARCADO,
                activo=True,
            )
            Boleto.objects.create(
                orden=orden_pullman,
                servicio=s2,
                asiento=asiento_s2_2,
                nombre_pasajero="Charles Aránguiz",
                rut_pasajero="17.112.233-4",
                precio_pagado=s2.precio_cama,
                estado_embarque=Boleto.ESTADO_EMBARQUE_EMITIDO,
                activo=True,
            )

        # Servicio 4 (EME Bus): 2 boletos emitidos
        s4 = servicios_instancias[3]
        if s4.boletos.count() == 0:
            asiento_s4_1 = s4.bus.asientos.get(numero=1)
            asiento_s4_2 = s4.bus.asientos.get(numero=2)

            orden_eme = OrdenCompra.objects.create(
                usuario=pasajero2,
                total=s4.precio_cama * 2,
                estado=OrdenCompra.ESTADO_PAGADO,
                metodo_pago=OrdenCompra.METODO_BANCO_ESTADO,
            )
            Boleto.objects.create(
                orden=orden_eme,
                servicio=s4,
                asiento=asiento_s4_1,
                nombre_pasajero="Marcelo Díaz",
                rut_pasajero="15.223.344-5",
                precio_pagado=s4.precio_cama,
                estado_embarque=Boleto.ESTADO_EMBARQUE_EMITIDO,
                activo=True,
            )
            Boleto.objects.create(
                orden=orden_eme,
                servicio=s4,
                asiento=asiento_s4_2,
                nombre_pasajero="Eduardo Vargas",
                rut_pasajero="16.554.433-2",
                precio_pagado=s4.precio_cama,
                estado_embarque=Boleto.ESTADO_EMBARQUE_EMBARCADO,
                activo=True,
            )

        self.stdout.write(self.style.SUCCESS("[OK] Boletos y transacciones históricas registradas con UUID y estados de embarque."))

        # 7. CARRITO PERSISTENTE PRE-CARGADO PARA PASAJERO 1 (DEMOSTRACIÓN INMEDIATA)
        carro_pasajero1, _ = CarroPasajes.objects.get_or_create(usuario=pasajero1)
        if carro_pasajero1.items.count() == 0:
            asiento_demo = s1.bus.asientos.get(numero=5)
            ItemCarro.objects.create(
                carro=carro_pasajero1,
                servicio=s1,
                asiento=asiento_demo,
                nombre_pasajero="Juan Pérez",
                rut_pasajero="18.345.678-9",
                precio_unitario=s1.precio_cama,
            )
        self.stdout.write(self.style.SUCCESS("[OK] Carrito persistente pre-cargado para pasajero1 en PostgreSQL."))

        self.stdout.write(self.style.SUCCESS("==> Poblacion de datos completada exitosamente!"))
