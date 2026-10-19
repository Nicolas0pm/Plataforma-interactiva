"""
RF03: carga el temario (app/curriculo.py: vocabulario + gramática, 26 lecciones) a
través de la API (POST /api/actividades). Normalmente no hace falta: la API carga el
temario sola al arrancar con una base vacía, y `python scripts/verificar_conexion.py
--sembrar` lo actualiza directo en PostgreSQL.

Uso:
    # Contra el backend en modo de prueba (USE_FAKE_DB=true) — crea un docente
    # temporal y no necesita ningún token:
    python scripts/seed_actividades.py

    # Contra un backend real (PostgreSQL de verdad), pasa el token de un
    # docente o admin ya autenticado:
    python scripts/seed_actividades.py --token "eyJ..." --base-url https://tu-api.com
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.curriculo import generar_actividades  # noqa: E402

# El temario completo (vocabulario + gramática) vive en app/curriculo.py.
ACTIVIDADES = generar_actividades()


def _post(base_url: str, path: str, body: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        base_url.rstrip("/") + path, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Error {exc.code} llamando a {path}: {detalle}") from exc


def _token_de_desarrollo(base_url: str) -> str:
    """Crea un docente temporal y su token, solo funciona con USE_FAKE_DB=true."""
    docente = _post(
        base_url, "/api/usuarios",
        {"nombre": "Docente Semilla", "edad": 99, "rol": "docente",
         "acudientes_ids": [], "docente_id": None, "email": "semilla@ejemplo.com",
         "acepta_terminos": True},
    )
    sesion = _post(base_url, "/api/usuarios/login-dev", {"id_usuario": docente["id_usuario"], "rol": "docente"})
    return sesion["token"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", default=None, help="Token de un docente/admin ya autenticado")
    args = parser.parse_args()

    token = args.token or _token_de_desarrollo(args.base_url)

    creadas = 0
    for actividad in ACTIVIDADES:
        payload = {k: v for k, v in actividad.items() if k != "activo"}
        _post(args.base_url, "/api/actividades", payload, token)
        creadas += 1

    print(f"{creadas} actividades del temario creadas en {args.base_url}.")


if __name__ == "__main__":
    main()
