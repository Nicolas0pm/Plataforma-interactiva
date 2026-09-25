# Cómo crear y configurar la base de datos en Firebase

Sigue estos pasos en orden. Toma unos 20-30 minutos la primera vez.

## 1. Crear el proyecto en Firebase

1. Entra a https://console.firebase.google.com
2. Clic en **"Agregar proyecto"**.
3. Nombre sugerido: `plataforma-ingles-kids` (o el que prefieras).
4. Desactiva Google Analytics si no lo vas a usar (no es necesario para este proyecto).
5. Espera a que se cree el proyecto.

## 2. Crear Firestore (base de datos principal)

1. En el menú lateral: **Compilación → Firestore Database**.
2. Clic en **"Crear base de datos"**.
3. Elige **modo producción** (usaremos `firestore.rules` para controlar permisos).
4. Elige la ubicación más cercana (ej. `southamerica-east1` para Latinoamérica).
5. Cuando esté creada, ve a la pestaña **Reglas** y pega el contenido de
   [`firestore.rules`](./firestore.rules) de este repo. Publica.
6. Ve a la pestaña **Índices** y crea los tres índices compuestos listados en
   [`firestore.indexes.json`](./firestore.indexes.json) (o usa la CLI, ver paso 6).

## 3. Crear las colecciones iniciales

Puedes crearlas a mano desde la consola (botón "Iniciar colección") o dejar que la API
las cree automáticamente al insertar el primer documento (Firestore no requiere crear
colecciones vacías de antemano). Colecciones que vas a usar:

- `usuarios`
- `actividades`
- `historial_actividades`
- `historial_recompensas`
- `feedback`
- Subcolección `usuarios/{id}/resultados`

Consulta [`../docs/data-model.md`](../docs/data-model.md) para los campos exactos de
cada una.

## 4. Activar Firebase Authentication (para docentes/padres/admin)

1. Menú lateral: **Compilación → Authentication → Comenzar**.
2. En la pestaña **Sign-in method**, habilita **Correo electrónico/contraseña**.
3. Los estudiantes NO usan Firebase Auth: usan el acceso simplificado (PIN) que maneja
   la API directamente contra el campo `pin_acceso` en `usuarios` (ver RF01 del documento).

## 5. Crear la Service Account para la API (Python)

La API necesita credenciales de administrador para leer/escribir Firestore sin pasar por
las reglas de seguridad del cliente.

1. En Firebase Console: ⚙️ (ajustes del proyecto) → **Cuentas de servicio**.
2. Clic en **"Generar nueva clave privada"** → se descarga un archivo `.json`.
3. Guárdalo como `backend/serviceAccountKey.json` (este archivo **ya está en `.gitignore`**,
   nunca lo subas al repositorio).
4. En `backend/.env` (cópialo desde `.env.example`) define:
   ```
   FIREBASE_CREDENTIALS_PATH=serviceAccountKey.json
   FIREBASE_PROJECT_ID=tu-project-id
   ```

## 6. (Opcional pero recomendado) Instalar Firebase CLI

Te sirve para desplegar reglas/índices/hosting desde la terminal en vez de la consola web.

```bash
npm install -g firebase-tools
firebase login
firebase init
# Selecciona: Firestore, Hosting, (Realtime Database si vas a usar la cola del ESP32)
# Cuando pregunte por el archivo de reglas, apunta a firebase/firestore.rules
# Cuando pregunte por índices, apunta a firebase/firestore.indexes.json
# Cuando pregunte por la carpeta pública del Hosting, apunta a frontend/

firebase deploy --only firestore:rules,firestore:indexes
firebase deploy --only hosting
```

## 7. Configurar el frontend (SDK web, solo para login)

1. En Firebase Console: ⚙️ → **Configuración del proyecto** → pestaña **General**.
2. En "Tus apps", clic en el ícono `</>` para registrar una app web.
3. Copia el objeto `firebaseConfig` que te da y pégalo en
   `frontend/js/firebase-config.js` (ya tiene el formato listo, solo reemplaza valores).

## 8. (Fase futura) Realtime Database para el ESP32

Cuando llegues a la integración con el ESP32:

1. Menú lateral: **Compilación → Realtime Database → Crear base de datos**.
2. Modo bloqueado (reglas cerradas), luego reemplaza las reglas por algo como:
   ```json
   {
     "rules": {
       "cola_recompensas": {
         "$device_id": {
           ".read": true,
           ".write": "auth != null"
         }
       }
     }
   }
   ```
   (Se puede afinar más adelante; para pruebas de laboratorio esto es suficiente. En
   producción real conviene autenticar también al propio ESP32 con un token, no dejar
   `.read: true` abierto.)
3. El ESP32 usará la librería `Firebase-ESP-Client` (Mobizt) para escuchar cambios en
   `cola_recompensas/{device_id}`. Hay una guía inicial en [`../esp32/README.md`](../esp32/README.md).

## Checklist rápido

- [ ] Proyecto Firebase creado
- [ ] Firestore creado en modo producción + reglas publicadas + índices creados
- [ ] Authentication con correo/contraseña habilitado
- [ ] Service Account descargada y puesta en `backend/serviceAccountKey.json`
- [ ] `backend/.env` configurado
- [ ] App web registrada y `frontend/js/firebase-config.js` actualizado
- [ ] (futuro) Realtime Database creada para la cola de recompensas del ESP32

## Verificar la configuración y sembrar actividades

Con `backend/.env` y `backend/serviceAccountKey.json` listos, desde `backend/`:

```bash
.venv/bin/python scripts/verificar_firebase.py            # revisa Firestore, Auth y Realtime Database
.venv/bin/python scripts/verificar_firebase.py --sembrar  # además crea el catálogo inicial de actividades
```

Sembrar es idempotente: las actividades que ya existen (por nombre) no se duplican.
