"""
Protección contra el abuso automatizado (RNF de seguridad y disponibilidad):

- **Límite de peticiones por dirección IP** (`LimitePorIP`): una ventana deslizante de 60
  segundos en memoria. El inicio de sesión tiene un límite propio, más bajo, para frenar a
  quien prueba muchos PIN o contraseñas; el resto de la API tiene uno general, holgado,
  porque todo un salón suele salir a internet por la misma IP. Si se supera, la API
  responde 429 con el encabezado `Retry-After`.
- **Tamaño máximo de las peticiones** (`TamanoMaximo`): un cuerpo más grande que
  `max_cuerpo_bytes` se rechaza con 413 antes de procesarlo, aunque no traiga
  `Content-Length`.

Los contadores viven en la memoria del proceso: en Render la API corre en una sola
instancia, así que basta. Con varias instancias habría que llevarlos a una base compartida.
"""
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import get_settings

_settings = get_settings()
VENTANA_SEGUNDOS = 60
RUTAS_DE_LOGIN = ("/api/usuarios/login", "/api/usuarios/login-pin")


def ip_del_cliente(request: Request) -> str:
    """Detrás del proxy de Render la IP real llega en X-Forwarded-For. Se toma la última
    entrada, la que agregó el proxy: las anteriores las puede inventar el cliente."""
    reenviado = request.headers.get("x-forwarded-for")
    if reenviado:
        return reenviado.split(",")[-1].strip()
    return request.client.host if request.client else "desconocida"


class LimitePorIP:
    def __init__(self):
        self._golpes: dict[tuple[str, str], deque] = defaultdict(deque)

    def reiniciar(self) -> None:
        self._golpes.clear()

    def permitir(self, ip: str, grupo: str, maximo: int, ahora: float | None = None) -> int:
        """0 si la petición pasa; si no, los segundos que faltan para volver a intentar."""
        ahora = time.monotonic() if ahora is None else ahora
        golpes = self._golpes[(ip, grupo)]
        while golpes and ahora - golpes[0] >= VENTANA_SEGUNDOS:
            golpes.popleft()
        if len(golpes) >= maximo:
            return max(1, int(VENTANA_SEGUNDOS - (ahora - golpes[0])) + 1)
        golpes.append(ahora)
        return 0


limite = LimitePorIP()


async def limitar_por_ip(request: Request, call_next):
    if not request.url.path.startswith("/api/") or request.method == "OPTIONS":
        return await call_next(request)
    ip = ip_del_cliente(request)
    if request.url.path in RUTAS_DE_LOGIN:
        espera = limite.permitir(ip, "login", _settings.limite_login_por_minuto)
    else:
        espera = limite.permitir(ip, "api", _settings.limite_api_por_minuto)
    if espera:
        return JSONResponse(
            {"detail": "Demasiadas peticiones seguidas. Espera un momento y vuelve a intentar."},
            status_code=429, headers={"Retry-After": str(espera)},
        )
    return await call_next(request)


class TamanoMaximo:
    """Middleware ASGI: rechaza con 413 los cuerpos de más de `maximo` bytes."""

    def __init__(self, app, maximo: int):
        self.app, self.maximo = app, maximo

    async def _rechazar(self, scope, receive, send):
        respuesta = JSONResponse({"detail": "La petición es demasiado grande."}, status_code=413)
        await respuesta(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        largo = dict(scope["headers"]).get(b"content-length")
        if largo is not None and largo.isdigit() and int(largo) > self.maximo:
            return await self._rechazar(scope, receive, send)

        recibido = 0
        excedido = False

        async def recibir():
            # Sin Content-Length el cuerpo llega por partes: al pasar el límite se corta ahí
            # y la respuesta de la ruta (que vio un cuerpo incompleto) se cambia por un 413.
            nonlocal recibido, excedido
            if excedido:
                return {"type": "http.request", "body": b"", "more_body": False}
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                recibido += len(mensaje.get("body", b""))
                if recibido > self.maximo:
                    excedido = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return mensaje

        async def enviar(mensaje):
            if not excedido:
                await send(mensaje)
            elif mensaje["type"] == "http.response.start":
                await self._rechazar(scope, receive, send)

        await self.app(scope, recibir, enviar)
