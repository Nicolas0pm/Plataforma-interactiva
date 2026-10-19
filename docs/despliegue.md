# Despliegue

El frontend y el backend se despliegan **por separado**, los dos en **Render**, desde el
mismo repositorio, y la base de datos PostgreSQL vive en **Neon**.
[`render.yaml`](../render.yaml) (un "Blueprint") crea los dos servicios de Render:

| Servicio | Tipo en Render | URL | Qué es |
|---|---|---|---|
| `plataforma-ingles-kids-api` | Web Service (Docker) | `https://plataforma-ingles-kids-api.onrender.com` | Backend (FastAPI), usa `backend/Dockerfile`. |
| `plataforma-ingles-kids` | Static Site | `https://plataforma-ingles-kids.onrender.com` | Frontend (`frontend/`), sin build. |

Cada servicio se vuelve a desplegar solo con cada `git push`, y uno no afecta al otro.

---

## 0. Crear la base de datos en Neon

1. Entra a <https://console.neon.tech> (se puede iniciar sesión con GitHub) y crea un
   proyecto: nombre `plataforma-ingles-kids`, PostgreSQL 17, región **AWS US West 2
   (Oregon)**, la misma de la API en Render, para que cada consulta tarde poco.
2. En el proyecto: **Connect** → copia la cadena de conexión (empieza por
   `postgresql://` y termina en `?sslmode=require`). Es una contraseña: no la subas a GitHub.
3. Pégala en `backend/.env` como `DATABASE_URL=...` y comprueba desde `backend/`:

   ```bash
   .venv/bin/python scripts/verificar_conexion.py
   ```

   La primera vez crea las tablas y carga el temario.
4. **Solo si tenías datos en Firestore:** cópialos una vez (primero en ensayo, luego de verdad):

   ```bash
   .venv/bin/python scripts/migrar_desde_firestore.py
   .venv/bin/python scripts/migrar_desde_firestore.py --escribir
   ```

> **Plan gratis de Neon:** 0,5 GB (para el tamaño de este proyecto alcanza para años, ver
> [`data-model.md`](data-model.md#espacio-plan-gratis-de-neon-05-gb)). La base se "duerme"
> tras unos minutos sin uso y despierta en menos de un segundo con la primera consulta.

## 1. Crear los dos servicios

1. Sube los últimos cambios a GitHub (`git push`); Render lee `render.yaml` desde ahí.
2. Entra a <https://dashboard.render.com> e inicia sesión con tu cuenta de GitHub.
3. **New → Blueprint**, elige el repositorio y dale acceso a Render si lo pide.
4. Render muestra los dos servicios. Completa los secretos del backend:

   | Variable | Qué poner |
   |---|---|
   | `DATABASE_URL` | La cadena de conexión de Neon (la misma de `backend/.env`). |
   | `PIN_PEPPER` | **El mismo valor** que está en tu `backend/.env`. Si pones otro, los PIN de los niños ya registrados dejan de funcionar. |

   `JWT_SECRET` y `DEVICE_SHARED_SECRET` los genera Render solo.
5. **Apply** y espera a que los dos queden en verde ("Live").
6. Comprueba el backend: al abrir su URL debe mostrar `{"status":"ok", ...}`.

> **Si Render te da URLs distintas** (porque el nombre ya estaba ocupado), actualiza:
> - `API_PRODUCCION` en [`frontend/js/config.js`](../frontend/js/config.js) con la URL del backend, y
> - `CORS_ORIGINS` del backend (en Render → Environment) con la URL del frontend.

> **Plan gratis de Render:** el backend se "duerme" tras 15 minutos sin uso y la primera
> petición después tarda unos 30–50 segundos. Para la sustentación, abre la URL de la API
> un minuto antes. El sitio estático no se duerme.

## 2. Contraseñas de los docentes y padres

La plataforma no envía correos. Para darle una contraseña a un adulto (por ejemplo, a las
cuentas que venían de Firebase, que no traen la suya, o a alguien que la olvidó), desde
`backend/` con `DATABASE_URL` en `.env`:

```bash
.venv/bin/python scripts/asignar_password.py correo@ejemplo.com
```

Imprime una contraseña temporal; entrégasela a la persona y pídele que la cambie en su panel
(botón **🔑 Contraseña**). Para crear una cuenta de administrador:
`scripts/asignar_password.py admin@ejemplo.com --crear-admin "Nombre"`.

## 3. Comprobación final

- Abre <https://plataforma-ingles-kids.onrender.com> y entra como niño (`2MFE4D` / `1234`).
- Entra como docente y como padre con sus correos.
- Crea una cuenta nueva de docente: debe entrar directo a su panel.
- Si algo falla con un error de CORS en la consola del navegador, revisa que
  `CORS_ORIGINS` en Render tenga exactamente la URL del frontend (sin `/` al final).

## Actualizar después

- **Backend y frontend:** basta con `git push`; Render vuelve a desplegar solo el servicio cuyos archivos cambiaron.

## Variables de entorno del backend

| Variable | Local (`backend/.env`) | Producción (Render) |
|---|---|---|
| `DATABASE_URL` | cadena de conexión de Neon | igual |
| `USE_FAKE_DB` | `false` (o `true` para pruebas sin Neon) | `false` |
| `CORS_ORIGINS` | `*` | URLs del frontend publicado |
| `JWT_SECRET` | secreto local | generado por Render |
| `JWT_PIN_EXP_MINUTOS` / `JWT_ADULTO_EXP_MINUTOS` | `30` / `480` | igual |
| `PIN_PEPPER` | secreto local | **el mismo que en local** |
| `DEVICE_SHARED_SECRET` | secreto local | generado por Render |
