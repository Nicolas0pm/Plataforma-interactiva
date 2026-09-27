# Despliegue

El frontend y el backend se despliegan **por separado**:

| Parte | Dónde | Por qué |
|---|---|---|
| Frontend (`frontend/`) | **Firebase Hosting** | Gratis, HTTPS automático, mismo proyecto de Firebase, usa `404.html` solo. |
| Backend (`backend/`) | **Render** (plan gratis) | Se conecta al repositorio de GitHub y se vuelve a desplegar solo con cada `git push`. Usa el `Dockerfile`, así que también sirve para Cloud Run. |

Orden recomendado: **primero el backend** (para tener su URL) y **después el frontend**.

---

## 1. Backend en Render

1. Sube los últimos cambios a GitHub (`git push`).
2. Entra a <https://render.com>, inicia sesión con tu cuenta de GitHub y dale acceso al repositorio.
3. **New → Blueprint** y elige el repositorio. Render lee [`render.yaml`](../render.yaml) y crea el servicio `plataforma-ingles-kids-api`.
4. Te pedirá los valores marcados como secretos:

   | Variable | Qué poner |
   |---|---|
   | `FIREBASE_CREDENTIALS_JSON` | El **contenido completo** de `backend/serviceAccountKey.json` (ábrelo, copia todo y pégalo). |
   | `PIN_PEPPER` | **El mismo valor** que está en tu `backend/.env`. Si pones otro, los PIN de los niños ya registrados dejan de funcionar. |

   `JWT_SECRET` y `DEVICE_SHARED_SECRET` los genera Render solo.
5. Espera a que termine el despliegue y copia la URL (algo como `https://plataforma-ingles-kids-api.onrender.com`).
6. Comprueba que responde: al abrir la URL debe mostrar `{"status":"ok", ...}`.

> **Plan gratis de Render:** el servicio se "duerme" tras 15 minutos sin uso y la primera
> petición después tarda unos 30–50 segundos en despertarlo. Para la sustentación, abre la
> URL de la API un minuto antes.

## 2. Frontend en Firebase Hosting

1. Si la URL que te dio Render es distinta, cámbiala en
   [`frontend/js/config.js`](../frontend/js/config.js) (`API_PRODUCCION`).
2. Instala Node.js y la CLI de Firebase (una sola vez):
   ```bash
   sudo pacman -S nodejs npm
   ```
   ```bash
   sudo npm install -g firebase-tools
   ```
3. Inicia sesión (abre el navegador):
   ```bash
   firebase login
   ```
4. Desde la raíz del proyecto, publica:
   ```bash
   firebase deploy --only hosting
   ```
5. La app queda en **<https://plataforma-ingles-kids.web.app>**.

`firebase.json` ya está configurado: publica la carpeta `frontend/`, excluye
`dev-server.py`, desactiva el caché de HTML/JS/CSS (para que los cambios se vean al
volver a publicar) y agrega cabeceras de seguridad.

## 3. Comprobación final

- Abre <https://plataforma-ingles-kids.web.app> y entra como niño (`2MFE4D` / `1234`).
- Entra como docente y como padre con sus correos.
- Si algo falla con un error de CORS en la consola del navegador, revisa que
  `CORS_ORIGINS` en Render tenga exactamente la URL del frontend (sin `/` al final).

## Actualizar después

- **Backend:** basta con `git push`; Render lo vuelve a desplegar solo.
- **Frontend:** `firebase deploy --only hosting`.

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
