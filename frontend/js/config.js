// Dónde está la API. El frontend y el backend se despliegan por separado, así que
// aquí se decide a qué URL llamar según dónde esté abierta la página:
// - en tu computador (localhost) → la API local;
// - publicada (Render o Firebase Hosting) → la API desplegada en Render.
// `window.PIK_API_BASE_URL` permite forzar otra URL para pruebas.

// ⚠️ Cambia esto por la URL que te dé Render al desplegar el backend.
const API_PRODUCCION = "https://plataforma-ingles-kids-api.onrender.com";

const API_LOCAL = "http://localhost:8000";

const esLocal = ["localhost", "127.0.0.1", ""].includes(window.location.hostname);

export const API_BASE_URL = window.PIK_API_BASE_URL || (esLocal ? API_LOCAL : API_PRODUCCION);
