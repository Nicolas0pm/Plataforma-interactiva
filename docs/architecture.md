# Arquitectura

## Capas

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| Frontend | HTML + CSS + JavaScript (vanilla) | UI para niños, docentes y padres. Consume la API vía `fetch`. |
| Autenticación | Propia de la API (JWT) | Docentes, padres y administradores: correo + contraseña (hash scrypt). Niños: código + PIN. |
| API | Python (FastAPI) + SQLAlchemy | Reglas de negocio, validaciones, inicio de sesión, orquestación entre frontend y base de datos. |
| Base de datos principal | PostgreSQL (Neon) | Usuarios, actividades, historial, resultados, recompensas, feedback. Relacional, ver `data-model.md`. |
| Hardware (futuro) | ESP32 | Pregunta a la API por sus premios pendientes y activa el dispensador físico. |

## Flujo típico: un niño termina una lección

1. El frontend envía `POST /api/lecciones/resultado` a la API con sus respuestas.
2. La API valida el payload (Pydantic), califica comparando con las respuestas correctas
   guardadas y, en **una sola transacción** de PostgreSQL:
   - agrega una fila en `intentos_leccion` (y sus errores en `errores_intento`)
   - actualiza `progreso`, `progreso_lecciones` y `progreso_unidades` del niño
3. Si con esa lección completó un mundo, la API:
   crea una fila en `historial_recompensas` con `estado: "pendiente"` y el `device_id` de
   la máquina del salón: esa es la cola de la máquina.
4. El ESP32 (fase futura) pregunta cada pocos segundos `GET /api/recompensas/cola/{device_id}`,
   activa el dispensador por cada premio y confirma la entrega a la API (`POST /api/recompensas/{id}/confirmar-entrega`), que
   marca la fila como `entregada`.
5. El panel de docente/padre lee de la API (que a su vez consulta PostgreSQL) y muestra el
   progreso y las recompensas obtenidas.

## Por qué API intermedia en vez de que el frontend hable directo con la base de datos

Un navegador no puede conectarse a PostgreSQL sin exponer la contraseña de la base de
datos, y aunque se usara un servicio que lo permita, se eligió meter una API en Python
en medio porque:

- Los criterios de negocio del proyecto (niveles, umbrales de recompensa, estadísticas
  agregadas, feedback docente) conviene tenerlos centralizados y con tests, no repetidos
  en JavaScript del cliente.
- El caso de uso de "recompensas físicas" implica lógica adicional (colas, estados,
  reintentos) que es más manejable en un backend.
- Es más fácil integrar después analítica, notificaciones o el ESP32 vía HTTP/MQTT desde
  un backend Python que desde el navegador.
- La cadena de conexión de la base de datos **nunca** debe vivir en el frontend; solo la
  API la usa.

## Roles y permisos (alto nivel)

Esta tabla ahora se hace cumplir en el backend (`app/services/auth_service.py`:
`require_role`, `verificar_acceso_estudiante`), no es solo documentación aspiracional.
Todo endpoint exige un token válido (el JWT que entrega la API al iniciar sesión con
correo y contraseña, o con código y PIN) y, cuando aplica, la relación correcta.

| Rol | Puede |
|---|---|
| Estudiante | Ver su propio perfil, jugar actividades, ver su propio progreso y recompensas |
| Docente | Ver progreso de sus estudiantes asignados, crear actividades, dejar feedback |
| Padre/Acudiente | Ver progreso y recompensas de sus hijos vinculados (RF11) |
| Administrador | Acceso total, incluida la exportación de auditoría |

## Despliegue sugerido

Ver [`despliegue.md`](despliegue.md). En resumen:

- **Frontend:** sitio estático en Render.
- **API (Python):** Render, con Docker (sirve cualquier servicio que corra un contenedor).
- **PostgreSQL:** Neon (plan gratis), en la misma región que la API.
