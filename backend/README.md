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

**Con la base de datos real** (la API crea las tablas que falten al arrancar):

```bash
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Documentación interactiva (Swagger): http://localhost:8000/docs

## Autenticación

Todos los endpoints (salvo los de login, la creación de la propia cuenta y los de la
máquina de premios, que usan `X-Device-Secret`) exigen `Authorization: Bearer <token>`.
Todos los tokens son JWT (HS256) emitidos por esta API, ver `app/services/auth_service.py`:

- **Docentes, padres y admin**: `POST /api/usuarios/login` con correo y contraseña
  (guardada como hash scrypt). Expira a los `JWT_ADULTO_EXP_MINUTOS` minutos (480).
- **Estudiantes**: `POST /api/usuarios/login-pin` con código + PIN. Expira a los
  `JWT_PIN_EXP_MINUTOS` minutos (30).

Tras 5 intentos fallidos seguidos, el correo o el código se bloquea 10 minutos.
Contraseña olvidada o cuenta de admin nueva: `python scripts/asignar_password.py <correo>`
(con `--crear-admin "Nombre"` para crear un admin).

Con `USE_FAKE_DB=true` también existe `POST /api/usuarios/login-dev` (docente/padre/
admin sin contraseña) — deshabilitado por completo si `USE_FAKE_DB` no está activo.

## Endpoints principales

| Método | Ruta | Quién puede llamarlo | Requisito cubierto |
|---|---|---|---|
| POST | `/api/usuarios` | Estudiante: su docente/padre/admin. Docente/padre/admin: se auto-registra | RF01 |
| POST | `/api/usuarios/login` | Público (valida correo y contraseña) | RF01 |
| POST | `/api/usuarios/cambiar-password` | El propio adulto | RF01 |
| POST | `/api/usuarios/login-pin` | Público (valida el PIN) | RF01 CA3 |
| POST | `/api/usuarios/login-dev` | Público, solo si `USE_FAKE_DB=true` | — (solo dev) |
| GET | `/api/usuarios/sesion` | Cualquier usuario autenticado (aunque no haya confirmado su correo) | Restaurar sesión |
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
| POST | `/api/vinculacion` | Docente o padre autenticado (con código + PIN del niño) | RF07/RF11 |
| GET | `/api/auditoria/exportar.csv` | Solo admin | RNF-AUD-07 |

## Pruebas

```bash
pytest
```

Las pruebas corren siempre con `USE_FAKE_DB=true` y SQLite en memoria (ver
`tests/conftest.py`), así que no necesitan credenciales. Para correrlas contra PostgreSQL,
usa una base **solo para pruebas** (se borra entera en cada prueba):
`TEST_DATABASE_URL=postgresql://... pytest`. Cubren: umbral de recompensas, vinculación con
código + PIN y bloqueo por intentos fallidos (RF11), progresión de niveles (RF04), y guardas
de rol/relación en la API (401/403).

## Estructura

```
backend/
└── app/
    ├── main.py                 # arranque de FastAPI, CORS, manejador de errores
    ├── config.py                # variables de entorno
    ├── db.py                    # conexión a PostgreSQL y transacción por petición
    ├── models/schemas.py         # validaciones Pydantic
    ├── models/tablas.py          # tablas de la base de datos (ver docs/data-model.md)
    ├── routers/                  # un archivo por recurso (usuarios, actividades, ...)
    └── services/
        ├── auth_service.py        # tokens, roles, auditoría
        ├── progreso_db.py          # progreso del niño ↔ sus tablas
        ├── progreso_service.py     # RF04: niveles a partir del puntaje
        ├── recompensas_service.py  # RF05
        └── vinculacion_service.py  # RF11
└── tests/                       # pytest
```
