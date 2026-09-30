# Frontend (páginas web)

El frontend está en [`frontend/`](../frontend). Es **HTML, CSS y JavaScript puro**, sin
frameworks ni paso de compilación: los archivos se publican tal cual (en Render, como sitio
estático). Funciona en computador y en celular.

> La integración con la máquina de premios (ESP32) todavía no está implementada; este
> documento no la cubre.

---

## 1. Cómo se conecta a la base de datos

El frontend **no habla directamente con Firestore**: todo pasa por la API.

```
Navegador ──fetch (JSON)──▶ API (Render) ──Admin SDK──▶ Firestore
    │
    └── Firebase Authentication (solo el login de docentes y padres)
```

- [`js/config.js`](../frontend/js/config.js) decide a qué API llamar: en tu computador
  (`localhost`) usa `http://localhost:8000`; publicado usa la API de Render.
- [`js/api.js`](../frontend/js/api.js) es la **única** puerta hacia la API. `apiFetch()`:
  - agrega el token de sesión a cada petición;
  - nunca usa la caché del navegador para datos (así "atrás" no muestra progreso viejo);
  - si la sesión venció (401), cierra sesión y vuelve al inicio;
  - si el servidor tarda más de 3 s (se estaba "despertando" en el plan gratis de Render),
    muestra el aviso "Despertando el servidor…".
- [`js/firebase-config.js`](../frontend/js/firebase-config.js) tiene la configuración web de
  Firebase, que se usa **solo** para que docentes y padres inicien sesión con correo y
  contraseña. Esa configuración es pública por diseño; lo que protege los datos son las
  reglas de Firestore y la API.

### Sesión

[`js/session.js`](../frontend/js/session.js) guarda la sesión (token, rol, nombre) en
`localStorage`. `exigirRol()` protege cada página: si no hay sesión o el rol no corresponde,
manda al inicio. Si el navegador restaura una página desde su caché al usar "atrás", la
vuelve a cargar para no mostrar datos viejos.

---

## 2. Páginas

| Página | Para quién | Qué hace |
|---|---|---|
| `index.html` | todos | Elegir "Soy un niño / docente / padre". Si ya hay sesión: "¡Hola de nuevo! Continuar". |
| `kid-login.html` | niño | Dos pasos: 🪪 **código** (Siguiente) y 🔒 **PIN** en un teclado de números, con botón **"✅ Entrar"** para confirmar. |
| `kid-dashboard.html` | niño | Botones **📚 Vocabulario / ✏️ Gramática / 👩‍🏫 Del profe**, "Tu próxima lección", avatar con marco, puntos, camino de lecciones (✅ repetir, ▶ actual, 🔒 bloqueada) y últimos intentos. |
| `activity.html` | niño | La lección: ❤️ vidas, preguntas de selección múltiple, "❌ Incorrecto, la respuesta era…", tarjeta "Cómo se usa" en gramática y felicitación al final (o "¡Completaste un mundo!"). |
| `rewards.html` | niño | **Tienda** (avatares y marcos con puntos) y **mundos completados**. |
| `adult-login.html` | docente, padre | Iniciar sesión o crear cuenta (con aceptación de términos). |
| `teacher.html` | docente | Botones de vista: **Estudiantes · Necesitan ayuda · Progreso · Activos hoy · Mis mundos**; máquina del salón; registrar / ingresar niños. |
| `parent.html` | padre | Registrar / ingresar hijos y ver su progreso, últimos intentos y comentarios del docente. |
| `terminos.html` | todos | Términos de uso y política de datos (Ley 1581). |
| `404.html` | todos | Página "no encontrada". |

Cada página tiene su script en [`js/pages/`](../frontend/js/pages) con el mismo nombre.

### Panel del docente en detalle

- **Estudiantes**: cada niño con su avatar, código, lecciones, aciertos, "va en" (por
  apartado) y "última vez activo". "Ver progreso" abre aciertos por tema, errores frecuentes
  (qué respondió y cuál era la correcta), últimos intentos con hora y comentarios.
- **Necesitan ayuda**: solo los que tienen un motivo (precisión baja, perdió la misma lección
  varias veces, sin practicar una semana), con el motivo escrito.
- **Progreso**: temas más difíciles del grupo y tabla de avance.
- **Activos hoy**: quién jugó hoy y en qué sesiones ("9:10 – 9:40 p. m. · 5 lecciones").
- **Mis mundos**: crear mundos y agregar preguntas de **selección múltiple** (2 a 4 opciones,
  se marca la correcta). Cada 8 preguntas forman una lección.

---

## 3. Módulos compartidos (`js/`)

| Archivo | Qué hace |
|---|---|
| `api.js` | Llamadas a la API (ver arriba). |
| `config.js` | URL de la API según dónde está abierta la página. |
| `session.js` | Guardar/leer/cerrar sesión y proteger páginas por rol. |
| `nav.js` | Botones "← Volver" coherentes y redirecciones sin ensuciar el historial. |
| `i18n.js` | Todos los textos en **español e inglés** (botón ES/EN). |
| `tema.js` | Botón 🎨: temas Automático, Claro, Oscuro, Noche morada y Rosa dulce. |
| `html.js` | `esc()` para mostrar texto de la base de datos sin riesgo (evita XSS), formato de porcentajes y horas ("hoy 3:45 p. m."). |
| `estudiantes-ui.js` | Formularios de "Registrar niño" e "Ingresar niño con código" (docente y padre). |

## 4. Estilos

Todo el diseño está en [`css/style.css`](../frontend/css/style.css):

- **Colores con variables** (`--superficie`, `--tinta`…): cada tema solo cambia las variables.
- **Celular primero**: tarjetas en 2 columnas, pestañas apiladas y botones de al menos 48 px
  en pantallas de hasta 480 px.
- Tipografía **Baloo 2**, botones con efecto de "hundirse", avatares con marcos.
- Si el sistema pide menos movimiento, las animaciones se desactivan.

## 5. Probar en local

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload
```
```bash
cd frontend && python dev-server.py
```

Abre <http://localhost:5500>. `dev-server.py` es un servidor estático que desactiva la caché
(para ver los cambios al recargar) y muestra `404.html` en rutas que no existen.
