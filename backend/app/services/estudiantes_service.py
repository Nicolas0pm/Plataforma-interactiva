"""
Código de acceso de los estudiantes (RF01 CA3) y verificación de código + PIN.

El mismo par código + PIN sirve para dos cosas:
- que el niño inicie sesión (`POST /api/usuarios/login-pin`), y
- que un padre o docente demuestre que tiene acceso a la cuenta del niño para
  vincularse con él (`POST /api/vinculacion`, RF07/RF11).

Como el PIN es de solo 4 dígitos, cada código se bloquea unos minutos después de
varios intentos fallidos seguidos, para que nadie pueda probar los 10.000 PIN.
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.services.auth_service import hash_pin

# Sin 0/O, 1/I/L: caracteres que un niño (o un adulto dictándolos) no confunde.
_ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_LARGO_CODIGO = 6

MAX_FALLOS = 5
BLOQUEO_MINUTOS = 10


def normalizar_codigo(codigo: str) -> str:
    return codigo.strip().upper().replace(" ", "").replace("-", "")


def generar_codigo_acceso(db) -> str:
    """Código corto y único que el estudiante escribe en el login."""
    while True:
        codigo = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(_LARGO_CODIGO))
        if not list(db.collection("usuarios").where("codigo_acceso", "==", codigo).limit(1).stream()):
            return codigo


def _como_utc(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def verificar_codigo_y_pin(db, codigo: str, pin: str):
    """Devuelve el documento del estudiante si el código y el PIN son correctos.

    Lanza 429 si el código está bloqueado por demasiados intentos fallidos y 401
    si el código no existe o el PIN no coincide (mismo mensaje en ambos casos, para
    no revelar qué códigos existen).
    """
    codigo = normalizar_codigo(codigo)
    intentos_ref = db.collection("intentos_pin").document(codigo)
    intentos = intentos_ref.get().to_dict() or {}
    ahora = datetime.now(timezone.utc)

    bloqueado_hasta = intentos.get("bloqueado_hasta")
    if bloqueado_hasta and _como_utc(bloqueado_hasta) > ahora:
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos y vuelve a intentar.")

    docs = list(db.collection("usuarios").where("codigo_acceso", "==", codigo).limit(1).stream())
    doc = docs[0] if docs else None
    data = doc.to_dict() if doc else {}
    correcto = (
        data.get("rol") == "estudiante"
        and data.get("activo", True)
        and data.get("pin_hash") == hash_pin(pin)
    )

    if correcto:
        if intentos:
            intentos_ref.set({"fallos": 0, "bloqueado_hasta": None})
        return doc

    fallos = intentos.get("fallos", 0) + 1
    bloqueo = ahora + timedelta(minutes=BLOQUEO_MINUTOS) if fallos >= MAX_FALLOS else None
    intentos_ref.set({"fallos": 0 if bloqueo else fallos, "bloqueado_hasta": bloqueo})
    raise HTTPException(401, "Código o PIN incorrecto")
