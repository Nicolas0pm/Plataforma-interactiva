"""
Autenticación y autorización de la API.

Hay dos tipos de token, ambos enviados como `Authorization: Bearer <token>`:

1. **Token propio (JWT HS256)**: lo emite esta misma API para el acceso
   simplificado por PIN de los estudiantes (RF01 CA3) y, solo cuando
   `USE_FAKE_DB=true`, para un login de desarrollo sin Firebase real.
   Expira a los `JWT_PIN_EXP_MINUTOS` minutos (RNF-SEG-04).
2. **ID token de Firebase Authentication (RS256)**: lo obtiene el frontend con
   el SDK web tras `signInWithEmailAndPassword` (docentes/padres/admin). Se
   valida contra Firebase y se resuelve a un usuario de la colección
   `usuarios` por su campo `auth_uid`.

`current_user()` intenta decodificar primero como token propio (rápido, sin
red) y si no es válido intenta verificarlo como ID token de Firebase. Además
exige que un adulto haya confirmado su correo (ver `verificacion_service.py`);
`usuario_autenticado()` es lo mismo sin esa exigencia.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException

from app.config import get_settings
from app.services.firebase_service import get_firebase_auth, get_firestore_client

_settings = get_settings()


def hash_pin(pin: str) -> str:
    return hashlib.sha256((_settings.pin_pepper + pin).encode()).hexdigest()


def crear_token_sesion(id_usuario: str, rol: str) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": id_usuario,
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=_settings.jwt_pin_exp_minutos),
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm="HS256")


def crear_token_dev(id_usuario: str, rol: str) -> str:
    """Login de desarrollo para docentes/padres/admin SIN Firebase Auth real.
    Solo funciona con USE_FAKE_DB=true; en cualquier otro caso está deshabilitado."""
    if not _settings.use_fake_db:
        raise HTTPException(403, "El login de desarrollo solo está disponible con USE_FAKE_DB=true")
    return crear_token_sesion(id_usuario, rol)


def extraer_token_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Falta el encabezado Authorization: Bearer <token>")
    return authorization.split(" ", 1)[1].strip()


# alias interno usado en este mismo módulo
_extraer_token = extraer_token_bearer


def verificar_id_token_firebase_crudo(authorization: str | None) -> dict:
    """Verifica un ID token de Firebase Auth SIN buscar el perfil en `usuarios`.

    Se usa únicamente en el registro (`POST /api/usuarios`) de docentes/padres/admin,
    donde el perfil todavía no existe: solo necesitamos confirmar que quien llama ya
    creó una cuenta válida en Firebase Authentication y obtener su `uid`/`email`.
    """
    token = extraer_token_bearer(authorization)
    try:
        decoded = get_firebase_auth().verify_id_token(token)
    except Exception as exc:
        raise HTTPException(401, "Token de Firebase inválido o expirado") from exc
    return {"auth_uid": decoded.get("uid"), "email": decoded.get("email")}


def _decodificar_token_propio(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, _settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    usuario = {"id_usuario": payload["sub"], "rol": payload["rol"], "email_verificado": True}
    if payload["rol"] != "estudiante":
        # Adultos con token propio: solo el login de desarrollo (USE_FAKE_DB=true).
        datos = get_firestore_client().collection("usuarios").document(payload["sub"]).get().to_dict() or {}
        usuario["email_verificado"] = datos.get("email_verificado", True)
    return usuario


def _decodificar_token_firebase(token: str) -> dict | None:
    if _settings.use_fake_db:
        return None  # en modo fake no hay Firebase Auth real que verificar
    try:
        decoded = get_firebase_auth().verify_id_token(token)
    except Exception:
        return None

    auth_uid = decoded.get("uid")
    db = get_firestore_client()
    docs = list(db.collection("usuarios").where("auth_uid", "==", auth_uid).limit(1).stream())
    if not docs:
        return None
    data = docs[0].to_dict()
    return {"id_usuario": docs[0].id, "rol": data.get("rol"), "email_verificado": data.get("email_verificado", True)}


def usuario_autenticado(authorization: str | None = Header(default=None)) -> dict:
    """Quién llama, aunque todavía no haya confirmado su correo. Solo para la sesión y
    los endpoints de verificación; todo lo demás usa `current_user()`."""
    token = _extraer_token(authorization)
    usuario = _decodificar_token_propio(token) or _decodificar_token_firebase(token)
    if usuario is None:
        raise HTTPException(401, "Token inválido o expirado")
    return usuario


def current_user(authorization: str | None = Header(default=None)) -> dict:
    usuario = usuario_autenticado(authorization)
    if not usuario["email_verificado"]:
        raise HTTPException(403, "Primero confirma tu correo con el código que te enviamos")
    return usuario


def require_role(*roles: str):
    """Dependencia de FastAPI: exige que el usuario autenticado tenga uno de `roles`."""

    def _verificar(usuario: dict = Depends(current_user)) -> dict:
        if usuario["rol"] not in roles:
            raise HTTPException(403, "No tienes permiso para realizar esta acción")
        return usuario

    return _verificar


def verificar_acceso_estudiante(usuario: dict, id_estudiante: str, db) -> None:
    """Lanza 403/404 si `usuario` no tiene derecho a ver u operar sobre los datos
    de `id_estudiante`: debe ser admin, el propio estudiante, su docente asignado
    o uno de sus padres/acudientes vinculados (RF11)."""
    if usuario["rol"] == "admin":
        return
    if usuario["rol"] == "estudiante":
        if usuario["id_usuario"] == id_estudiante:
            return
        raise HTTPException(403, "Un estudiante solo puede ver su propia información")

    doc = db.collection("usuarios").document(id_estudiante).get()
    if not doc.exists:
        raise HTTPException(404, "Estudiante no encontrado")
    data = doc.to_dict()

    if usuario["rol"] == "docente" and data.get("docente_id") == usuario["id_usuario"]:
        return
    if usuario["rol"] == "padre" and usuario["id_usuario"] in data.get("acudientes_ids", []):
        return
    raise HTTPException(403, "No tienes ningún vínculo con este estudiante")


def registrar_auditoria(db, tipo: str, actor: str | None, detalle: dict | None = None) -> None:
    """RNF-AUD-*: registro de auditoría de solo-inserción (ver firebase/firestore.rules)."""
    db.collection("auditoria").document().set(
        {
            "tipo": tipo,
            "actor": actor,
            "detalle": detalle or {},
            "fecha": datetime.now(timezone.utc),
        }
    )
