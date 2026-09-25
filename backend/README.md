# Backend (API en Python)

FastAPI + Firebase Admin SDK.

## Instalación

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edita .env con tu FIREBASE_PROJECT_ID
# coloca tu serviceAccountKey.json aquí (ver firebase/README_FIREBASE.md paso 5)
```

## Ejecutar en desarrollo

**Sin un proyecto de Firebase real** (base de datos en memoria, para desarrollar y
probar rápido — nunca usar en producción):

```bash
USE_FAKE_DB=true uvicorn app.main:app --reload --port 8000
```

**Con Firebase real:**

```bash
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Documentación interactiva (Swagger): http://localhost:8000/docs

## Autenticación

Todos los endpoints (salvo `POST /api/usuarios/login-pin`, `POST /api/usuarios/login-dev`
y la creación de la propia cuenta) exigen `Authorization: Bearer <token>`. Hay dos
tipos de token, ver `app/services/auth_service.py`:

- **ID token de Firebase Authentication** (RS256): para docentes, padres y admin.
  El frontend lo obtiene con el SDK web tras `signInWithEmailAndPassword`.
- **JWT propio (HS256)** emitido por esta API: para el acceso simplificado por PIN
  de los estudiantes (`POST /api/usuarios/login-pin`). Expira a los
  `JWT_PIN_EXP_MINUTOS` minutos (por defecto 30).

Con `USE_FAKE_DB=true` también existe `POST /api/usuarios/login-dev` (docente/padre/
admin sin Firebase real) — deshabilitado por completo si `USE_FAKE_DB` no está activo.

## Endpoints principales

| Método | Ruta | Quién puede llamarlo | Requisito cubierto |
|---|---|---|---|
| POST | `/api/usuarios` | Estudiante: su docente/padre/admin. Docente/padre/admin: se auto-registra | RF01 |
| POST | `/api/usuarios/login-pin` | Público (valida el PIN) | RF01 CA3 |
| POST | `/api/usuarios/login-dev` | Público, solo si `USE_FAKE_DB=true` | — (solo dev) |
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
| POST | `/api/recompensas/{id}/confirmar-entrega` | El ESP32, con `X-Device-Secret` | RF05 (fase ESP32) |
| POST | `/api/vinculacion` | Docente o padre autenticado (con código + PIN del niño) | RF07/RF11 |
| GET | `/api/auditoria/exportar.csv` | Solo admin | RNF-AUD-07 |

## Pruebas

```bash
pytest
```

Las pruebas corren siempre con `USE_FAKE_DB=true` (ver `tests/conftest.py`), así que
no necesitan credenciales de Firebase. Cubren: umbral de recompensas, vinculación con
código + PIN y bloqueo por intentos fallidos (RF11), progresión de niveles (RF04), y guardas
de rol/relación en la API (401/403).

## Estructura

```
backend/
└── app/
    ├── main.py                 # arranque de FastAPI, CORS, manejador de errores
    ├── config.py                # variables de entorno
    ├── models/schemas.py         # validaciones Pydantic
    ├── routers/                  # un archivo por recurso (usuarios, actividades, ...)
    └── services/
        ├── auth_service.py        # tokens, roles, auditoría
        ├── firebase_service.py     # Firestore/Realtime Database (real o fake)
        ├── fake_firestore.py       # base de datos en memoria para USE_FAKE_DB=true
        ├── progreso_service.py     # RF04: niveles a partir del puntaje
        ├── recompensas_service.py  # RF05
        └── vinculacion_service.py  # RF11
└── tests/                       # pytest
```
