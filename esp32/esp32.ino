// Máquina de premios (ESP32 + driver A4988 + motor NEMA 17)
//
// La máquina se configura desde el panel del docente: se conecta al computador por USB y,
// en «Máquina de premios del salón», el docente pulsa «Conectar máquina». La página le
// envía por el cable (Web Serial) el WiFi del salón y las credenciales de la máquina; la
// ESP32 las guarda en su memoria, así que sirve en cualquier red y no hay que reprogramarla.
//
// Después, cada pocos segundos pregunta a la API si hay un premio que soltar:
//   GET  {api}/api/recompensas/cola/{device_id}                  (X-Device-Token)
//   POST {api}/api/recompensas/{id_historial}/confirmar-entrega  (X-Device-Id, X-Device-Token)
//
// Mensajes por el puerto serie (115200 baudios, una línea JSON por mensaje):
//   {"cmd":"config","ssid":"...","password":"...","api":"https://...","device_id":"maq-...","token":"..."}
//   {"cmd":"estado"}    {"cmd":"probar"}    {"cmd":"olvidar"}
// La máquina responde con líneas JSON {"evento": "...", ...}.
//
// Librerías: ArduinoJson 7 (las demás vienen con el núcleo ESP32 de Arduino).

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>

#define STEP_PIN 4
#define DIR_PIN 5
#define EN_PIN 18   // LOW = driver encendido, HIGH = apagado

const unsigned long CONSULTA_MS = 3000;     // cada cuánto pregunta por premios
const unsigned long REINTENTO_WIFI_MS = 15000;
const unsigned long ESPERA_WIFI_MS = 20000; // tiempo máximo para conectarse a la red

Preferences memoria;
String ssid, password, api, deviceId, token;
unsigned long ultimaConsulta = 0;
unsigned long ultimoIntentoWifi = 0;
String lineaSerie;

// ---------------------------------------------------------------- motor

void moverMotor(bool derecha, int pasos, int duracionMs) {
  digitalWrite(EN_PIN, LOW);  // enciende el driver
  delay(2);
  digitalWrite(DIR_PIN, derecha ? HIGH : LOW);
  int retardo = duracionMs * 1000 / pasos;  // microsegundos entre pasos
  for (int i = 0; i < pasos; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(retardo / 2);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(retardo / 2);
  }
  digitalWrite(EN_PIN, HIGH);  // apaga el driver: sin zumbido ni calor en reposo
}

void soltarPremio() {
  moverMotor(false, 200, 2000);  // una vuelta del tambor = un premio
}

// ---------------------------------------------------------------- mensajes

void enviar(JsonDocument& doc) {
  serializeJson(doc, Serial);
  Serial.println();
}

void evento(const char* nombre, const char* detalle = nullptr) {
  JsonDocument doc;
  doc["evento"] = nombre;
  if (detalle) doc["detalle"] = detalle;
  enviar(doc);
}

bool configurada() {
  return ssid.length() && api.length() && deviceId.length() && token.length();
}

void reportarEstado() {
  JsonDocument doc;
  doc["evento"] = "estado";
  doc["configurada"] = configurada();
  doc["device_id"] = deviceId;
  doc["ssid"] = ssid;
  doc["wifi"] = WiFi.status() == WL_CONNECTED;
  if (WiFi.status() == WL_CONNECTED) doc["ip"] = WiFi.localIP().toString();
  enviar(doc);
}

// ---------------------------------------------------------------- configuración

void cargarConfiguracion() {
  memoria.begin("maquina", true);
  ssid = memoria.getString("ssid", "");
  password = memoria.getString("password", "");
  api = memoria.getString("api", "");
  deviceId = memoria.getString("device_id", "");
  token = memoria.getString("token", "");
  memoria.end();
}

void guardarConfiguracion() {
  memoria.begin("maquina", false);
  memoria.putString("ssid", ssid);
  memoria.putString("password", password);
  memoria.putString("api", api);
  memoria.putString("device_id", deviceId);
  memoria.putString("token", token);
  memoria.end();
}

bool conectarWifi() {
  if (!ssid.length()) return false;
  WiFi.disconnect(true);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid.c_str(), password.c_str());
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < ESPERA_WIFI_MS) {
    delay(250);
  }
  ultimoIntentoWifi = millis();
  if (WiFi.status() != WL_CONNECTED) {
    evento("wifi_error", "No se pudo conectar a la red: revise el nombre y la contraseña");
    return false;
  }
  JsonDocument doc;
  doc["evento"] = "wifi_ok";
  doc["ip"] = WiFi.localIP().toString();
  enviar(doc);
  return true;
}

void procesarComando(const String& linea) {
  JsonDocument doc;
  if (deserializeJson(doc, linea)) {
    evento("error", "Mensaje no válido");
    return;
  }
  String cmd = doc["cmd"] | "";
  if (cmd == "config") {
    ssid = doc["ssid"] | "";
    password = doc["password"] | "";
    api = doc["api"] | "";
    deviceId = doc["device_id"] | "";
    token = doc["token"] | "";
    while (api.endsWith("/")) api.remove(api.length() - 1);
    if (!configurada()) {
      evento("error", "Faltan datos de configuración");
      return;
    }
    guardarConfiguracion();
    evento("guardado");
    if (conectarWifi()) ultimaConsulta = 0;  // consulta de inmediato: el panel la ve en línea
  } else if (cmd == "estado") {
    reportarEstado();
  } else if (cmd == "probar") {
    soltarPremio();
    evento("premio_soltado", "prueba");
  } else if (cmd == "olvidar") {
    ssid = password = api = deviceId = token = "";
    guardarConfiguracion();
    WiFi.disconnect(true);
    evento("olvidada");
  } else {
    evento("error", "Comando desconocido");
  }
}

void leerSerie() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      lineaSerie.trim();
      if (lineaSerie.length()) procesarComando(lineaSerie);
      lineaSerie = "";
    } else if (lineaSerie.length() < 1024) {
      lineaSerie += c;
    }
  }
}

// ---------------------------------------------------------------- cola de la API

void confirmarEntrega(const String& idHistorial) {
  WiFiClientSecure cliente;
  cliente.setInsecure();  // la API usa HTTPS; sin validar el certificado para no tener que actualizarlo
  HTTPClient http;
  http.begin(cliente, api + "/api/recompensas/" + idHistorial + "/confirmar-entrega");
  http.addHeader("X-Device-Id", deviceId);
  http.addHeader("X-Device-Token", token);
  int codigo = http.POST("");
  http.end();
  if (codigo != 200) evento("error", "No se pudo confirmar la entrega");
}

void consultarCola() {
  WiFiClientSecure cliente;
  cliente.setInsecure();
  HTTPClient http;
  http.setTimeout(15000);  // la API gratuita puede tardar en despertar
  http.begin(cliente, api + "/api/recompensas/cola/" + deviceId);
  http.addHeader("X-Device-Token", token);
  int codigo = http.GET();
  if (codigo == 401) {
    evento("error", "La plataforma no reconoce esta máquina: vuelva a conectarla desde el panel del docente");
  } else if (codigo == 200) {
    JsonDocument cola;
    if (!deserializeJson(cola, http.getStream())) {
      for (JsonObject premio : cola.as<JsonArray>()) {
        String id = premio["id_historial"] | "";
        if (!id.length()) continue;
        soltarPremio();
        confirmarEntrega(id);
        JsonDocument doc;
        doc["evento"] = "premio_soltado";
        doc["id_historial"] = id;
        enviar(doc);
      }
    }
  }
  http.end();
}

// ---------------------------------------------------------------- programa

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, HIGH);  // driver apagado en reposo

  Serial.begin(115200);
  cargarConfiguracion();
  reportarEstado();
  if (configurada()) conectarWifi();
}

void loop() {
  leerSerie();
  if (!configurada()) return;

  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - ultimoIntentoWifi > REINTENTO_WIFI_MS) conectarWifi();
    return;
  }
  if (ultimaConsulta == 0 || millis() - ultimaConsulta > CONSULTA_MS) {
    ultimaConsulta = millis();
    consultarCola();
  }
}
