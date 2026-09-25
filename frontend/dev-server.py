"""
Servidor estático para desarrollo local que desactiva el caché del navegador.

`python -m http.server` no envía `Cache-Control`, así que el navegador puede
seguir sirviendo una versión vieja de un .js/.css desde su caché de disco
después de que lo edites, incluso navegando de nuevo a la página (hace falta
un hard-refresh). Este servidor agrega `Cache-Control: no-store` a cada
respuesta para que siempre veas el archivo tal como está en disco.

Uso:
    python dev-server.py [puerto]   # por defecto 5500
"""
import http.server
import os
import sys


class SinCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        # Igual que Firebase Hosting: ante una ruta inexistente se muestra 404.html.
        pagina = os.path.join(self.directory, "404.html")
        if code == 404 and os.path.isfile(pagina):
            with open(pagina, "rb") as f:
                cuerpo = f.read()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(cuerpo)
            return
        super().send_error(code, message, explain)


if __name__ == "__main__":
    # Sirve siempre esta misma carpeta (frontend/), sin importar desde dónde
    # se haya lanzado el proceso.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 5500
    http.server.test(HandlerClass=SinCacheHandler, port=puerto)
