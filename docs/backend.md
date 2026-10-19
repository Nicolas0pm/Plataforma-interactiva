# Backend (API en Python)

La API está en [`backend/`](../backend). Está hecha con **FastAPI** (Python 3.12) y es la
única parte que habla con la base de datos: el frontend nunca lee ni escribe en ella
directamente, siempre pasa por aquí. Así las reglas del juego (niveles, puntos, vidas,
premios) viven en un solo lugar y tienen pruebas automáticas.

> La integración con la máquina de premios (ESP32) todavía no está implementada en
> hardware; este documento no la cubre.

---

## 1. Cómo se conecta a la base de datos

### Dónde están los datos

Todo está en **PostgreSQL (Neon)**: usuarios, contraseñas (cifradas), temario, progreso,
intentos, comentarios, premios y auditoría. Ver [`data-model.md`](data-model.md). La
plataforma ya no usa Firebase: el login y la cola de la máquina de premios los resuelve la
propia API.

### La conexión a PostgreSQL: `db.py`

[`app/db.py`](../backend/app/db.py) crea la conexión con **SQLAlchemy** a partir de la
variable `DATABASE_URL` (la cadena de conexión que da Neon). Las tablas están en
[`app/models/tablas.py`](../backend/app/models/tablas.py) y se crean solas al arrancar si
no existen; si la base está vacía, también se carga el temario.

Cada petición recibe su propia **sesión** (`Depends(get_db)`) y todo lo que escribe va en
**una transacción**:

- Si la petición termina bien, se guarda (justo antes de responder, ver `RutaConTransaccion`).
- Si termina con un error esperado (`HTTPException`: PIN incorrecto, sin permiso...), también
  se guarda lo que alcanzó a escribir, como el contador de PIN fallidos o la auditoría.
- Si falla por un error inesperado, se deshace todo: no quedan datos a medias.

Neon "duerme" la base tras unos minutos sin uso; la conexión revisa que siga viva antes de
usarla (`pool_pre_ping`), así que la primera consulta después de un rato solo tarda un poco más.

Toda la configuración sale de variables de entorno (`backend/.env` en local, el panel de
Render en producción). Ver [`despliegue.md`](despliegue.md).

### Modo de prueba sin Neon

Con `USE_FAKE_DB=true` (y `DATABASE_URL` vacío) la API usa **SQLite en memoria**, con las
mismas tablas, y permite un login de desarrollo sin contraseña. Sirve para desarrollar
sin tocar los datos reales y es lo que usan las pruebas automáticas. Al arrancar en este
modo se carga el temario solo.

### Rendimiento

- El temario fijo se arma en memoria al arrancar (no se consulta).
- El panel del docente trae el progreso de **todos** sus estudiantes con una consulta por
  tabla (no una por niño), y los últimos intentos de cada uno con una sola consulta.
- Neon conviene crearlo en la misma región que la API de Render (Oregón → AWS `us-west-2`)
  para que cada consulta tarde pocos milisegundos.
- Las respuestas van comprimidas (gzip) y marcadas `Cache-Control: no-store` (son datos
  personales y de progreso: ningún navegador debe guardarlos).

---

## 2. Estructura del código

```
backend/
├── app/
│   ├── main.py              Arranque: rutas, CORS, gzip, manejo de errores
│   ├── config.py            Variables de entorno (base de datos, secretos, umbrales)
│   ├── db.py                Conexión a PostgreSQL y transacción por petición
│   ├── curriculo.py         El temario: vocabulario y gramática
│   ├── gramatica_extra.py   Lecciones 3 y 4 de cada tema de gramática
│   ├── models/schemas.py    Qué datos entran y salen (validación con Pydantic)
│   ├── models/tablas.py     Las tablas de la base de datos (SQLAlchemy)
│   ├── routers/             Las rutas HTTP (una por tema)
│   └── services/            La lógica de negocio
├── scripts/                 Herramientas (verificar la conexión, cargar temario, contraseñas)
├── tests/                   Pruebas automáticas (pytest)
├── Dockerfile               Imagen para desplegar en Render
└── requirements.txt
```

La arquitectura es por capas: **rutas → servicios → base de datos**. Las rutas solo reciben la
petición, revisan permisos y llaman a un servicio; los servicios tienen las reglas.

---

## 3. Seguridad y sesiones

[`auth_service.py`](../backend/app/services/auth_service.py) decide quién es cada petición:

- **Docentes y padres** inician sesión con **correo + contraseña** (`POST /api/usuarios/login`):
  - La contraseña (mínimo 8 caracteres) se guarda como **hash scrypt** con sal propia, nunca
    en texto plano.
  - Un correo inexistente y una contraseña equivocada dan la misma respuesta (y tardan lo
    mismo), para no revelar qué correos tienen cuenta.
  - Tras 5 intentos fallidos seguidos, ese correo se bloquea 10 minutos.
  - Si es correcto, la API entrega su propio token (JWT) que vence a las 8 horas
    (`JWT_ADULTO_EXP_MINUTOS`). Puede cambiar su contraseña desde su panel.
  - No hay correos: si alguien olvida su contraseña, el admin le asigna una temporal con
    `python scripts/asignar_password.py <correo>`. Las cuentas de admin se crean con el
    mismo script (`--crear-admin "Nombre"`); nadie puede registrarse como admin.
- **Niños** entran con **código + PIN** ([`estudiantes_service.py`](../backend/app/services/estudiantes_service.py)):
  - El código es de 6 letras y números sin caracteres confusos (sin 0/O ni 1/I).
  - El PIN (4 dígitos) se guarda **cifrado** (hash con un "pepper" secreto), nunca en texto.
  - Tras 5 PIN equivocados, el código se bloquea 10 minutos.
  - Si es correcto, la API entrega su propio token (JWT) que vence a los 30 minutos.
- Con cada petición se revisa que el token sea válido y la cuenta siga activa: desactivar
  una cuenta cierra sus sesiones.
- Cada ruta exige un rol (`require_role`) y, para datos de un niño, que quien pregunta sea el
  propio niño, su docente o un padre vinculado (`verificar_acceso_estudiante`).

Registrar un niño exige la **autorización de datos** del adulto (Ley 1581) y registrar un
adulto exige aceptar los **términos**; ambas quedan guardadas con fecha y versión.

El correo de los adultos **no se confirma** (la plataforma no envía correos).

---

## 4. El temario y las lecciones

### Temario ([`curriculo.py`](../backend/app/curriculo.py))

| Apartado | Contenido |
|---|---|
| 📚 **Vocabulario** | 11 mundos (animales, colores, comida, números, ropa, cuerpo, casa, útiles, transporte, naturaleza, deportes) × **5 lecciones** de 8 preguntas. |
| ✏️ **Gramática** | 10 temas (to be, artículos, plurales, posesivos, presente simple, preposiciones, there is/are, can, presente continuo, pasado simple) × **4 lecciones**, cada uno con su explicación "Cómo se usa". |
| 👩‍🏫 **Del profe** | Los mundos que crea el docente del niño. |

El temario fijo se define en código y se **carga en la tabla `actividades`** sola al arrancar
con una base vacía; después de cambiarlo, `python scripts/verificar_conexion.py --sembrar`
lo actualiza (es seguro repetirlo: usa ids fijos).

### Catálogo ([`catalogo_service.py`](../backend/app/services/catalogo_service.py))

Junta los tres apartados para un niño concreto: el temario fijo más los mundos de **su**
docente. Los mundos del docente arman sus lecciones solos, en grupos de 8 preguntas.

### Camino guiado ([`lecciones_service.py`](../backend/app/services/lecciones_service.py))

- El niño **elige el apartado**; dentro de él, la plataforma elige la lección: la primera no
  aprobada, o cada 3 lecciones nuevas un **repaso** de la que le fue peor (< 80 %). Una
  lección solo se repasa si pasó al menos **1 hora** desde su último intento
  (`ESPERA_REPASO`), para no pedir de repaso la que se acaba de jugar.
- Puede **repetir** lecciones aprobadas (práctica): cuenta para su precisión, no da puntos.
- **5 vidas** que se guardan entre lecciones: cada error gasta una y se recupera una cada
  30 minutos. Sin vidas la lección se pierde y no se pueden empezar lecciones nuevas hasta
  recuperar alguna; practicar una lección ya aprobada no gasta vidas y, si se aprueba,
  devuelve una (`VIDAS_MAX` y `MINUTOS_POR_VIDA` en `app/curriculo.py`).
- **Preguntas de vocabulario variadas**: cada mundo tiene 5 lecciones con un enfoque distinto:
  1 *Conoce* (imagen → palabra), 2 *Encuentra* (palabras nuevas, imagen ↔ palabra),
  3 *Traduce* («perro» → Dog y dog → «perro»), 4 *Escribe* (ortografía y letra que falta)
  y 5 *Desafío* (¿sí o no?, "¿cuál NO es…?" y mezcla). Las traducciones y las preguntas
  "intruso" están en `curriculo.py` (`TRADUCCIONES`, `_INTRUSO`).
- **El servidor califica**: el navegador manda las respuestas y la API las compara con las
  correctas guardadas; no se confía en un puntaje del cliente.
- Guarda qué respondió mal cada niño: es lo que ve el docente como "errores frecuentes".

### Puntos, tienda y premios

- Cada acierto de una lección nueva o repaso aprobado vale **10 puntos**.
- Los puntos se gastan en la **tienda del perfil** ([`tienda_service.py`](../backend/app/services/tienda_service.py)):
  avatares y marcos. El nivel se calcula con todo lo ganado, así que comprar no lo baja.
- Al **completar un mundo** (todas sus lecciones, primera vez) se registra el premio en
  `historial_recompensas` ([`recompensas_service.py`](../backend/app/services/recompensas_service.py));
  el niño ve "¡Felicidades, completaste el mundo…!".

---

## 5. Rutas de la API

La documentación interactiva está en `/docs` (Swagger) cuando corre la API.

| Ruta | Quién | Para qué |
|---|---|---|
| `POST /api/usuarios` | adultos | Registrarse (adulto) o registrar un niño |
| `POST /api/usuarios/login-pin` | niño | Entrar con código + PIN |
| `GET /api/usuarios/sesion` | adultos | Perfil de quien inició sesión |
| `GET /api/usuarios/padre/{id}/hijos` | padre | Hijos vinculados |
| `PUT /api/usuarios/docente/{id}/dispensador` | docente | Máquina de premios del salón |
| `POST /api/vinculacion` | adultos | Vincularse a un niño con su código + PIN |
| `GET /api/lecciones/jugar` | niño | La lección que le toca (`?seccion=`) o repetir una (`?unidad=&leccion=`) |
| `POST /api/lecciones/resultado` | niño | Enviar respuestas; la API califica |
| `GET /api/lecciones/resumen/{id}` | niño, docente, padre | Camino, precisión, intentos, errores |
| `GET /api/lecciones/docente/{id}` | docente | Todo el panel del docente en una llamada |
| `GET/POST/DELETE /api/mundos…` | docente | Crear mundos y preguntas de selección múltiple (con imagen opcional: data URL JPG/PNG/WEBP/GIF de hasta ~300 KB) |
| `GET /api/tienda` · `POST /api/tienda/comprar` · `/equipar` | niño | Tienda del perfil |
| `GET /api/recompensas/estudiante/{id}` | niño, docente, padre | Mundos completados |
| `POST /api/feedback` · `GET /api/feedback/estudiante/{id}` | docente, padre | Comentarios |

---

## 6. Pruebas

```bash
cd backend && USE_FAKE_DB=true .venv/bin/python -m pytest -q
```

45 pruebas cubren: login con PIN y bloqueo, permisos por rol, vinculación, camino guiado,
vidas que se guardan y se recargan, repasos (y su espera de 1 hora), práctica sin puntos,
respuestas duplicadas, mundos completados, tienda, mundos del docente (solo selección
múltiple, con imagen), variedad y validez de las preguntas de vocabulario, confirmación del
correo de los adultos y el panel del docente.
