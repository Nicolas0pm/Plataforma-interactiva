# Matriz de cumplimiento de requisitos

Este documento traza cada requisito del documento de grado / `Requisitos - Plataforma
de Inglés con Recompensas Físicas.docx` contra el estado real del código, con
honestidad sobre qué queda pendiente y qué depende de decisiones de despliegue que
este repositorio no controla (dónde se aloja, con qué dominio, con qué política
operativa).

Leyenda: ✅ Implementado — 🟡 Parcial (se explica el motivo) — ⚙️ Depende del
despliegue (no es código de la app) — ❌ Pendiente.

## Requisitos funcionales

| ID | Estado | Dónde vive | Notas |
|---|---|---|---|
| RF01 | ✅ | `routers/usuarios.py` (`crear_usuario`, `login-pin`, `login-dev`), `kid-login.html` | Cada estudiante recibe un código corto único de 6 caracteres (`codigo_acceso`, sin caracteres ambiguos como 0/O o 1/I) que el docente ve en su panel; el niño lo escribe y luego marca su PIN de exactamente 4 dígitos. |
| RF02 | ✅ | `kid-login.html`, `kid-dashboard.html`, `activity.html` | Interfaz con emojis grandes, colores vivos y navegación de un toque. |
| RF03 | 🟡 | `activity.html`, `routers/actividades.py` | El único tipo de actividad es `vocabulario` (imagen/emoji + selección múltiple), con un catálogo inicial de 36 preguntas en 6 niveles (Animals/Colors/Food/Numbers/Transport/My body, ver `backend/scripts/seed_actividades.py`). No hay emparejamiento (drag & drop) ni pronunciación (esto último explícitamente fuera de alcance según el ajuste de RF03 en el documento de requisitos). |
| RF04 | ✅ | `services/progreso_service.py`, `routers/actividades.py` | El nivel se recalcula matemáticamente desde el puntaje total (nunca se guarda "a mano"), por eso no puede desincronizarse. 6 niveles con umbrales en `config.py: nivel_umbrales` (agregar uno nuevo es una entrada ahí + su mundo correspondiente en `kid-dashboard.js`). |
| RF05 | ✅ | `services/recompensas_service.py`, `rewards.html` | Cola de Realtime Database para el ESP32 lista pero no probada con hardware real (fase futura, ver `esp32/README.md`). El mensaje al ganar una recompensa depende de si el estudiante tiene un `device_id` asignado (dispensador sincronizado): con dispensador, se le dice que vaya a revisar la máquina; sin dispensador, solo se le felicita (sin mencionar un premio físico ni pedirle que hable con el profe) y en "Mis premios" tampoco se le muestra el estado Pendiente/Entregada, ya que no hay ninguna entrega física en curso. |
| RF06 | 🟡 | `teacher.html`, `routers/usuarios.py` (`/estadisticas`) | Métricas, lista de estudiantes, registro de estudiantes y feedback sí están. "Asignar actividad" (CA2) hoy es implícito: toda actividad activa de un nivel queda disponible para cualquier estudiante de ese nivel; no hay asignación 1 a 1 por estudiante todavía. |
| RF07 | ✅ | `parent.html`, `routers/usuarios.py` (`/hijos`) | Incluye el bug corregido de `acudientes_ids` (ver más abajo). |
| RF08 | 🟡 | `activity.js` (modal + confeti CSS) | Feedback visual inmediato sí; feedback auditivo (RNF-UX-03) no se implementó — no hay archivos de audio en el proyecto. |
| RF09 | 🟡 | `historial_actividades`, `/estadisticas` | Guarda tiempo, intentos y puntaje por intento, y expone promedios/activos-hoy/necesitan-ayuda. No se calculan explícitamente "errores frecuentes" (CA1) como una estadística agregada aparte. |
| RF11 | ✅ | `services/vinculacion_service.py`, `estudiantes-ui.js` (paneles de padre y docente) | El padre o docente escribe el código y el PIN del niño (demuestra que tiene acceso a su cuenta) y queda vinculado al instante; un niño puede tener varios acudientes; tras 5 intentos fallidos el código se bloquea 10 minutos. Si el niño no existe, el padre o docente lo registra desde el mismo panel. |

## Requisitos no funcionales

### Rendimiento
| ID | Estado | Notas |
|---|---|---|
| RNF-R-01 | ⚙️ | El frontend es estático (sin build), lo que favorece cargar rápido; el tiempo real depende del hosting elegido. |
| RNF-R-02 | ✅ | Las actividades se piden con un solo `fetch` sin dependencias pesadas. |
| RNF-R-03 | ⚙️ | Depende de la capacidad del backend/Firestore desplegado; no se hicieron pruebas de carga. |
| RNF-R-04 | ✅ | Cada actividad completada dispara `POST /completar` que persiste al instante. |

### Disponibilidad
| ID | Estado | Notas |
|---|---|---|
| RNF-DISP-01/02/03 | ⚙️ | Horario de disponibilidad, backups automáticos y notificaciones de mantenimiento son políticas/servicios que se configuran en el hosting (Firebase/Cloud Run), no lógica de esta app. |

### Seguridad
| ID | Estado | Notas |
|---|---|---|
| RNF-SEG-01 | ⚙️ | HTTPS lo entrega el hosting (Firebase Hosting/Cloud Run lo dan por defecto); en desarrollo local se usa HTTP. |
| RNF-SEG-02 | ✅ | Firebase Authentication + verificación de ID token en cada endpoint (`auth_service.py`). |
| RNF-SEG-03 | ✅ | `require_role` / `verificar_acceso_estudiante` en todos los routers — antes de esta revisión NINGÚN endpoint validaba esto. |
| RNF-SEG-04 | ✅ | Los tokens de PIN expiran a los 30 min (`JWT_PIN_EXP_MINUTOS`); el frontend cierra sesión automáticamente ante un 401. |

### Usabilidad
| ID | Estado | Notas |
|---|---|---|
| RNF-UX-01/02/04/05 | ✅ | Interfaz infantil separada de los paneles de adultos, navegación de un clic, feedback visual inmediato. |
| RNF-UX-03 | ❌ | No hay audio todavía (ni texto leído en voz alta). |

### Fiabilidad
| ID | Estado | Notas |
|---|---|---|
| RNF-FB-01 | ✅ | El nivel se deriva del puntaje acumulado, nunca se sobrescribe manualmente. |
| RNF-FB-02 | ✅ | Cubierto por `tests/test_recompensas.py` (umbral exacto, sin duplicados). |
| RNF-FB-03 | ✅ | Manejador global de excepciones en `main.py` registra cualquier error 500 en `auditoria`. |

### Mantenibilidad
| ID | Estado | Notas |
|---|---|---|
| RNF-MNT-01 | ✅ | `routers/` (HTTP), `services/` (lógica), `models/` (esquemas) separados. |
| RNF-MNT-02 | ✅ | Este documento + `README.md` + `docs/architecture.md` + `docs/data-model.md`. |
| RNF-MNT-03 | ✅ | Todo lo sensible/variable vive en `.env` (`config.py`), nunca hardcodeado. |

### Escalabilidad
| ID | Estado | Notas |
|---|---|---|
| RNF-ESC-01 | ✅ | Una actividad nueva es un documento Firestore (`POST /api/actividades`); el frontend la interpreta sin tocar código. |
| RNF-ESC-02 | ⚙️ | Firestore escala horizontalmente de forma nativa; no se probó con volúmenes grandes. |

### Portabilidad
| ID | Estado | Notas |
|---|---|---|
| RNF-PRT-01/02/03/06 | ✅ | HTML/CSS/JS estándar, responsivo (grid/flex + media queries), sin dependencias de un navegador específico. |
| RNF-PRT-04 | ✅ | FastAPI no depende de un proveedor de cómputo específico; solo Firestore/Auth atan a Firebase (documentado en `docs/architecture.md`). |
| RNF-PRT-05 | ✅ | Verificado corriendo en Windows en este entorno; Python/FastAPI son multiplataforma. |

### Compatibilidad
| ID | Estado | Notas |
|---|---|---|
| RNF-CMP-01/02/06/07 | ✅ | HTML5 + emojis nativos (sin librerías gráficas externas que puedan renderizar distinto entre navegadores). |
| RNF-CMP-03 | ✅ | No se usan formatos multimedia propietarios. |
| RNF-CMP-04 | 🟡 | Solo el reporte de auditoría se exporta en CSV hoy (`/api/auditoria/exportar.csv`); progreso/recompensas no tienen export propio todavía. |
| RNF-CMP-05 | ❌ | Fuera de alcance actual; la API REST documentada facilita integrarlo cuando exista un LMS objetivo. |

### Auditoría
| ID | Estado | Notas |
|---|---|---|
| RNF-AUD-01/04 | ✅ | Cada intento de login por PIN (éxito o fallo) se registra en `auditoria`. |
| RNF-AUD-02 | ✅ | `historial_actividades` guarda cada intento del estudiante. |
| RNF-AUD-03 | ✅ | Creación de actividades, feedback y vinculaciones quedan auditadas con el actor. |
| RNF-AUD-05 | ✅ | Cada recompensa generada se registra en `auditoria`. |
| RNF-AUD-06 | ✅ | Manejador global de excepciones. |
| RNF-AUD-07 | ✅ | `GET /api/auditoria/exportar.csv`, solo `admin`. |
| RNF-AUD-08 | ✅ | `firestore.rules`: nadie puede escribir/editar `auditoria` desde el cliente; solo el Admin SDK del backend. |
| RNF-AUD-09 | ❌ | No hay purga automática por antigüedad (requeriría una Cloud Function programada fuera del alcance de este scaffold). |

### Localización
| ID | Estado | Notas |
|---|---|---|
| RNF-LOC-01 | ✅ | Toggle ES/EN persistente (`js/i18n.js`). Limitación conocida: el texto generado dinámicamente por JS (nombres, comentarios) no se re-traduce sin recargar la página tras cambiar de idioma. |
| RNF-LOC-02/07 | 🟡 | Textos simples en español neutro; no hubo validación pedagógica formal del nivel lingüístico ni de terminología escolar local. |
| RNF-LOC-03 | ❌ | No hay audio con pronunciación todavía. |
| RNF-LOC-04 | ✅ | Emojis y colores como lenguaje visual universal para niños. |
| RNF-LOC-05/09 | 🟡 | El contenido de actividades/recompensas es genérico; adaptarlo al contexto colombiano es cuestión de datos (vía `POST /api/actividades`), no de código. |
| RNF-LOC-06 | ❌ | No se implementó configuración de formato de fecha/hora regional. |
| RNF-LOC-08 | ✅ | Cualquier docente puede crear sus propias actividades (RNF-ESC-01). |

### Tolerancia a fallos
| ID | Estado | Notas |
|---|---|---|
| RNF-TF-01 | ✅ | Progreso guardado automáticamente tras cada actividad. |
| RNF-TF-02/03/05/08/09 | 🟡 | El manejador global de excepciones evita que un error tumbe el servidor y el frontend muestra mensajes en vez de romperse; no se hicieron pruebas formales de inyección de fallos. |
| RNF-TF-04 | 🟡 | Se conserva el progreso ya guardado; una pregunta a medio responder si se corta la conexión sí se pierde. |
| RNF-TF-06 | ⚙️ | Firestore ofrece recuperación ante fallos como servicio administrado. |
| RNF-TF-07 | ❌ | No hay diálogos de confirmación en acciones críticas del frontend todavía (p. ej. antes de registrar un estudiante). |

## Bugs corregidos en esta revisión

- **Cero autenticación/autorización**: ningún endpoint validaba quién llamaba. Ahora
  todos exigen un token válido y, cuando aplica, la relación correcta
  (docente asignado / padre vinculado / el propio estudiante / admin).
- **`hijos_de_padre` roto**: filtraba por un campo `acudiente_id` que nunca existió;
  el campo real es `acudientes_ids` (arreglo). El panel de padres nunca encontraba a
  nadie. Corregido a `where("acudientes_ids", "array_contains", id_padre)` y
  verificado en el navegador de punta a punta.
- **Fuga del hash del PIN**: `estudiantes_de_docente`, `hijos_de_padre` y las
  estadísticas del docente devolvían el documento crudo de Firestore, incluyendo
  `pin_hash`. Se encontró probando el flujo real en el navegador durante esta
  revisión. Ahora esos endpoints usan `response_model=UsuarioOut` (o construyen el
  modelo explícitamente), que nunca incluye el PIN ni su hash.
- **CORS inválido**: `allow_credentials=True` combinado con `CORS_ORIGINS=*` no es
  válido (los navegadores lo rechazan) y de paso abría la API a cualquier origen.
  Ahora `cors_allow_credentials` se desactiva automáticamente cuando la lista de
  orígenes es `*`.
- **RF04 nunca implementado**: `nivel_logrado` se guardaba pero nunca cambiaba.
  Ahora se deriva matemáticamente del puntaje total en cada actividad completada.

## Marco legal (Ley 1581 de 2012, Decreto 1377 de 2013, Ley 1098 de 2006)

| Aspecto | Estado | Dónde vive | Notas |
|---|---|---|---|
| Términos de uso y política de datos | ✅ | `frontend/terminos.html` | Versión 1.0, enlazada desde la pantalla inicial. Falta completar el correo de contacto de los responsables. |
| Aceptación de términos (adultos) | ✅ | `adult-login.html`, `routers/usuarios.py` | Casilla obligatoria; la API rechaza el registro sin ella y guarda `terminos_aceptados` (versión y fecha). |
| Autorización de datos del menor | ✅ | `teacher.html`, `parent.html`, `routers/usuarios.py` | Casilla obligatoria al registrar un niño; se guarda `autorizacion_datos` (quién, rol, fecha, versión). Los niños no pueden crear su propia cuenta. |
| Derechos del titular (conocer, rectificar, suprimir) | 🟡 | `terminos.html` §2.6 | Se ejercen escribiendo al contacto del proyecto; no hay todavía un botón de "eliminar mis datos" en la app. |

## Simplificaciones deliberadas (para no inflar el alcance)

- El **modo de prueba** (`USE_FAKE_DB=true`, `POST /api/usuarios/login-dev`) existe
  solo para poder desarrollar y probar todo el flujo sin un proyecto de Firebase
  real; está deshabilitado por defecto y el backend lo rechaza explícitamente si
  `USE_FAKE_DB` no está activo.
- El **PIN de los estudiantes** se guarda con `sha256(pepper + pin)`. Para un PIN de
  4 dígitos esto no es a prueba de fuerza bruta offline si alguien roba la base de
  datos completa; es una mejora sobre texto plano, no una solución criptográfica
  fuerte. Suficiente para el alcance de este proyecto (niños de 6-8 años, acceso
  supervisado en el aula).
