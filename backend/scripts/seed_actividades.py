"""
RF03: siembra un catálogo inicial de actividades de vocabulario en inglés,
agrupadas por nivel (1 = Animals, 2 = Colors, 3 = Food, 4 = Numbers, 5 = Transport,
6 = My body, ver frontend/js/pages/kid-dashboard.js — debe mantenerse sincronizado con
app/config.py: Settings.nivel_umbrales). Todas son del único tipo soportado hoy:
"vocabulario" (imagen/emoji + selección múltiple).

No agrega dependencias nuevas: usa solo la librería estándar.

Uso:
    # Contra el backend en modo de prueba (USE_FAKE_DB=true) — crea un docente
    # temporal y no necesita ningún token:
    python scripts/seed_actividades.py

    # Contra un backend real (Firebase de verdad), pasa el token de un
    # docente o admin ya autenticado:
    python scripts/seed_actividades.py --token "eyJ..." --base-url https://tu-api.com
"""
import argparse
import json
import urllib.error
import urllib.request

ACTIVIDADES = [
    # --- Nivel 1: Animals ---
    {"nombre": "Animals 1", "nivel": 1, "pregunta": "What animal is this?",
     "opciones": ["Dog", "Cat", "Bird", "Fish"], "respuesta_correcta": "Dog", "icono": "🐶"},
    {"nombre": "Animals 2", "nivel": 1, "pregunta": "What animal is this?",
     "opciones": ["Dog", "Cat", "Bird", "Fish"], "respuesta_correcta": "Cat", "icono": "🐱"},
    {"nombre": "Animals 3", "nivel": 1, "pregunta": "What animal is this?",
     "opciones": ["Dog", "Cat", "Bird", "Fish"], "respuesta_correcta": "Bird", "icono": "🐦"},
    {"nombre": "Animals 4", "nivel": 1, "pregunta": "What animal is this?",
     "opciones": ["Dog", "Cat", "Bird", "Fish"], "respuesta_correcta": "Fish", "icono": "🐟"},
    {"nombre": "Animals 5", "nivel": 1, "pregunta": "What animal is this?",
     "opciones": ["Horse", "Cow", "Pig", "Sheep"], "respuesta_correcta": "Horse", "icono": "🐴"},
    {"nombre": "Animals 6", "nivel": 1, "pregunta": "What animal is this?",
     "opciones": ["Horse", "Cow", "Pig", "Sheep"], "respuesta_correcta": "Cow", "icono": "🐮"},
    # --- Nivel 2: Colors ---
    {"nombre": "Colors 1", "nivel": 2, "pregunta": "What color is this?",
     "opciones": ["Red", "Blue", "Green", "Yellow"], "respuesta_correcta": "Red", "icono": "🔴"},
    {"nombre": "Colors 2", "nivel": 2, "pregunta": "What color is this?",
     "opciones": ["Red", "Blue", "Green", "Yellow"], "respuesta_correcta": "Blue", "icono": "🔵"},
    {"nombre": "Colors 3", "nivel": 2, "pregunta": "What color is this?",
     "opciones": ["Red", "Blue", "Green", "Yellow"], "respuesta_correcta": "Green", "icono": "🟢"},
    {"nombre": "Colors 4", "nivel": 2, "pregunta": "What color is this?",
     "opciones": ["Red", "Blue", "Green", "Yellow"], "respuesta_correcta": "Yellow", "icono": "🟡"},
    {"nombre": "Colors 5", "nivel": 2, "pregunta": "What color is this?",
     "opciones": ["Orange", "Purple", "Pink", "Black"], "respuesta_correcta": "Orange", "icono": "🟠"},
    {"nombre": "Colors 6", "nivel": 2, "pregunta": "What color is this?",
     "opciones": ["Orange", "Purple", "Pink", "Black"], "respuesta_correcta": "Purple", "icono": "🟣"},
    # --- Nivel 3: Food ---
    {"nombre": "Food 1", "nivel": 3, "pregunta": "What food is this?",
     "opciones": ["Apple", "Banana", "Bread", "Milk"], "respuesta_correcta": "Apple", "icono": "🍎"},
    {"nombre": "Food 2", "nivel": 3, "pregunta": "What food is this?",
     "opciones": ["Apple", "Banana", "Bread", "Milk"], "respuesta_correcta": "Banana", "icono": "🍌"},
    {"nombre": "Food 3", "nivel": 3, "pregunta": "What food is this?",
     "opciones": ["Apple", "Banana", "Bread", "Milk"], "respuesta_correcta": "Bread", "icono": "🍞"},
    {"nombre": "Food 4", "nivel": 3, "pregunta": "What food is this?",
     "opciones": ["Apple", "Banana", "Bread", "Milk"], "respuesta_correcta": "Milk", "icono": "🥛"},
    {"nombre": "Food 5", "nivel": 3, "pregunta": "What food is this?",
     "opciones": ["Pizza", "Egg", "Cheese", "Rice"], "respuesta_correcta": "Pizza", "icono": "🍕"},
    {"nombre": "Food 6", "nivel": 3, "pregunta": "What food is this?",
     "opciones": ["Pizza", "Egg", "Cheese", "Rice"], "respuesta_correcta": "Egg", "icono": "🥚"},
    # --- Nivel 4: Numbers ---
    {"nombre": "Numbers 1", "nivel": 4, "pregunta": "What number is this?",
     "opciones": ["One", "Two", "Three", "Four"], "respuesta_correcta": "One", "icono": "1️⃣"},
    {"nombre": "Numbers 2", "nivel": 4, "pregunta": "What number is this?",
     "opciones": ["One", "Two", "Three", "Four"], "respuesta_correcta": "Two", "icono": "2️⃣"},
    {"nombre": "Numbers 3", "nivel": 4, "pregunta": "What number is this?",
     "opciones": ["One", "Two", "Three", "Four"], "respuesta_correcta": "Three", "icono": "3️⃣"},
    {"nombre": "Numbers 4", "nivel": 4, "pregunta": "What number is this?",
     "opciones": ["One", "Two", "Three", "Four"], "respuesta_correcta": "Four", "icono": "4️⃣"},
    {"nombre": "Numbers 5", "nivel": 4, "pregunta": "What number is this?",
     "opciones": ["Five", "Six", "Seven", "Eight"], "respuesta_correcta": "Five", "icono": "5️⃣"},
    {"nombre": "Numbers 6", "nivel": 4, "pregunta": "What number is this?",
     "opciones": ["Five", "Six", "Seven", "Eight"], "respuesta_correcta": "Six", "icono": "6️⃣"},
    # --- Nivel 5: Transport ---
    {"nombre": "Transport 1", "nivel": 5, "pregunta": "What is this?",
     "opciones": ["Car", "Bus", "Bike", "Plane"], "respuesta_correcta": "Car", "icono": "🚗"},
    {"nombre": "Transport 2", "nivel": 5, "pregunta": "What is this?",
     "opciones": ["Car", "Bus", "Bike", "Plane"], "respuesta_correcta": "Bus", "icono": "🚌"},
    {"nombre": "Transport 3", "nivel": 5, "pregunta": "What is this?",
     "opciones": ["Car", "Bus", "Bike", "Plane"], "respuesta_correcta": "Bike", "icono": "🚲"},
    {"nombre": "Transport 4", "nivel": 5, "pregunta": "What is this?",
     "opciones": ["Car", "Bus", "Bike", "Plane"], "respuesta_correcta": "Plane", "icono": "✈️"},
    {"nombre": "Transport 5", "nivel": 5, "pregunta": "What is this?",
     "opciones": ["Train", "Boat", "Truck", "Helicopter"], "respuesta_correcta": "Train", "icono": "🚂"},
    {"nombre": "Transport 6", "nivel": 5, "pregunta": "What is this?",
     "opciones": ["Train", "Boat", "Truck", "Helicopter"], "respuesta_correcta": "Boat", "icono": "🚢"},
    # --- Nivel 6: My body ---
    {"nombre": "Body 1", "nivel": 6, "pregunta": "What part of the body is this?",
     "opciones": ["Eye", "Ear", "Nose", "Mouth"], "respuesta_correcta": "Eye", "icono": "👁️"},
    {"nombre": "Body 2", "nivel": 6, "pregunta": "What part of the body is this?",
     "opciones": ["Eye", "Ear", "Nose", "Mouth"], "respuesta_correcta": "Ear", "icono": "👂"},
    {"nombre": "Body 3", "nivel": 6, "pregunta": "What part of the body is this?",
     "opciones": ["Eye", "Ear", "Nose", "Mouth"], "respuesta_correcta": "Nose", "icono": "👃"},
    {"nombre": "Body 4", "nivel": 6, "pregunta": "What part of the body is this?",
     "opciones": ["Eye", "Ear", "Nose", "Mouth"], "respuesta_correcta": "Mouth", "icono": "👄"},
    {"nombre": "Body 5", "nivel": 6, "pregunta": "What part of the body is this?",
     "opciones": ["Hand", "Foot", "Leg", "Arm"], "respuesta_correcta": "Hand", "icono": "✋"},
    {"nombre": "Body 6", "nivel": 6, "pregunta": "What part of the body is this?",
     "opciones": ["Hand", "Foot", "Leg", "Arm"], "respuesta_correcta": "Foot", "icono": "🦶"},
]


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
        payload = {
            "nombre": actividad["nombre"],
            "descripcion": "",
            "nivel": actividad["nivel"],
            "tipo": "vocabulario",
            "puntaje_maximo": 100,
            "pregunta": actividad["pregunta"],
            "opciones": actividad["opciones"],
            "respuesta_correcta": actividad["respuesta_correcta"],
            "icono": actividad["icono"],
        }
        _post(args.base_url, "/api/actividades", payload, token)
        creadas += 1

    print(f"{creadas} actividades de vocabulario creadas en {args.base_url}.")


if __name__ == "__main__":
    main()
