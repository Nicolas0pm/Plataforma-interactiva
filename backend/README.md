# Backend (API en Python)

FastAPI + PostgreSQL (SQLAlchemy, en Neon).

## Instalación

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edita .env con DATABASE_URL (cadena de conexión de Neon, ver docs/despliegue.md),
# JWT_SECRET y PIN_PEPPER
```

## Ejecutar en desarrollo

**Sin Neon** (base SQLite en memoria, para desarrollar y probar rápido —
nunca usar en producción):

```bash
USE_FAKE_DB=true uvicorn app.main:app --reload --port 8000
```

En este modo ya existe un coordinador para entrar: usuario `coordinador`, contraseña
`coordinador123` (solo en el modo de prueba; en producción no existe).

**Con la base de datos real** (la API crea las tablas que falten al arrancar):

```bash
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Documentación interactiva (Swagger): http://localhost:8000/docs

## Autenticación

Nadie se registra solo: el **coordinador** (rol `admin`) crea todas las cuentas desde su
panel (`/api/coordinador/...`). Todos los endpoints (salvo los de login y los de la máquina
de premios, que usan `X-Device-Secret`) exigen `Authorization: Bearer <token>`. Todos los
tokens son JWT (HS256) emitidos por esta API, ver `app/services/auth_service.py`:

- **Docentes, padres y coordinadores**: `POST /api/usuarios/login` con su usuario (o su
  correo) y contraseña (guardada como hash scrypt). Entran la primera vez con la contraseña
  temporal que les dio el coordinador y deben cambiarla y aceptar los términos
  (`POST /api/usuarios/cambiar-password`). Expira a los `JWT_ADULTO_EXP_MINUTOS` minutos (480).
- **Estudiantes**: `POST /api/usuarios/login-pin` con código + PIN. Expira a los
  `JWT_PIN_EXP_MINUTOS` minutos (30).

Tras 5 intentos fallidos seguidos, el usuario o el código se bloquea 10 minutos.
El primer coordinador se crea desde la terminal:
`python scripts/asignar_password.py <usuario> --crear-admin "Nombre"`.

## Endpoints principales

| Método | Ruta | Quién puede llamarlo | Requisito cubierto |
|---|---|---|---|
| GET | `/api/coordinador/usuarios` | Coordinador | Gestión de cuentas |
| POST | `/api/coordinador/adultos` | Coordinador (crea docente, padre o coordinador; devuelve la contraseña temporal) | RF01 |
| POST | `/api/coordinador/estudiantes` | Coordinador (con PIN, docente y acudientes) | RF01/RF07/RF11 |
| PATCH | `/api/coordinador/estudiantes/{id}` | Coordinador (cambia docente y/o acudientes) | RF07/RF11 |
| POST | `/api/coordinador/usuarios/{id}/restablecer-password` | Coordinador | Contraseña olvidada |
| POST | `/api/coordinador/estudiantes/{id}/pin` | Coordinador | PIN olvidado |
| PATCH | `/api/coordinador/usuarios/{id}` | Coordinador (activar / desactivar) | Gestión de cuentas |
| POST | `/api/usuarios/login` | Público (valida usuario y contraseña) | RF01 |
| POST | `/api/usuarios/cambiar-password` | El propio adulto | RF01 |
| POST | `/api/usuarios/login-pin` | Público (valida el PIN) | RF01 CA3 |
| GET | `/api/usuarios/sesion` | Cualquier usuario autenticado | Restaurar sesión |
| GET | `/api/usuarios/{id}/progreso` | El propio estudiante, su docente, sus padres o admin | RF06/RF07/RF09 |
| GET | `/api/usuarios/docente/{id}/estudiantes` | Ese docente o admin | RF06 |
| GET | `/api/usuarios/docente/{id}/estadisticas` | Ese docente o admin | RF06/RF09 |
| GET | `/api/usuarios/padre/{id}/hijos` | Ese padre o admin | RF07 |
| GET | `/api/actividades` | Cualquier usuario autenticado | RF04 |
| POST | `/api/actividades` | Docente o admin | RNF-ESC-01 |
| POST | `/api/actividades/completar/{id}` | El propio estudiante | RF03/RF04/RF08/RF09/RF05 |
| POST | `/api/feedback` | El docente asignado a ese estudiante | Feedback de progreso |
| GET | `/api/feedback/estudiante/{id}` | El propio estudiante, su docente, sus padres o admin | Feedback de progreso |
| GET | `/api/recompensas/estudiante/{id}` | El propio estudiante, su docente, sus padres o admin | RF05 |
| GET | `/api/recompensas/cola/{device_id}` | El ESP32, con `X-Device-Secret` | RF05 (fase ESP32) |
| POST | `/api/recompensas/{id}/confirmar-entrega` | El ESP32, con `X-Device-Secret` | RF05 (fase ESP32) |
| GET | `/api/auditoria/exportar.csv` | Solo el coordinador | RNF-AUD-07 |

## Pruebas

```bash
pytest
```

Las pruebas corren siempre con `USE_FAKE_DB=true` y SQLite en memoria (ver
`tests/conftest.py`), así que no necesitan credenciales. Para correrlas contra PostgreSQL,
usa una base **solo para pruebas** (se borra entera en cada prueba):
`TEST_DATABASE_URL=postgresql://... pytest`. Cubren: cuentas creadas por el coordinador,
primer ingreso, bloqueo por intentos fallidos, camino de lecciones, umbral de recompensas,
progresión de niveles (RF04), guardas de rol/relación en la API (401/403) y las garantías de
la base de datos (transacciones, largos de columna).

## Estructura

```
backend/
└── app/
    ├── main.py                 # arranque de FastAPI, CORS, manejador de errores
    ├── config.py                # variables de entorno
    ├── db.py                    # conexión a PostgreSQL y transacción por petición
    ├── models/schemas.py         # validaciones Pydantic
    ├── models/tablas.py          # tablas de la base de datos (ver docs/data-model.md)
    ├── routers/                  # un archivo por recurso (usuarios, coordinador, ...)
    └── services/
        ├── auth_service.py        # tokens, roles, auditoría
        ├── progreso_db.py          # progreso del niño ↔ sus tablas
        ├── progreso_service.py     # RF04: niveles a partir del puntaje
        └── recompensas_service.py  # RF05
└── tests/                       # pytest
```
