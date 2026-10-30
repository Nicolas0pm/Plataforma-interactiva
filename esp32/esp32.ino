// Máquina de premios (ESP32 + driver A4988 + motor NEMA 17)
//
// Nadie toca la máquina: todo se hace desde páginas web.
//
// 1. Primera conexión (una sola vez, la hace quien instala la máquina):
//    si la máquina no tiene WiFi guardado, o el que tiene no funciona, crea su propia red
//    «Maquina-Premios-XXXX». Al conectarse desde el celular se abre sola una página (portal
//    cautivo, en http://192.168.4.1) para elegir el WiFi del colegio y escribir su contraseña.
// 2. Con internet, la máquina se registra sola en la plataforma con su dirección MAC; su
//    código es MAQ- y los 6 últimos dígitos de la MAC.
// 3. Desde el panel del docente se asigna al salón, se prueba y se le cambia el WiFi.
//
// Cada pocos segundos le pregunta a la plataforma por sus premios:
//   GET  {API}/api/recompensas/cola/{device_id}                   (X-Device-Id, X-Device-Token)
//   POST {API}/api/recompensas/{id_historial}/confirmar-entrega
//   GET  {API}/api/maquinas/yo?red=...       ← si el docente le pidió otro WiFi
//
// Librerías: ArduinoJson 7 (las demás vienen con el núcleo ESP32 de Arduino).

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <esp_random.h>

#define STEP_PIN 4
#define DIR_PIN 5
#define EN_PIN 18   // LOW = driver encendido, HIGH = apagado

const char* API = "https://plataforma-ingles-kids-api.onrender.com";
const char* CLAVE_RED_PROPIA = "premios123";  // contraseña de la red «Maquina-Premios-XXXX»

const unsigned long COLA_MS = 3000;           // cada cuánto pregunta por premios
const unsigned long CONFIG_MS = 15000;        // cada cuánto pregunta si hay WiFi nuevo
const unsigned long REGISTRO_MS = 10000;      // reintento del registro en la plataforma
const unsigned long ESPERA_WIFI_MS = 20000;   // tiempo máximo para conectarse a una red
const unsigned long SIN_WIFI_PORTAL_MS = 120000;  // sin WiFi tanto tiempo → vuelve a abrir su red

Preferences memoria;
WebServer servidor(80);
DNSServer dns;

String ssid, password, clave, deviceId, mac;
bool portalAbierto = false;
String mensajePortal = "";
unsigned long ultimaCola = 0, ultimaConfig = 0, ultimoRegistro = 0, sinWifiDesde = 0;

void cerrarPortal();

// Texto seguro dentro del HTML del portal (los nombres de red pueden traer comillas o <).
String html(const String& texto) {
  String r = texto;
  r.replace("&", "&amp;");
  r.replace("<", "&lt;");
  r.replace("'", "&#39;");
  r.replace("\"", "&quot;");
  return r;
}

String codificarUrl(const String& texto) {
  String r;
  const char* hex = "0123456789ABCDEF";
  for (unsigned char c : texto) {
    if (isalnum(c) || c == '-' || c == '_' || c == '.') r += (char)c;
    else { r += '%'; r += hex[c >> 4]; r += hex[c & 15]; }
  }
  return r;
}

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

// ---------------------------------------------------------------- memoria

void cargarMemoria() {
  memoria.begin("maquina", false);
  ssid = memoria.getString("ssid", "");
  password = memoria.getString("password", "");
  deviceId = memoria.getString("device_id", "");
  clave = memoria.getString("clave", "");
  if (clave.length() < 16) {  // la primera vez inventa su clave y no la cambia nunca
    char hex[33];
    for (int i = 0; i < 16; i++) sprintf(hex + i * 2, "%02x", (uint8_t)esp_random());
    clave = String(hex);
    memoria.putString("clave", clave);
  }
  memoria.end();
}

void guardarWifi(const String& nuevaRed, const String& nuevaClave) {
  ssid = nuevaRed;
  password = nuevaClave;
  memoria.begin("maquina", false);
  memoria.putString("ssid", ssid);
  memoria.putString("password", password);
  memoria.end();
}

void guardarDeviceId(const String& id) {
  deviceId = id;
  memoria.begin("maquina", false);
  memoria.putString("device_id", deviceId);
  memoria.end();
}

// ---------------------------------------------------------------- WiFi

bool conectar(const String& red, const String& clv) {
  if (!red.length()) return false;
  WiFi.begin(red.c_str(), clv.c_str());
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < ESPERA_WIFI_MS) {
    if (portalAbierto) {
      dns.processNextRequest();
      servidor.handleClient();
    }
    delay(50);
  }
  return WiFi.status() == WL_CONNECTED;
}

// ---------------------------------------------------------------- red propia (portal cautivo)

String nombreRedPropia() {
  return "Maquina-Premios-" + mac.substring(12, 14) + mac.substring(15, 17);
}

String paginaPortal() {
  String opciones = "";
  int n = WiFi.scanNetworks();
  for (int i = 0; i < n && i < 15; i++) {
    String red = WiFi.SSID(i);
    if (!red.length()) continue;
    String barras = WiFi.RSSI(i) > -60 ? "📶📶📶" : (WiFi.RSSI(i) > -75 ? "📶📶" : "📶");
    opciones += "<label class='red'><input type='radio' name='ssid' value='" + html(red) + "'> " + html(red) + " " + barras + "</label>";
  }
  String codigo = "MAQ-" + mac.substring(9, 11) + mac.substring(12, 14) + mac.substring(15, 17);
  return String("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'><title>Máquina de premios</title>"
    "<style>body{font-family:sans-serif;max-width:420px;margin:auto;padding:16px;background:#f6f9fc;color:#223345}"
    "h1{font-size:1.3rem}.red{display:block;padding:10px;margin:6px 0;background:#fff;border-radius:10px;border:1px solid #d9e2ec}"
    "input[type=text],input[type=password]{width:100%;padding:10px;margin:6px 0 12px;box-sizing:border-box;border-radius:10px;border:1px solid #d9e2ec}"
    "button{width:100%;padding:12px;border:0;border-radius:12px;background:#ff6f59;color:#fff;font-size:1rem}"
    ".aviso{padding:10px;border-radius:10px;background:#fff7e8}</style></head><body>"
    "<h1>🎁 Máquina de premios</h1><p>Código: <b>") + codigo + "</b></p>" +
    (mensajePortal.length() ? "<p class='aviso'>" + html(mensajePortal) + "</p>" : "") +
    "<form method='post' action='/guardar'><p>Elige el WiFi del colegio:</p>" + opciones +
    "<label class='red'><input type='radio' name='ssid' value=''> Otra red:</label>"
    "<input type='text' name='otra' placeholder='Nombre de la red' maxlength='32'>"
    "<p>Contraseña del WiFi:</p><input type='password' name='password' maxlength='64'>"
    "<button type='submit'>Guardar y conectar</button></form></body></html>";
}

void mostrarPortal() {
  servidor.send(200, "text/html; charset=utf-8", paginaPortal());
}

void guardarDesdePortal() {
  String red = servidor.arg("ssid");
  if (!red.length()) red = servidor.arg("otra");
  red.trim();
  String clv = servidor.arg("password");
  if (!red.length()) {
    mensajePortal = "Elige una red o escribe su nombre.";
    mostrarPortal();
    return;
  }
  servidor.send(200, "text/html; charset=utf-8",
                "<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
                "<body style='font-family:sans-serif;padding:16px'><h2>Conectando a " + html(red) + "…</h2>"
                "<p>Si la red y la contraseña son correctas, la máquina se conectará a internet y esta red "
                "«Maquina-Premios» desaparecerá. Si no, vuelve a conectarte a ella para intentarlo otra vez.</p>");
  delay(500);
  if (conectar(red, clv)) {
    guardarWifi(red, clv);
    mensajePortal = "";
    cerrarPortal();
  } else {
    mensajePortal = "No se pudo conectar a «" + red + "». Revisa la contraseña e inténtalo otra vez.";
  }
}

void redirigirAlPortal() {
  servidor.sendHeader("Location", "http://192.168.4.1/", true);
  servidor.send(302, "text/plain", "");
}

void abrirPortal() {
  if (portalAbierto) return;
  WiFi.mode(WIFI_AP_STA);  // red propia + seguir intentando el WiFi guardado
  WiFi.softAP(nombreRedPropia().c_str(), CLAVE_RED_PROPIA);
  dns.start(53, "*", WiFi.softAPIP());  // responde «soy yo» a cualquier dirección
  servidor.on("/", HTTP_GET, mostrarPortal);
  servidor.on("/guardar", HTTP_POST, guardarDesdePortal);
  servidor.onNotFound(redirigirAlPortal);  // así el celular abre la página solo
  servidor.begin();
  portalAbierto = true;
  Serial.println("Red propia abierta: " + nombreRedPropia() + " (http://192.168.4.1)");
}

void cerrarPortal() {
  if (!portalAbierto) return;
  dns.stop();
  servidor.stop();
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_STA);
  portalAbierto = false;
  Serial.println("Conectada a " + ssid + ": red propia cerrada");
}

// ---------------------------------------------------------------- plataforma

int peticion(const char* metodo, const String& ruta, const String& cuerpo, String* respuesta) {
  WiFiClientSecure cliente;
  cliente.setInsecure();  // HTTPS sin validar el certificado, para no tener que actualizarlo
  HTTPClient http;
  http.setTimeout(15000);  // la API gratuita puede tardar en despertar
  http.begin(cliente, String(API) + ruta);
  http.addHeader("Content-Type", "application/json");
  if (deviceId.length()) {
    http.addHeader("X-Device-Id", deviceId);
    http.addHeader("X-Device-Token", clave);
  }
  int codigo = http.sendRequest(metodo, cuerpo);
  if (respuesta) *respuesta = codigo > 0 ? http.getString() : "";
  http.end();
  return codigo;
}

void registrarse() {
  JsonDocument doc;
  doc["mac"] = mac;
  doc["clave"] = clave;
  String cuerpo, respuesta;
  serializeJson(doc, cuerpo);
  if (peticion("POST", "/api/maquinas/registro", cuerpo, &respuesta) == 200) {
    JsonDocument r;
    if (!deserializeJson(r, respuesta)) {
      guardarDeviceId(r["device_id"] | "");
      Serial.println("Registrada en la plataforma como " + deviceId);
    }
  } else {
    Serial.println("No se pudo registrar en la plataforma; se reintenta");
  }
}

void consultarCola() {
  String respuesta;
  int codigo = peticion("GET", "/api/recompensas/cola/" + deviceId, "", &respuesta);
  if (codigo == 401) {  // la plataforma no la reconoce: se registra de nuevo
    guardarDeviceId("");
    return;
  }
  if (codigo != 200) return;
  JsonDocument cola;
  if (deserializeJson(cola, respuesta)) return;
  for (JsonObject premio : cola.as<JsonArray>()) {
    String id = premio["id_historial"] | "";
    if (!id.length()) continue;
    soltarPremio();
    peticion("POST", "/api/recompensas/" + id + "/confirmar-entrega", "", nullptr);
    Serial.println("Premio entregado: " + id);
  }
}

void avisarWifi(bool ok, const String& red, const char* detalle) {
  JsonDocument doc;
  doc["ok"] = ok;
  doc["red"] = red;
  if (detalle) doc["detalle"] = detalle;
  String cuerpo;
  serializeJson(doc, cuerpo);
  peticion("POST", "/api/maquinas/yo/wifi", cuerpo, nullptr);
}

void consultarConfiguracion() {
  String respuesta;
  if (peticion("GET", "/api/maquinas/yo?red=" + codificarUrl(ssid), "", &respuesta) != 200) return;
  JsonDocument yo;
  if (deserializeJson(yo, respuesta) || yo["wifi"].isNull()) return;
  // El docente pidió otro WiFi desde su panel: se prueba y, si falla, se vuelve al anterior.
  String nuevaRed = yo["wifi"]["ssid"] | "";
  String nuevaClave = yo["wifi"]["password"] | "";
  Serial.println("Cambiando a la red " + nuevaRed);
  WiFi.disconnect();
  if (conectar(nuevaRed, nuevaClave)) {
    guardarWifi(nuevaRed, nuevaClave);
    avisarWifi(true, nuevaRed, nullptr);
  } else if (conectar(ssid, password)) {
    avisarWifi(false, nuevaRed, "La máquina no pudo conectarse a esa red: revisa el nombre y la contraseña");
  }
}

// ---------------------------------------------------------------- puerto serie (depuración)

void leerSerie() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd == "estado") {
    Serial.printf("MAC %s | código %s | red %s | wifi %s | red propia %s\n", mac.c_str(), deviceId.c_str(),
                  ssid.c_str(), WiFi.status() == WL_CONNECTED ? "conectada" : "sin conexión",
                  portalAbierto ? "abierta" : "cerrada");
  } else if (cmd == "probar") {
    soltarPremio();
  } else if (cmd == "olvidar") {
    guardarWifi("", "");
    WiFi.disconnect();
    abrirPortal();
  }
}

// ---------------------------------------------------------------- programa

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, HIGH);  // driver apagado en reposo

  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  mac = WiFi.macAddress();
  cargarMemoria();
  Serial.println("Máquina de premios · MAC " + mac);

  if (!conectar(ssid, password)) abrirPortal();
}

void loop() {
  leerSerie();
  if (portalAbierto) {
    dns.processNextRequest();
    servidor.handleClient();
  }

  if (WiFi.status() != WL_CONNECTED) {
    if (!sinWifiDesde) sinWifiDesde = millis();
    if (!portalAbierto && millis() - sinWifiDesde > SIN_WIFI_PORTAL_MS) abrirPortal();
    return;  // el ESP32 sigue reintentando la red guardada por su cuenta
  }
  sinWifiDesde = 0;
  if (portalAbierto && ssid.length()) cerrarPortal();  // volvió el WiFi guardado

  unsigned long ahora = millis();
  if (!deviceId.length()) {
    if (!ultimoRegistro || ahora - ultimoRegistro > REGISTRO_MS) {
      ultimoRegistro = ahora;
      registrarse();
    }
    return;
  }
  if (!ultimaCola || ahora - ultimaCola > COLA_MS) {
    ultimaCola = ahora;
    consultarCola();
  }
  if (!ultimaConfig || ahora - ultimaConfig > CONFIG_MS) {
    ultimaConfig = ahora;
    consultarConfiguracion();
  }
}
