# Plataforma Interactiva de Inglés con Recompensas Físicas

Plataforma web para incentivar el aprendizaje del inglés en niños de 6 a 8 años mediante
actividades interactivas y un sistema de recompensas físicas (dispensador con ESP32).

Basado en el documento de grado *"Plataforma Interactiva con un sistema de recompensas
físicas para incentivar el aprendizaje del inglés en Niños de 6 a 8 Años"* (UMB, 2025).

## Arquitectura general

```
┌───────────────┐      HTTPS/REST      ┌───────────────────┐    SQL (SQLAlchemy)   ┌──────────────────┐
│   Frontend    │ ───────────────────▶ │   API (Python /   │ ────────────────────▶ │   PostgreSQL     │
│ HTML/CSS/JS   │ ◀─────────────────── │     FastAPI)       │ ◀──────────────────── │     (Neon)       │
└───────────────┘                      └───────────────────┘                       └──────────────────┘
                                                 ▲
                                                 │ HTTPS: "¿tengo premios pendientes?" / "ya lo entregué"
                                       ┌──────────────────┐
                                       │   ESP32 (futuro)  │
                                       │ Dispensador físico│
                                       └──────────────────┘
```

**Por qué esta arquitectura:**

- **Frontend (HTML/CSS/JS puro):** simple, sin build tools, fácil de desplegar en cualquier
  servidor estático. Solo habla con la API, así toda regla de negocio vive en un solo lugar.
- **API en Python (FastAPI):** capa intermedia que valida reglas de negocio (niveles,
  puntajes, generación de recompensas), maneja el inicio de sesión de todos (contraseñas
  y PIN cifrados), protege la contraseña de la base de datos y expone endpoints REST limpios y documentados
  automáticamente (Swagger en `/docs`).
- **PostgreSQL (Neon):** base de datos principal, relacional, a partir del modelo del
  documento de grado. Guarda usuarios, actividades, historial e informes de progreso.
- **Login propio:** docentes, padres y administradores entran con correo y contraseña; los
  estudiantes, con un código de 6 caracteres y un PIN de 4 dígitos.
- **ESP32 (fase futura):** pregunta a la API cada pocos segundos si tiene premios
  pendientes y confirma cada entrega (`esp32/README.md`).

Ver el detalle completo en [`docs/architecture.md`](docs/architecture.md) y
[`docs/data-model.md`](docs/data-model.md). Explicación de cada parte y de cómo se conecta a
la base de datos: [`docs/frontend.md`](docs/frontend.md) y [`docs/backend.md`](docs/backend.md).

## Estructura del repositorio

```
plataforma-ingles-kids/
├── backend/          API en Python (FastAPI) que habla con PostgreSQL
├── frontend/          HTML/CSS/JS que consume la API
├── esp32/             Placeholder y guía para la integración futura del hardware
├── docs/               Arquitectura y modelo de datos
└── README.md
```

## Cómo levantar el proyecto en local

**Opción rápida, sin base de datos real (modo de prueba):**

1. Backend: ver [`backend/README.md`](backend/README.md) — arranca con
   `USE_FAKE_DB=true` para usar una base de datos SQLite en memoria.
2. Frontend: sirve la carpeta `frontend/` con un servidor estático (ES modules no
   funcionan con `file://`). Usa `python frontend/dev-server.py` en vez de
   `python -m http.server`: este último no envía `Cache-Control`, así que el
   navegador puede seguir mostrando una versión vieja de un `.js`/`.css` después de
   editarlo. Abre `http://localhost:5500/index.html` y usa las secciones "Modo de
   prueba (sin contraseña)" de la pantalla de login para crear cuentas sin configurar
   nada más.

**Para publicarlo en internet** (frontend y backend en Render, por separado, y la base de
datos en Neon), sigue [`docs/despliegue.md`](docs/despliegue.md).

**Con la base de datos real:** pon en `backend/.env` la cadena de conexión de Neon
(`DATABASE_URL`, ver [`docs/despliegue.md`](docs/despliegue.md)) y levanta la API con
`USE_FAKE_DB=false`.

## Estado actual

Ver [`docs/cumplimiento.md`](docs/cumplimiento.md) para la matriz completa de qué
requisito funcional y no funcional está implementado, cuál es parcial (y por qué) y
cuál depende de decisiones de despliegue en vez de código.

En resumen: RF01-RF09 y RF11 están implementados (algunos de forma parcial, ver el
detalle); autenticación y control de roles por token cubren todos los endpoints;
hay un registro de auditoría de solo-inserción; y una suite de pruebas (`pytest`)
cubre la lógica de negocio (recompensas, niveles, vinculación, guardas de rol).
Pendiente explícito: audio en las actividades (RNF-UX-03/RNF-LOC-03), asignación de
actividades 1 a 1 por estudiante (parte de RF06), y la integración física con el
ESP32 (placeholder listo, sin hardware probado).
