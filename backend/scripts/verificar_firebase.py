"""
Verifica que la configuración de Firebase real (backend/.env + serviceAccountKey.json)
funcione, y opcionalmente siembra el catálogo inicial de actividades directamente en
Firestore con el Admin SDK (sin necesitar el token de un docente).

Uso (desde backend/):
    python scripts/verificar_firebase.py            # solo revisa la conexión
    python scripts/verificar_firebase.py --sembrar  # revisa y crea las actividades
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings  # noqa: E402

OK, FALLA, AVISO = "✅", "❌", "⚠️ "


def _revisar_configuracion(settings) -> bool:
    bien = True
    if settings.use_fake_db:
        print(f"{FALLA} USE_FAKE_DB=true en .env: ponlo en false para usar Firebase real.")
        bien = False
    from app.services.firebase_service import cargar_credenciales

    if not settings.firebase_credentials_json and not os.path.isfile(settings.firebase_credentials_path):
        print(f"{FALLA} No existe '{settings.firebase_credentials_path}' ni FIREBASE_CREDENTIALS_JSON. "
              "Descarga la clave privada (Configuración del proyecto → Cuentas de servicio) y guárdala en backend/.")
        return False
    credenciales = cargar_credenciales()
    if isinstance(credenciales, str):
        with open(credenciales, encoding="utf-8") as f:
            credenciales = json.load(f)
    proyecto_clave = credenciales.get("project_id", "")
    origen = "FIREBASE_CREDENTIALS_JSON" if settings.firebase_credentials_json else settings.firebase_credentials_path
    print(f"{OK} Clave de servicio encontrada en {origen} (proyecto '{proyecto_clave}').")
    if settings.firebase_project_id in ("", "tu-project-id"):
        print(f"{FALLA} FIREBASE_PROJECT_ID sin configurar en .env (debería ser '{proyecto_clave}').")
        bien = False
    elif settings.firebase_project_id != proyecto_clave:
        print(f"{FALLA} FIREBASE_PROJECT_ID='{settings.firebase_project_id}' no coincide con la "
              f"clave de servicio ('{proyecto_clave}').")
        bien = False
    if settings.jwt_secret.startswith("dev-") or settings.pin_pepper.startswith("dev-"):
        print(f"{AVISO} JWT_SECRET / PIN_PEPPER siguen con el valor de ejemplo.")
    return bien


def _revisar_servicios(settings) -> bool:
    from app.services.firebase_service import get_firebase_auth, get_firestore_client, get_realtime_ref

    bien = True
    try:
        list(get_firestore_client().collection("actividades").limit(1).stream())
        print(f"{OK} Firestore responde.")
    except Exception as exc:  # noqa: BLE001 - queremos mostrar cualquier error al usuario
        print(f"{FALLA} Firestore no responde: {exc}\n   ¿Creaste la base de datos en "
              "Compilación → Firestore Database?")
        bien = False

    try:
        get_firebase_auth().list_users(max_results=1)
        print(f"{OK} Firebase Authentication responde.")
    except Exception as exc:  # noqa: BLE001
        print(f"{FALLA} Authentication no responde: {exc}\n   ¿Activaste Compilación → Authentication?")
        bien = False

    if settings.realtime_db_url:
        try:
            get_realtime_ref("cola_recompensas").get(shallow=True)
            print(f"{OK} Realtime Database responde (cola del ESP32).")
        except Exception as exc:  # noqa: BLE001
            print(f"{FALLA} Realtime Database no responde: {exc}")
            bien = False
    else:
        print(f"{AVISO} FIREBASE_REALTIME_DB_URL vacío: la cola del ESP32 queda desactivada (opcional).")
    return bien


def _sembrar_actividades() -> None:
    from app.services.firebase_service import get_firestore_client
    from scripts.seed_actividades import ACTIVIDADES

    db = get_firestore_client()
    existentes = {doc.to_dict().get("nombre") for doc in db.collection("actividades").stream()}
    creadas = 0
    for actividad in ACTIVIDADES:
        if actividad["nombre"] in existentes:
            continue
        db.collection("actividades").document().set({
            "nombre": actividad["nombre"],
            "descripcion": "",
            "nivel": actividad["nivel"],
            "tipo": "vocabulario",
            "puntaje_maximo": 100,
            "pregunta": actividad["pregunta"],
            "opciones": actividad["opciones"],
            "respuesta_correcta": actividad["respuesta_correcta"],
            "icono": actividad["icono"],
            "activo": True,
        })
        creadas += 1
    print(f"{OK} {creadas} actividades nuevas creadas ({len(existentes)} ya existían).")


def _asignar_codigos_faltantes() -> None:
    """Estudiantes creados antes de existir `codigo_acceso` no podrían iniciar sesión."""
    from app.services.estudiantes_service import generar_codigo_acceso
    from app.services.firebase_service import get_firestore_client

    db = get_firestore_client()
    for doc in db.collection("usuarios").where("rol", "==", "estudiante").stream():
        if not doc.to_dict().get("codigo_acceso"):
            codigo = generar_codigo_acceso(db)
            doc.reference.update({"codigo_acceso": codigo})
            print(f"{OK} Código {codigo} asignado a {doc.to_dict().get('nombre')}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sembrar", action="store_true", help="Crea el catálogo inicial de actividades")
    args = parser.parse_args()

    settings = get_settings()
    if not _revisar_configuracion(settings) or not _revisar_servicios(settings):
        raise SystemExit("\nHay pasos pendientes: revisa los ❌ de arriba (firebase/README_FIREBASE.md).")
    _asignar_codigos_faltantes()
    if args.sembrar:
        _sembrar_actividades()
    print("\nFirebase configurado correctamente.")


if __name__ == "__main__":
    main()
