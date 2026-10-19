# Integración futura con ESP32

Esta carpeta es un placeholder para cuando llegues a la fase de hardware. La
arquitectura ya está pensada para esto (ver [`../docs/architecture.md`](../docs/architecture.md)),
así que cuando la retomes no deberías tener que rediseñar nada del backend/base de datos.

## Idea general

1. Cada dispensador físico tiene un `device_id` único (ej. `"aula-101"`). El docente lo
   asigna a su salón desde su panel, y queda en la columna `device_id` de sus estudiantes
   (ver `docs/data-model.md`).
2. Cuando un estudiante completa un mundo, la API crea una fila en `historial_recompensas`
   con `estado = 'pendiente'` y ese `device_id` (`app/services/recompensas_service.py`).
   Esas filas pendientes son la **cola** de la máquina.
3. El ESP32 pregunta cada pocos segundos por su cola, por HTTPS:

   ```
   GET /api/recompensas/cola/{device_id}
   X-Device-Secret: <DEVICE_SHARED_SECRET>
   ```

   Respuesta: `[{"id_historial": "...", "id_usuario": "...", "comando": "dispensar", ...}]`
   (del premio más antiguo al más nuevo; `[]` si no hay nada).
4. Por cada premio activa el servomotor/dispensador y confirma:

   ```
   POST /api/recompensas/{id_historial}/confirmar-entrega
   X-Device-Secret: <DEVICE_SHARED_SECRET>
   ```

   El premio queda como `"entregada"` y sale de la cola, así que no se vuelve a soltar
   aunque la máquina se reinicie.

No hace falta ninguna librería especial: solo WiFi y HTTPS, que el ESP32 trae (`WiFi.h`,
`HTTPClient.h`) más `ArduinoJson` para leer la respuesta.

## Esqueleto de referencia (pseudocódigo Arduino/C++)

```cpp
// esp32/firmware/main.ino (a crear cuando llegues a esta fase)
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#define WIFI_SSID "..."
#define WIFI_PASSWORD "..."
#define API "https://plataforma-ingles-kids-api.onrender.com"
#define DEVICE_ID "aula-101"
#define DEVICE_SECRET "..."   // el DEVICE_SHARED_SECRET del backend (Render → Environment)

void setup() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(500);
}

void loop() {
  HTTPClient http;
  http.begin(String(API) + "/api/recompensas/cola/" + DEVICE_ID);
  http.addHeader("X-Device-Secret", DEVICE_SECRET);
  if (http.GET() == 200) {
    JsonDocument cola;
    deserializeJson(cola, http.getString());
    for (JsonObject premio : cola.as<JsonArray>()) {
      // activar el servo/motor del dispensador
      HTTPClient confirmar;
      confirmar.begin(String(API) + "/api/recompensas/" + premio["id_historial"].as<String>() + "/confirmar-entrega");
      confirmar.addHeader("X-Device-Secret", DEVICE_SECRET);
      confirmar.POST("");
      confirmar.end();
    }
  }
  http.end();
  delay(5000);  // vuelve a preguntar en 5 segundos
}
```

> El plan gratis de Render "duerme" la API tras 15 minutos sin uso: la primera consulta del
> día puede tardar ~50 s. Mientras la máquina esté preguntando cada 5 s, la API no se duerme
> (y eso gasta horas del plan gratis: 750 al mes alcanzan para un servicio encendido todo el mes).

## Cuando llegues a esta fase, necesitarás

- [ ] Definir el mecanismo físico (servomotor, solenoide, etc.)
- [ ] Cablear el ESP32 con el actuador y una fuente de alimentación adecuada
- [ ] Configurar `DEVICE_SHARED_SECRET` en el backend y en el firmware
- [ ] Probar el flujo completo: lección terminada → mundo completado → premio en la cola →
      ESP32 lo recibe → dispensa → confirma entrega → se refleja en el panel de docente/padres
