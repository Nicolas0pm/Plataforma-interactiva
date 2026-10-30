# Máquina de premios (ESP32)

Programa de la máquina dispensadora: [`esp32.ino`](esp32.ino). Usa una ESP32, un driver
A4988 y un motor paso a paso NEMA 17 que gira el tambor y suelta un juguete.

**Nadie toca la máquina por dentro.** Todo se hace desde páginas web: la de la propia
máquina (solo la primera vez, para darle el WiFi) y el panel del docente en la plataforma.

## Conexiones

| ESP32 | A4988 |
|---|---|
| GPIO 4 | STEP |
| GPIO 5 | DIR |
| GPIO 18 | EN (LOW = encendido; en reposo queda apagado, sin zumbido ni calor) |

Un premio = 200 pasos en 2 segundos (una vuelta del tambor).

## Cargar el programa (lo hace el equipo, una sola vez)

1. Arduino IDE con el núcleo **esp32** de Espressif y la librería **ArduinoJson** (versión 7).
2. Abrir la carpeta `esp32/` (el archivo se llama igual que la carpeta, como pide Arduino).
3. Elegir la placa (por ejemplo, *ESP32 Dev Module*) y el puerto, y pulsar **Subir**.

El programa no lleva ningún WiFi escrito. La dirección de la plataforma está en la constante
`API` y la contraseña de la red propia de la máquina en `CLAVE_RED_PROPIA` (`premios123`).

## 1. Darle el WiFi del colegio (solo la primera vez)

1. Encender la máquina. Si no tiene WiFi guardado, o el que tiene no funciona, crea su propia
   red: **«Maquina-Premios-XXXX»** (XXXX son los 4 últimos dígitos de su dirección MAC).
2. Desde un celular, conectarse a esa red con la contraseña `premios123`.
3. Se abre sola una página de la máquina (**portal cautivo**: la máquina responde a cualquier
   dirección que pida el celular, así que el celular cree que es un WiFi con página de inicio).
   Si no se abre, entrar desde el navegador a `http://192.168.4.1`.
4. Elegir el WiFi del colegio en la lista (o escribir su nombre), escribir su contraseña y
   pulsar **Guardar y conectar**. La máquina guarda la red, se conecta y cierra su red propia.
   Si la contraseña está mal, la red «Maquina-Premios» sigue abierta para intentarlo otra vez.

Esto no necesita internet: la conexión es directa entre el celular y la máquina. Si algún
día la máquina pasa más de 2 minutos sin WiFi (por ejemplo, la llevan a otro colegio), vuelve
a abrir su red propia.

## 2. Registro en la plataforma (automático)

Con internet, la máquina se presenta sola con su **dirección MAC** y una clave que inventó la
primera vez que se encendió (queda guardada en su memoria). La plataforma la guarda en la
tabla `maquinas` con el código **MAQ-** y los 6 últimos dígitos de la MAC, y guarda solo el
hash de la clave.

## 3. Todo lo demás, desde el panel del docente

En «Máquina de premios del salón»:

- **Elegir la máquina:** aparece la lista de máquinas registradas que no tienen salón; el
  docente pulsa **Usar en mi salón**. Una máquina asignada a otro salón no se puede tomar.
- **Estado:** 🟢 en línea (con la red a la que está conectada) o 🟠 sin conexión.
- **Probar máquina:** pone un premio de prueba y la máquina gira el motor una vez.
- **Cambiar el WiFi:** el docente escribe la red y la contraseña nuevas; la máquina las recibe
  en su próxima consulta, prueba la red nueva y, si no funciona, vuelve a la anterior y avisa.
- **Desvincular:** la máquina queda libre para otro salón.

## Cómo habla con la plataforma

| Cada | Petición | Para qué |
|---|---|---|
| Hasta registrarse | `POST /api/maquinas/registro` `{mac, clave}` | Registrarse y conocer su código |
| 3 s | `GET /api/recompensas/cola/{device_id}` | Premios por soltar (y cuenta como «en línea») |
| Por premio | `POST /api/recompensas/{id}/confirmar-entrega` | Que no lo vuelva a soltar aunque se reinicie |
| 15 s | `GET /api/maquinas/yo?red=...` | Si tiene salón y si el docente le pidió otro WiFi |
| Al cambiar de red | `POST /api/maquinas/yo/wifi` `{ok, red, detalle}` | Avisar si la red nueva funcionó |

Todas, menos el registro, llevan las cabeceras `X-Device-Id` y `X-Device-Token`. Se sigue
aceptando el secreto compartido `DEVICE_SHARED_SECRET` (`X-Device-Secret`) en la cola para
una máquina configurada a mano.

## Puerto serie (depuración)

115200 baudios. Escribir `estado` (MAC, código, red y si la red propia está abierta),
`probar` (gira el motor una vez) u `olvidar` (borra el WiFi y abre la red propia).

> La API gratuita de Render se duerme tras 15 minutos sin uso; mientras la máquina esté
> encendida pregunta cada 3 segundos y la mantiene despierta.
