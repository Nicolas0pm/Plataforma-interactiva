# Arquitectura

## Capas

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| Frontend | HTML + CSS + JavaScript (vanilla) | UI para niños, docentes y padres. Consume la API vía `fetch`. |
| Autenticación | Firebase Authentication | Login de docentes, padres y administradores (email/contraseña). |
| API | Python (FastAPI) | Reglas de negocio, validaciones, orquestación entre frontend y Firebase. |
| Base de datos principal | Firestore | Usuarios, actividades, historial, resultados, recompensas, feedback. |
| Base de datos de hardware | Realtime Database | Cola liviana de comandos de recompensa para el ESP32. |
| Hardware (futuro) | ESP32 | Escucha la cola de recompensas y activa el dispensador físico. |

## Flujo típico: un niño completa una actividad

1. El frontend envía `POST /api/actividades/{id}/completar` a la API con el resultado.
2. La API valida el payload (Pydantic), calcula puntaje/nivel y llama a Firestore
   (Admin SDK) para:
   - crear un documento en `historial_actividades`
   - actualizar `resultados` (puntaje_total, nivel_logrado) del usuario
3. Si el puntaje acumulado alcanza el umbral de una recompensa, la API:
   - crea un documento en `historial_recompensas` con `estado: "pendiente"`
   - escribe un nodo en Realtime Database `cola_recompensas/{device_id}` con la orden
4. El ESP32 (fase futura) tiene un listener en `cola_recompensas/{device_id}`, activa el
   motor/dispensador, y al terminar actualiza el nodo (`estado: "entregada"`), lo cual la
   API sincroniza de vuelta a Firestore.
5. El panel de docente/padre lee de la API (que a su vez lee Firestore) y muestra el
   progreso y las recompensas obtenidas.

## Por qué API intermedia en vez de que el frontend hable directo con Firestore

Es técnicamente posible que el JS del navegador use el SDK web de Firestore directamente.
Se eligió meter una API en Python en medio porque:

- Los criterios de negocio del proyecto (niveles, umbrales de recompensa, estadísticas
  agregadas, feedback docente) conviene tenerlos centralizados y con tests, no repetidos
  en JavaScript del cliente.
- El caso de uso de "recompensas físicas" implica lógica adicional (colas, estados,
  reintentos) que es más manejable en un backend.
- Es más fácil integrar después analítica, notificaciones o el ESP32 vía HTTP/MQTT desde
  un backend Python que desde el navegador.
- Las credenciales de administrador (Service Account) de Firebase **nunca** deben vivir en
  el frontend; solo la API las usa.

El frontend sí usa el SDK web de Firebase, pero **solo para Authentication** (login),
nunca para leer/escribir datos de negocio directamente.

## Roles y permisos (alto nivel)

Esta tabla ahora se hace cumplir en el backend (`app/services/auth_service.py`:
`require_role`, `verificar_acceso_estudiante`), no es solo documentación aspiracional.
Todo endpoint exige un token válido (Firebase ID token para docente/padre/admin, o
el JWT propio de PIN para estudiantes) y, cuando aplica, la relación correcta.

| Rol | Puede |
|---|---|
| Estudiante | Ver su propio perfil, jugar actividades, ver su propio progreso y recompensas |
| Docente | Ver progreso de sus estudiantes asignados, crear actividades, dejar feedback |
| Padre/Acudiente | Ver progreso y recompensas de sus hijos vinculados (RF11) |
| Administrador | Acceso total, incluida la exportación de auditoría |

## Despliegue sugerido

- **Frontend:** Firebase Hosting (gratis, HTTPS automático, CDN).
- **API (Python):** Cloud Run, Render o Railway (cualquiera que corra un contenedor
  Docker con FastAPI). Cloud Run es la opción más natural porque vive en el mismo
  proyecto de Google/Firebase.
- **Firestore / Auth / RTDB:** ya son servicios administrados de Firebase.
