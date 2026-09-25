# Integración futura con ESP32

Esta carpeta es un placeholder para cuando llegues a la fase de hardware. La
arquitectura ya está pensada para esto (ver [`../docs/architecture.md`](../docs/architecture.md)),
así que cuando la retomes no deberías tener que rediseñar nada del backend/base de datos.

## Idea general

1. Cada dispensador físico tiene un `device_id` único (ej. `"aula-101"`).
2. Ese `device_id` se guarda en el documento `usuarios/{id}` del estudiante asignado a
   ese dispensador (campo `device_id`, ver `docs/data-model.md`).
3. Cuando la API detecta que un estudiante ganó una recompensa
   (`app/services/recompensas_service.py`), escribe un comando en Realtime Database:
   `cola_recompensas/{device_id}`.
4. El ESP32 tiene un listener permanente sobre ese nodo. Al recibir
   `comando: "dispensar"`, activa el servomotor/dispensador, y luego llama al endpoint
   `POST /api/recompensas/{id_historial}/confirmar-entrega` de la API (por HTTP, con
   WiFi) para marcar la recompensa como `"entregada"`.

## Librería recomendada

`Firebase-ESP-Client` (Mobizt) — es la más usada y mantenida para conectar un ESP32 a
Firebase Realtime Database vía WiFi. Repo: https://github.com/mobizt/Firebase-ESP-Client

## Esqueleto de referencia (pseudocódigo Arduino/C++)

```cpp
// esp32/firmware/main.ino (a crear cuando llegues a esta fase)
#include <WiFi.h>
#include <Firebase_ESP_Client.h>

#define WIFI_SSID "..."
#define WIFI_PASSWORD "..."
#define DATABASE_URL "https://tu-project-id-default-rtdb.firebaseio.com/"
#define API_KEY "..."
#define DEVICE_ID "aula-101"

FirebaseData stream;

void setup() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  // ... configurar FirebaseConfig / FirebaseAuth ...
  Firebase.RTDB.beginStream(&stream, "/cola_recompensas/" DEVICE_ID);
  Firebase.RTDB.setStreamCallback(&stream, streamCallback, streamTimeoutCallback);
}

void streamCallback(FirebaseStream data) {
  if (data.dataType() == "json") {
    // parsear { comando: "dispensar", ... }
    // activar el servo/motor del dispensador
    // luego hacer HTTP POST a la API para confirmar entrega
  }
}

void loop() {
  // nada, todo es event-driven vía el stream
}
```

## Cuando llegues a esta fase, necesitarás

- [ ] Definir el mecanismo físico (servomotor, solenoide, etc.)
- [ ] Cablear el ESP32 con el actuador y una fuente de alimentación adecuada
- [ ] Crear las credenciales de Firebase específicas para el dispositivo (idealmente un
      token con permisos limitados, no la Service Account de la API)
- [ ] Probar el flujo completo: actividad completada → recompensa generada → ESP32 la
      recibe → dispensa → confirma entrega → se refleja en el panel de docente/padres
