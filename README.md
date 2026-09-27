# Plataforma Interactiva de Inglés con Recompensas Físicas

Plataforma web para incentivar el aprendizaje del inglés en niños de 6 a 8 años mediante
actividades interactivas y un sistema de recompensas físicas (dispensador con ESP32).

Basado en el documento de grado *"Plataforma Interactiva con un sistema de recompensas
físicas para incentivar el aprendizaje del inglés en Niños de 6 a 8 Años"* (UMB, 2025).

## Arquitectura general

```
┌───────────────┐      HTTPS/REST      ┌───────────────────┐      Admin SDK      ┌──────────────────┐
│   Frontend    │ ───────────────────▶ │   API (Python /   │ ──────────────────▶ │    Firebase       │
│ HTML/CSS/JS   │ ◀─────────────────── │     FastAPI)       │ ◀────────────────── │ Firestore + Auth  │
└───────────────┘                      └───────────────────┘                      └──────────────────┘
                                                 │                                          ▲
                                                 │ escribe evento de recompensa             │ escucha en
                                                 ▼                                          │ tiempo real
                                        ┌───────────────────┐                     ┌──────────────────┐
                                        │ Realtime Database │ ───────────────────▶│   ESP32 (futuro)  │
                                        │  cola_recompensas │                     │ Dispensador físico│
                                        └───────────────────┘                     └──────────────────┘
```

**Por qué esta arquitectura:**

- **Frontend (HTML/CSS/JS puro):** simple, sin build tools, fácil de desplegar en Firebase
  Hosting o cualquier servidor estático. Habla con la API, nunca con Firebase directamente
  (excepto Firebase Auth para login), así toda regla de negocio vive en un solo lugar.
- **API en Python (FastAPI):** capa intermedia que valida reglas de negocio (niveles,
  puntajes, generación de recompensas), protege las credenciales de administrador de
  Firebase (Service Account) y expone endpoints REST limpios y documentados
  automáticamente (Swagger en `/docs`).
- **Firestore:** base de datos principal (equivalente NoSQL al modelo relacional del
  documento de grado). Guarda usuarios, actividades, historial e informes de progreso.
- **Firebase Authentication:** login de docentes/padres/administradores (los estudiantes
  usan un acceso simplificado gestionado por la API, no cuentas de Firebase Auth propias).
- **Realtime Database (pequeño, solo para hardware):** una única colección ligera
  `cola_recompensas/{device_id}` que el ESP32 escucha en tiempo real para activar el
  dispensador físico. Se usa RTDB y no Firestore para esto porque las librerías de
  ESP32 (p. ej. `Firebase-ESP-Client`) tienen mejor soporte y menor latencia con RTDB.

Ver el detalle completo en [`docs/architecture.md`](docs/architecture.md) y
[`docs/data-model.md`](docs/data-model.md).

## Estructura del repositorio

```
plataforma-ingles-kids/
├── backend/          API en Python (FastAPI) que habla con Firebase
├── frontend/          HTML/CSS/JS que consume la API
├── firebase/           Reglas de seguridad, índices e instrucciones de configuración
├── esp32/             Placeholder y guía para la integración futura del hardware
├── docs/               Arquitectura y modelo de datos
└── README.md
```

## Cómo levantar el proyecto en local

**Opción rápida, sin cuenta de Firebase (modo de prueba):**

1. Backend: ver [`backend/README.md`](backend/README.md) — arranca con
   `USE_FAKE_DB=true` para usar una base de datos en memoria.
2. Frontend: sirve la carpeta `frontend/` con un servidor estático (ES modules no
   funcionan con `file://`). Usa `python frontend/dev-server.py` en vez de
   `python -m http.server`: este último no envía `Cache-Control`, así que el
   navegador puede seguir mostrando una versión vieja de un `.js`/`.css` después de
   editarlo. Abre `http://localhost:5500/index.html` y usa las secciones "Modo de
   prueba (sin Firebase)" de la pantalla de login para crear cuentas sin configurar
   nada más.

**Para publicarlo en internet** (frontend en Firebase Hosting y backend en Render, por
separado), sigue [`docs/despliegue.md`](docs/despliegue.md).

**Con un proyecto de Firebase real (para producción):**

1. Configura Firebase siguiendo [`firebase/README_FIREBASE.md`](firebase/README_FIREBASE.md).
2. Levanta la API con `USE_FAKE_DB=false` (o sin definirla) y tu `serviceAccountKey.json`.
3. Ajusta `frontend/js/firebase-config.js` con las credenciales web de tu proyecto.

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
