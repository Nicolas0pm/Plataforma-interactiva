# Despliegue

El frontend y el backend se despliegan **por separado**, los dos en **Render**, desde el
mismo repositorio. [`render.yaml`](../render.yaml) (un "Blueprint") crea ambos servicios:

| Servicio | Tipo en Render | URL | Qué es |
|---|---|---|---|
| `plataforma-ingles-kids-api` | Web Service (Docker) | `https://plataforma-ingles-kids-api.onrender.com` | Backend (FastAPI), usa `backend/Dockerfile`. |
| `plataforma-ingles-kids` | Static Site | `https://plataforma-ingles-kids.onrender.com` | Frontend (`frontend/`), sin build. |

Cada servicio se vuelve a desplegar solo con cada `git push`, y uno no afecta al otro.

---

## 1. Crear los dos servicios

1. Sube los últimos cambios a GitHub (`git push`); Render lee `render.yaml` desde ahí.
2. Entra a <https://dashboard.render.com> e inicia sesión con tu cuenta de GitHub.
3. **New → Blueprint**, elige el repositorio y dale acceso a Render si lo pide.
4. Render muestra los dos servicios. Completa los secretos del backend:

   | Variable | Qué poner |
   |---|---|
   | `FIREBASE_CREDENTIALS_JSON` | El **contenido completo** de `backend/serviceAccountKey.json` (ábrelo, copia todo y pégalo). |
   | `PIN_PEPPER` | **El mismo valor** que está en tu `backend/.env`. Si pones otro, los PIN de los niños ya registrados dejan de funcionar. |

   | `BREVO_API_KEY` | La API key de Brevo, para enviar el código de confirmación del correo (ver abajo). |
   | `EMAIL_REMITENTE` | El correo que verificaste como remitente en Brevo. |

   `JWT_SECRET` y `DEVICE_SHARED_SECRET` los genera Render solo.
5. **Apply** y espera a que los dos queden en verde ("Live").
6. Comprueba el backend: al abrir su URL debe mostrar `{"status":"ok", ...}`.

> **Si Render te da URLs distintas** (porque el nombre ya estaba ocupado), actualiza:
> - `API_PRODUCCION` en [`frontend/js/config.js`](../frontend/js/config.js) con la URL del backend, y
> - `CORS_ORIGINS` del backend (en Render → Environment) con la URL del frontend.

> **Plan gratis de Render:** el backend se "duerme" tras 15 minutos sin uso y la primera
> petición después tarda unos 30–50 segundos. Para la sustentación, abre la URL de la API
> un minuto antes. El sitio estático no se duerme.

## 2. Autorizar el dominio en Firebase (login de docentes y padres)

Firebase Authentication solo acepta inicios de sesión desde dominios autorizados:
**Firebase Console → Authentication → Configuración → Dominios autorizados → Agregar dominio**
y agrega `plataforma-ingles-kids.onrender.com` (o la URL que te haya dado Render).

## Correo de confirmación (código de 6 dígitos)

Al crear una cuenta, cada docente o padre recibe un código en su correo y debe escribirlo
para poder entrar. El plan gratis de Render **bloquea el envío por SMTP**, así que el correo
sale por la API de [Brevo](https://www.brevo.com) (gratis, 300 correos al día):

1. Crea una cuenta en Brevo.
2. **Senders, domains & dedicated IPs → Senders → Add a sender**: agrega el correo que
   aparecerá como remitente (puede ser un Gmail) y confírmalo desde el correo que te llega.
3. **SMTP & API → API keys → Generate a new API key**.
4. En Render (servicio `plataforma-ingles-kids-api` → Environment) pon `BREVO_API_KEY` y
   `EMAIL_REMITENTE` (el remitente del paso 2) y guarda.

Si no se configura, el correo **no se envía**: el código queda escrito en los logs del
backend en Render (sirve para probar, no para usuarios reales). Las cuentas creadas antes de
este cambio no necesitan confirmar nada.

## Alternativa: frontend en Firebase Hosting

Si prefieres Firebase Hosting para el frontend, `firebase.json` ya está listo:
instala Node.js y `firebase-tools`, ejecuta `firebase login` y luego
`firebase deploy --only hosting` (queda en `https://plataforma-ingles-kids.web.app`, que ya
está autorizado en Firebase y en `CORS_ORIGINS`).

## 3. Comprobación final

- Abre <https://plataforma-ingles-kids.onrender.com> y entra como niño (`2MFE4D` / `1234`).
- Entra como docente y como padre con sus correos.
- Crea una cuenta nueva y comprueba que llega el código al correo.
- Si algo falla con un error de CORS en la consola del navegador, revisa que
  `CORS_ORIGINS` en Render tenga exactamente la URL del frontend (sin `/` al final).

## Actualizar después

- **Backend y frontend:** basta con `git push`; Render vuelve a desplegar solo el servicio cuyos archivos cambiaron.

## Variables de entorno del backend

| Variable | Local (`backend/.env`) | Producción (Render) |
|---|---|---|
| `USE_FAKE_DB` | `false` (o `true` para pruebas sin Firebase) | `false` |
| `FIREBASE_CREDENTIALS_PATH` | `serviceAccountKey.json` | — |
| `FIREBASE_CREDENTIALS_JSON` | — | contenido de la clave |
| `FIREBASE_PROJECT_ID` | `plataforma-ingles-kids` | igual |
| `FIREBASE_REALTIME_DB_URL` | URL de Realtime Database | igual |
| `CORS_ORIGINS` | `*` | URLs del frontend publicado |
| `JWT_SECRET` | secreto local | generado por Render |
| `PIN_PEPPER` | secreto local | **el mismo que en local** |
| `DEVICE_SHARED_SECRET` | secreto local | generado por Render |
