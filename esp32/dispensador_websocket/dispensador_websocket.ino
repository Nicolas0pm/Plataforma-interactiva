#include <WiFi.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>

const char* ssid = "TU_WIFI";
const char* password = "TU_CONTRASENA";

#define STEP_PIN 4
#define DIR_PIN 5
#define EN_PIN 18   // LOW = driver encendido, HIGH = apagado

WebSocketsServer webSocket = WebSocketsServer(81);

bool motorRunning = false;
unsigned long lastHeartbeat = 0;
const unsigned long heartbeatInterval = 5000; // 5 segundos
const unsigned long clientTimeout = 15000; // 15 segundos

struct ClientInfo {
    bool isConnected;
    unsigned long lastHeartbeat;
};

ClientInfo clients[WEBSOCKETS_SERVER_CLIENT_MAX];

void sendHeartbeat() {
    webSocket.broadcastTXT("heartbeat");
}

void checkClientTimeouts() {
    unsigned long currentTime = millis();
    for (int i = 0; i < WEBSOCKETS_SERVER_CLIENT_MAX; i++) {
        if (clients[i].isConnected && (currentTime - clients[i].lastHeartbeat > clientTimeout)) {
            Serial.printf("Cliente %d desconectado por timeout\n", i);
            webSocket.disconnect(i);
            clients[i].isConnected = false;
        }
    }
}

void moveMotor(bool isRight, int steps, int duration) {
    digitalWrite(EN_PIN, LOW);   // enciende el driver
    delay(2);

    digitalWrite(DIR_PIN, isRight ? HIGH : LOW);
    int delayBetweenSteps = duration * 1000 / steps;  // Calcula el retraso entre pasos en microsegundos
    for (int i = 0; i < steps; i++) {
        digitalWrite(STEP_PIN, HIGH);
        delayMicroseconds(delayBetweenSteps / 2);
        digitalWrite(STEP_PIN, LOW);
        delayMicroseconds(delayBetweenSteps / 2);
    }

    digitalWrite(EN_PIN, HIGH);  // apaga el driver
}

void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.printf("[%u] Desconectado!\n", num);
            clients[num].isConnected = false;
            break;
        case WStype_CONNECTED:
            {
                IPAddress ip = webSocket.remoteIP(num);
                Serial.printf("[%u] Conectado desde %d.%d.%d.%d\n", num, ip[0], ip[1], ip[2], ip[3]);
                clients[num].isConnected = true;
                clients[num].lastHeartbeat = millis();
            }
            break;
        case WStype_TEXT:
            clients[num].lastHeartbeat = millis();   // Cualquier mensaje cuenta como "sigo vivo"

            // Ignorar mensajes vacíos (evita que el ESP32 se reinicie)
            if (payload == NULL || length == 0) {
                Serial.println("Mensaje vacío recibido, ignorado");
                return;
            }

            Serial.printf("[%u] Texto recibido: %s\n", num, payload);

            // Manejar mensajes de heartbeat
            if (strcmp((char*)payload, "pong") == 0) {
                IPAddress ip = webSocket.remoteIP(num);
                Serial.printf("Pong recibido del cliente %d.%d.%d.%d\n", ip[0], ip[1], ip[2], ip[3]);
                return;
            }
            if (strcmp((char*)payload, "ping") == 0) {
                webSocket.sendTXT(num, "pong");
                return;
            }

            {
                // Procesar el mensaje JSON recibido
                DynamicJsonDocument doc(1024);
                DeserializationError error = deserializeJson(doc, payload, length);

                if (error) {
                    Serial.print("deserializeJson() falló: ");
                    Serial.println(error.c_str());
                    return;
                }

                // Verificar si el campo 'puntos' existe y es igual a 3
                if (doc.containsKey("puntos") && doc["puntos"] == 3) {
                    if (!motorRunning) {
                        motorRunning = true;
                        Serial.println("Moviendo motor...");
                        moveMotor(false, 200, 2000);
                        Serial.println("Motor detenido");
                        motorRunning = false;
                    } else {
                        Serial.println("Motor ocupado, intente más tarde");
                    }
                }
            }
            break;
        default:
            break;
    }
}

void setup() {
    pinMode(STEP_PIN, OUTPUT);
    pinMode(DIR_PIN, OUTPUT);
    pinMode(EN_PIN, OUTPUT);
    digitalWrite(EN_PIN, HIGH);  // driver apagado en reposo: sin zumbido ni calor

    Serial.begin(115200);
    WiFi.begin(ssid, password);

    while (WiFi.status() != WL_CONNECTED) {
        delay(1000);
        Serial.println("Conectando a WiFi...");
    }

    Serial.println("Conectado a la red WiFi");
    Serial.print("Dirección IP: ");
    Serial.println(WiFi.localIP());

    for (int i = 0; i < WEBSOCKETS_SERVER_CLIENT_MAX; i++) {
        clients[i].isConnected = false;
    }

    webSocket.begin();
    webSocket.onEvent(webSocketEvent);

    Serial.println("Servidor WebSocket iniciado");
}

void loop() {
    webSocket.loop();

    unsigned long currentTime = millis();
    if (currentTime - lastHeartbeat > heartbeatInterval) {
        sendHeartbeat();
        lastHeartbeat = currentTime;
    }

    checkClientTimeouts();
}
