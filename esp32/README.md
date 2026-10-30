# Máquina de premios (ESP32)

Programa de la máquina dispensadora: [`esp32.ino`](esp32.ino). Usa una ESP32, un driver
A4988 y un motor paso a paso NEMA 17 que gira el tambor y suelta un juguete.

## Conexiones

| ESP32 | A4988 |
|---|---|
| GPIO 4 | STEP |
| GPIO 5 | DIR |
| GPIO 18 | EN (LOW = encendido; en reposo queda apagado, sin zumbido ni calor) |

Un premio = 200 pasos en 2 segundos (una vuelta del tambor).

## Cargar el programa (una sola vez)

1. Arduino IDE con el núcleo **esp32** de Espressif y la librería **ArduinoJson** (versión 7).
2. Abrir la carpeta `esp32/` (el archivo se llama igual que la carpeta, como pide Arduino).
3. Elegir la placa (por ejemplo, *ESP32 Dev Module*) y el puerto, y pulsar **Subir**.

El programa no lleva el WiFi ni contraseñas escritos: se configuran desde la plataforma.

## Conectarla desde el panel del docente

1. Conectar la máquina al computador con el cable USB.
2. En el panel del docente, recuadro **Máquina de premios del salón**, escribir el nombre y la
   contraseña del WiFi del salón y pulsar **Conectar máquina por USB** (Chrome o Edge en un
   computador, porque usa Web Serial).
3. El navegador pide elegir el dispositivo USB. La página registra la máquina en la API, le
   envía el WiFi, la dirección de la API, su identificador (`maq-…`) y su token, y espera a
   que se conecte. La máquina guarda todo en su memoria: sirve en cualquier red y, si se
   cambia de salón o de WiFi, basta con conectarla otra vez.
4. Desconectar el cable. El recuadro muestra si la máquina está **en línea** y tiene el botón
   **Probar máquina**, que hace girar el motor una vez.

## Cómo entrega los premios

Cada 3 segundos la máquina pregunta a la API si tiene premios para soltar, con su token:

```
GET  /api/recompensas/cola/{device_id}                   X-Device-Token: <token>
POST /api/recompensas/{id_historial}/confirmar-entrega   X-Device-Id: <device_id>, X-Device-Token: <token>
```

Por cada premio gira el motor y confirma la entrega, así no lo vuelve a soltar aunque se
reinicie. Cada consulta le sirve al panel para saber que la máquina está en línea.

La API guarda solo el hash del token. Si se vuelve a conectar la máquina o se desvincula
desde el panel, el token anterior deja de servir. Sigue aceptándose el secreto compartido
`DEVICE_SHARED_SECRET` (cabecera `X-Device-Secret`) para una máquina configurada a mano.

## Mensajes por el puerto serie

115200 baudios, una línea JSON por mensaje. Sirven para depurar con el monitor serie:

| Envío | Qué hace |
|---|---|
| `{"cmd":"estado"}` | Responde si está configurada, su `device_id`, la red y su IP |
| `{"cmd":"probar"}` | Gira el motor una vez sin pasar por la API |
| `{"cmd":"olvidar"}` | Borra el WiFi y las credenciales guardadas |
| `{"cmd":"config", ...}` | Lo que envía el panel del docente al conectarla |

> La API gratuita de Render se duerme tras 15 minutos sin uso; mientras la máquina esté
> encendida pregunta cada 3 segundos y la mantiene despierta.
