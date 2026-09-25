"""
Inicializa Firebase Admin SDK una sola vez y expone los clientes de
Firestore y (opcionalmente) Realtime Database para el resto de la API.

Si `USE_FAKE_DB=true` (ver `app/config.py`), se usa en su lugar una base de
datos en memoria (`app/services/fake_firestore.py`) para poder desarrollar y
probar sin credenciales reales de Firebase. Nunca activar esto en producción.
"""
import firebase_admin
from firebase_admin import credentials, firestore, db

from app.config import get_settings
from app.services.fake_firestore import get_fake_firestore_client, get_fake_realtime_ref

_settings = get_settings()
_app = None


def init_firebase():
    global _app
    if _settings.use_fake_db:
        return None
    if _app is not None:
        return _app

    cred = credentials.Certificate(_settings.firebase_credentials_path)
    options = {"projectId": _settings.firebase_project_id}
    if _settings.realtime_db_url:
        options["databaseURL"] = _settings.realtime_db_url

    _app = firebase_admin.initialize_app(cred, options)
    return _app


def get_firestore_client():
    if _settings.use_fake_db:
        return get_fake_firestore_client()
    init_firebase()
    return firestore.client()


def get_realtime_ref(path: str):
    """Devuelve una referencia a un nodo de Realtime Database (usado por la cola
    de recompensas para el ESP32). Requiere FIREBASE_REALTIME_DB_URL en .env."""
    if _settings.use_fake_db:
        return get_fake_realtime_ref(path)
    init_firebase()
    return db.reference(path)


def get_firebase_auth():
    """Módulo `firebase_admin.auth`, para verificar ID tokens (ver auth_service.py).
    No aplica en modo fake: ahí la verificación de tokens Firebase se omite."""
    init_firebase()
    from firebase_admin import auth as firebase_auth

    return firebase_auth
