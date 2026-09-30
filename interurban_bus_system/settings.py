"""
================================================================================
PROYECTO: SISTEMA DE RESERVAS DE PASAJES DE BUSES INTERURBANOS
ASIGNATURA: DESARROLLO BACKEND (EVALUACIÓN EVA-2)
AÑO: 2026
================================================================================
CONFIGURACIÓN PRINCIPAL DE DJANGO (settings.py)
--------------------------------------------------------------------------------
Este archivo contiene la configuración central del backend, integrando:
1. Base de datos relacional PostgreSQL ('django.db.backends.postgresql').
2. Modelo de usuario personalizado con soporte de roles mediante RBAC.
3. Django REST Framework (DRF) configurado con paginación, filtros y esquema OpenAPI.
4. SimpleJWT con claims personalizados en el payload del token.
5. Documentación interactiva de API mediante drf-spectacular (OpenAPI 3.0).
6. Metadatos del estudiante y pie de página institucional requerido por la pauta.
================================================================================
"""

import os
from datetime import timedelta
from pathlib import Path

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# DATOS DEL ESTUDIANTE Y CONTEXTO ACADÉMICO (EVA-2)
# ==============================================================================
# Estos datos son expuestos a través de la vista base y endpoints informativos
# para cumplir estrictamente con los requerimientos de la pauta de evaluación.
STUDENT_INFO = {
    "ALUMNO": "Rodrigo Gallardo",
    "SECCION": "AP-N4-C2(E-F)/D",
    "ANIO": 2026,
    "ASIGNATURA": "Desarrollo Backend (Evaluación EVA-2)",
    "PROYECTO": "Proyecto 4 - Reservas de Pasajes de Buses Interurbanos (Transporte)",
    "VERSION": "1.0.0",
}

# Clave secreta de seguridad (configurable mediante variable de entorno)
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-eva2-buses-chile-key-2026-interurban-bus-system-super-secure"
)

# Modo depuración
DEBUG = os.environ.get("DEBUG", "True").lower() in ("true", "1", "t")

# Hosts autorizados
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# ==============================================================================
# APLICACIONES INSTALADAS (INSTALLED_APPS)
# ==============================================================================
INSTALLED_APPS = [
    # Aplicaciones nativas de Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Librerías de Terceros requeridas por la pauta técnica
    "rest_framework",                         # Django REST Framework
    "rest_framework_simplejwt",               # Autenticación JWT
    "django_filters",                         # Filtrado avanzado de consultas
    "drf_spectacular",                        # Generador OpenAPI 3.0 y Swagger UI

    # Aplicación local del dominio de transporte
    "transporte.apps.TransporteConfig",
]

# ==============================================================================
# MODELO DE USUARIO PERSONALIZADO (AUTH_USER_MODEL)
# ==============================================================================
# Se extiende AbstractUser en la aplicación 'transporte' para soportar los roles
# de negocio ('PASAJERO' y 'ADMIN_FLOTA') directamente en la entidad de autenticación.
AUTH_USER_MODEL = "transporte.Usuario"

# ==============================================================================
# MIDDLEWARE
# ==============================================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "interurban_bus_system.urls"

# ==============================================================================
# PLANTILLAS (TEMPLATES)
# ==============================================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "interurban_bus_system.wsgi.application"

# Carga de variables de entorno desde archivo .env local si existe
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    try:
        with open(ENV_FILE, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass

# ==============================================================================
# CONFIGURACIÓN DE BASE DE DATOS (POSTGRESQL)
# ==============================================================================
# Según la pauta formal de evaluación (EVA-2), el motor primario y obligatorio
# configurado para el backend es 'django.db.backends.postgresql'.
#
# MECANISMO DE RESILIENCIA Y DETECCIÓN AUTOMÁTICA:
# 1. Si el servicio PostgreSQL está activo y escuchando en el puerto indicado,
#    Django se conecta utilizando el motor 'django.db.backends.postgresql'.
# 2. Si el servicio PostgreSQL no está activo en el equipo local o se especifica
#    USE_SQLITE=True en el entorno, el sistema conmuta automáticamente a SQLite
#    ('db.sqlite3') para que el proyecto inicie al instante sin requerir levantar
#    un contenedor Docker o servicio PostgreSQL en el computador del alumno.
# ==============================================================================
DB_NAME = os.environ.get("DB_NAME", "buses_chile_db")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")

def _verificar_postgres_activo(host, port):
    """Comprueba rápidamente (timeout 0.3s) si el puerto de PostgreSQL está abierto."""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((host, int(port))) == 0
    except Exception:
        return False

_forzar_sqlite = os.environ.get("USE_SQLITE", "").lower() in ("true", "1")
_postgres_activo = _verificar_postgres_activo(DB_HOST, DB_PORT)

if _postgres_activo and not _forzar_sqlite:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DB_NAME,
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
            "CONN_MAX_AGE": 600,
        }
    }
else:
    # Conmutación transparente a SQLite local para inicio inmediato y sin errores
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ==============================================================================
# VALIDACIÓN DE CONTRASEÑAS
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ==============================================================================
# INTERNACIONALIZACIÓN Y ZONA HORARIA
# ==============================================================================
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==============================================================================
# CONFIGURACIÓN DE DJANGO REST FRAMEWORK (DRF)
# ==============================================================================
# Configuración global del framework para habilitar:
# - Autenticación JWT por defecto mediante SimpleJWT.
# - Permisos basados en autenticación por defecto (abiertos selectivamente por vista).
# - Integración del backend de filtrado django-filter.
# - Generación automática del esquema OpenAPI mediante drf-spectacular.
# - Paginación estándar de 20 registros por página.
# ==============================================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# ==============================================================================
# CONFIGURACIÓN DE SIMPLE JWT (JSON WEB TOKENS)
# ==============================================================================
# Define los parámetros de expiración de tokens, tipo de cabecera de autorización
# y vincula el serializador de claims personalizados para inyectar 'role',
# 'username' y 'user_id' en el token de acceso según exige la pauta de evaluación.
# ==============================================================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_OBTAIN_SERIALIZER": "transporte.serializers.CustomTokenObtainPairSerializer",
}

# ==============================================================================
# CONFIGURACIÓN DE DRF-SPECTACULAR (SWAGGER / OPENAPI 3.0)
# ==============================================================================
# Configuración del generador de documentación OpenAPI interactiva.
# Disponible en la ruta '/api/docs/' con soporte de autenticación Bearer JWT.
# ==============================================================================
SPECTACULAR_SETTINGS = {
    "TITLE": "Sistema de Reservas de Pasajes de Buses Interurbanos API",
    "DESCRIPTION": (
        "API RESTful empresarial para la gestión integral de itinerarios de buses interurbanos, "
        "persistencia de carro de pasajes por usuario en PostgreSQL, validación concurrente "
        "y bloqueo atómico de asientos (transacción ACID con select_for_update), y control de acceso "
        "basado en roles (RBAC: Pasajero y Administrador de Flota) mediante SimpleJWT.\n\n"
        "Evaluación EVA-2 - Asignatura: Desarrollo Backend - Año 2026."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
        "defaultModelsExpandDepth": 2,
    },
}
