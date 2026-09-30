# Backend (API en Python)

La API está en [`backend/`](../backend). Está hecha con **FastAPI** (Python 3.12) y es la
única parte que habla con la base de datos: el frontend nunca lee ni escribe Firestore
directamente, siempre pasa por aquí. Así las reglas del juego (niveles, puntos, vidas,
premios) viven en un solo lugar y tienen pruebas automáticas.

> La integración con la máquina de premios (ESP32) todavía no está implementada en
> hardware; este documento no la cubre.

---

## 1. Cómo se conecta a la base de datos

### Firebase: tres servicios

| Servicio | Para qué se usa |
|---|---|
| **Firestore** | Base de datos principal: usuarios, temario, progreso, intentos, comentarios, auditoría. |
| **Authentication** | Inicio de sesión de docentes y padres con correo y contraseña. |
| **Realtime Database** | Reservada para la cola de premios de la máquina (fase futura). |

### La conexión: `firebase_service.py`

[`app/services/firebase_service.py`](../backend/app/services/firebase_service.py) inicializa
el **Firebase Admin SDK** una sola vez y entrega el cliente de Firestore al resto de la API.

El Admin SDK se autentica con una **cuenta de servicio** (una clave privada del proyecto) y
tiene permisos de administrador: por eso **solo el backend** la usa y nunca se sube a GitHub.
La clave se carga de una de dos formas ([`config.py`](../backend/app/config.py)):

| Dónde corre | De dónde sale la clave |
|---|---|
| Tu computador | El archivo `backend/serviceAccountKey.json` (variable `FIREBASE_CREDENTIALS_PATH`). |
| Render (producción) | La variable de entorno `FIREBASE_CREDENTIALS_JSON`, con el contenido del JSON. |

Toda la configuración sale de variables de entorno (`backend/.env` en local, el panel de
Render en producción). Ver [`despliegue.md`](despliegue.md).

### Modo de prueba sin Firebase

Con `USE_FAKE_DB=true` la API usa una base de datos **en memoria**
([`fake_firestore.py`](../backend/app/services/fake_firestore.py)) que imita la interfaz de
Firestore. Sirve para desarrollar sin tocar los datos reales y es la que usan las pruebas
automáticas. Al arrancar en este modo se carga el temario solo.

### Colecciones de Firestore

| Colección | Qué guarda |
|---|---|
| `usuarios/{id}` | Niños, docentes y padres: nombre, rol, código de acceso y PIN cifrado (niños), docente y acudientes vinculados, autorización de datos / términos aceptados. |
| `usuarios/{id}/resultados/actual` | **Todo el progreso del niño en un solo documento**: puntos, lecciones aprobadas, precisión por tema, mundos completados, últimos 20 intentos y su perfil (avatar, marco, puntos gastados). |
| `actividades` | Las preguntas: las del temario fijo (id como `animals-1-1`) y las que crean los docentes. |
| `mundos_docente` | Los mundos que crea cada docente (con el contador `n_preguntas`). |
| `intentos_leccion` | Historial completo de cada lección jugada, con sus errores (para análisis de la prueba piloto). |
| `feedback` | Comentarios del docente sobre un niño. |
| `historial_recompensas` | Cada mundo completado (el "premio"). |
| `auditoria` | Registro de solo-inserción: logins, registros, lecciones, compras, errores. |
| `intentos_pin` | Contador de PIN fallidos por código (bloqueo de 10 minutos tras 5 fallos). |

Las reglas de [`firebase/firestore.rules`](../firebase/firestore.rules) cierran la escritura
desde el navegador: aunque alguien tenga la configuración web de Firebase, no puede escribir
en la base de datos. Solo la API (Admin SDK) escribe.

### Rendimiento

La API corre en Render (EE. UU.) y Firestore en São Paulo, así que cada consulta cruza el
continente. Por eso:

- El temario fijo se arma en memoria al arrancar (no se consulta).
- El progreso del niño y sus últimos intentos van en **un solo documento**.
- El panel del docente trae el progreso de **todos** sus estudiantes en una sola consulta
  (`get_all`) y los mundos del docente una sola vez.
- Las respuestas van comprimidas (gzip) y marcadas `Cache-Control: no-store` (son datos
  personales y de progreso: ningún navegador debe guardarlos).

---

## 2. Estructura del código

```
backend/
├── app/
│   ├── main.py              Arranque: rutas, CORS, gzip, manejo de errores
│   ├── config.py            Variables de entorno (Firebase, secretos, umbrales)
│   ├── curriculo.py         El temario: vocabulario y gramática
│   ├── gramatica_extra.py   Lecciones 3 y 4 de cada tema de gramática
│   ├── models/schemas.py    Qué datos entran y salen (validación con Pydantic)
│   ├── routers/             Las rutas HTTP (una por tema)
│   └── services/            La lógica de negocio
├── scripts/                 Herramientas (verificar Firebase, cargar temario)
├── tests/                   Pruebas automáticas (pytest)
├── Dockerfile               Imagen para desplegar en Render
└── requirements.txt
```

La arquitectura es por capas: **rutas → servicios → Firestore**. Las rutas solo reciben la
petición, revisan permisos y llaman a un servicio; los servicios tienen las reglas.

---

## 3. Seguridad y sesiones

[`auth_service.py`](../backend/app/services/auth_service.py) decide quién es cada petición:

- **Docentes y padres** inician sesión con Firebase Authentication en el navegador y mandan
  su *ID token*; la API lo verifica con el Admin SDK.
- **Niños** entran con **código + PIN** ([`estudiantes_service.py`](../backend/app/services/estudiantes_service.py)):
  - El código es de 6 letras y números sin caracteres confusos (sin 0/O ni 1/I).
  - El PIN (4 dígitos) se guarda **cifrado** (hash con un "pepper" secreto), nunca en texto.
  - Tras 5 PIN equivocados, el código se bloquea 10 minutos.
  - Si es correcto, la API entrega su propio token (JWT) que vence a los 30 minutos.
- Cada ruta exige un rol (`require_role`) y, para datos de un niño, que quien pregunta sea el
  propio niño, su docente o un padre vinculado (`verificar_acceso_estudiante`).

Registrar un niño exige la **autorización de datos** del adulto (Ley 1581) y registrar un
adulto exige aceptar los **términos**; ambas quedan guardadas con fecha y versión.

---

## 4. El temario y las lecciones

### Temario ([`curriculo.py`](../backend/app/curriculo.py))

| Apartado | Contenido |
|---|---|
| 📚 **Vocabulario** | 11 mundos (animales, colores, comida, números, ropa, cuerpo, casa, útiles, transporte, naturaleza, deportes) × **5 lecciones** de 8 preguntas. |
| ✏️ **Gramática** | 10 temas (to be, artículos, plurales, posesivos, presente simple, preposiciones, there is/are, can, presente continuo, pasado simple) × **4 lecciones**, cada uno con su explicación "Cómo se usa". |
| 👩‍🏫 **Del profe** | Los mundos que crea el docente del niño. |

El temario fijo se define en código y se **carga en Firestore** con
`python scripts/verificar_firebase.py --sembrar` (es seguro repetirlo: usa ids fijos).

### Catálogo ([`catalogo_service.py`](../backend/app/services/catalogo_service.py))

Junta los tres apartados para un niño concreto: el temario fijo más los mundos de **su**
docente. Los mundos del docente arman sus lecciones solos, en grupos de 8 preguntas.

### Camino guiado ([`lecciones_service.py`](../backend/app/services/lecciones_service.py))

- El niño **elige el apartado**; dentro de él, la plataforma elige la lección: la primera no
  aprobada, o cada 3 lecciones nuevas un **repaso** de la que le fue peor (< 80 %).
- Puede **repetir** lecciones aprobadas (práctica): cuenta para su precisión, no da puntos.
- **3 vidas**: cada error quita una; sin vidas la lección se pierde y se repite.
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
| `GET/POST/DELETE /api/mundos…` | docente | Crear mundos y preguntas de selección múltiple |
| `GET /api/tienda` · `POST /api/tienda/comprar` · `/equipar` | niño | Tienda del perfil |
| `GET /api/recompensas/estudiante/{id}` | niño, docente, padre | Mundos completados |
| `POST /api/feedback` · `GET /api/feedback/estudiante/{id}` | docente, padre | Comentarios |

---

## 6. Pruebas

```bash
cd backend && USE_FAKE_DB=true .venv/bin/python -m pytest -q
```

39 pruebas cubren: login con PIN y bloqueo, permisos por rol, vinculación, camino guiado,
vidas, repasos, práctica sin puntos, respuestas duplicadas, mundos completados, tienda,
mundos del docente (solo selección múltiple) y el panel del docente.
