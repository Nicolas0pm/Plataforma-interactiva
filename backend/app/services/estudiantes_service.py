"""
Código de acceso de los estudiantes (RF01 CA3) y verificación de código + PIN.

El mismo par código + PIN sirve para dos cosas:
- que el niño inicie sesión (`POST /api/usuarios/login-pin`), y
- que un padre o docente demuestre que tiene acceso a la cuenta del niño para
  vincularse con él (`POST /api/vinculacion`, RF07/RF11).

Como el PIN es de solo 4 dígitos, cada código se bloquea unos minutos después de
varios intentos fallidos seguidos (`auth_service.anotar_intento`), para que nadie pueda
probar los 10.000 PIN.
"""
import secrets
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tablas import Usuario
from app.services.auth_service import anotar_intento, hash_pin, revisar_bloqueo

# Sin 0/O, 1/I/L: caracteres que un niño (o un adulto dictándolos) no confunde.
_ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_LARGO_CODIGO = 6


def normalizar_codigo(codigo: str) -> str:
    return codigo.strip().upper().replace(" ", "").replace("-", "")


def generar_codigo_acceso(db: Session) -> str:
    """Código corto y único que el estudiante escribe en el login."""
    while True:
        codigo = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(_LARGO_CODIGO))
        if db.scalar(select(Usuario.id_usuario).where(Usuario.codigo_acceso == codigo)) is None:
            return codigo


def verificar_codigo_y_pin(db: Session, codigo: str, pin: str) -> Usuario:
    """Devuelve el estudiante si el código y el PIN son correctos.

    Lanza 429 si el código está bloqueado por demasiados intentos fallidos y 401
    si el código no existe o el PIN no coincide (mismo mensaje en ambos casos, para
    no revelar qué códigos existen).
    """
    codigo = normalizar_codigo(codigo)
    clave = f"pin:{codigo}"
    revisar_bloqueo(db, clave)

    estudiante = db.scalar(select(Usuario).where(Usuario.codigo_acceso == codigo))
    correcto = (
        estudiante is not None
        and estudiante.rol == "estudiante"
        and estudiante.activo
        and estudiante.pin_hash == hash_pin(pin)
    )

    anotar_intento(db, clave, correcto)
    if not correcto:
        raise HTTPException(401, "Código o PIN incorrecto")
    return estudiante
