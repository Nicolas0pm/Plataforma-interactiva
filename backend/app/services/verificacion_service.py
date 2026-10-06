"""
Confirmación del correo de docentes y padres con un código de 6 dígitos.

1. Al registrarse, el perfil queda con `email_verificado: False` y se envía un código.
2. Mientras no lo confirme, `current_user()` le responde 403 en toda la API, salvo
   `GET /sesion` y los endpoints de verificación (ver `usuario_autenticado()`).
3. El código se guarda como hash (nunca en texto plano), vence a los
   `MINUTOS_VIGENCIA` minutos y admite `MAX_INTENTOS` intentos. Pedir otro código
   exige esperar `ESPERA_REENVIO` segundos.

Los perfiles creados antes de existir esto no tienen el campo y cuentan como verificados.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import HTTPException

from app.config import get_settings
from app.services.correo_service import CorreoNoEnviado, enviar_correo

MINUTOS_VIGENCIA = 15
MAX_INTENTOS = 5
ESPERA_REENVIO = 60  # segundos

_settings = get_settings()


def _hash(id_usuario: str, codigo: str) -> str:
    return hashlib.sha256(f"{_settings.pin_pepper}:{id_usuario}:{codigo}".encode()).hexdigest()


def _como_utc(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def enviar_codigo(db, id_usuario: str, datos: dict, forzar: bool = False) -> None:
    """Genera un código nuevo, lo guarda y lo envía. Lanza 429 si se pide muy seguido
    y 502 si el correo no sale (el código anterior deja de servir igual)."""
    ahora = datetime.now(timezone.utc)
    anterior = datos.get("verificacion_email") or {}
    if not forzar and anterior.get("enviado_en"):
        espera = ESPERA_REENVIO - (ahora - _como_utc(anterior["enviado_en"])).total_seconds()
        if espera > 0:
            raise HTTPException(429, f"Espera {int(espera) + 1} segundos para pedir otro código")

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    db.collection("usuarios").document(id_usuario).update({
        "verificacion_email": {
            "hash": _hash(id_usuario, codigo),
            "expira": ahora + timedelta(minutes=MINUTOS_VIGENCIA),
            "intentos": 0,
            "enviado_en": ahora,
        }
    })
    try:
        _enviar(datos["email"], datos.get("nombre") or "", codigo)
    except CorreoNoEnviado as exc:
        raise HTTPException(502, "No pudimos enviar el correo. Intenta de nuevo en un momento.") from exc


def confirmar_codigo(db, id_usuario: str, codigo: str) -> None:
    ref = db.collection("usuarios").document(id_usuario)
    datos = ref.get().to_dict() or {}
    if datos.get("email_verificado", True):
        return
    pendiente = datos.get("verificacion_email")
    if not pendiente:
        raise HTTPException(400, "Pide un código nuevo")
    if datetime.now(timezone.utc) > _como_utc(pendiente["expira"]):
        raise HTTPException(400, "El código venció. Pide uno nuevo.")
    if pendiente["intentos"] >= MAX_INTENTOS:
        raise HTTPException(400, "Demasiados intentos. Pide un código nuevo.")
    if not hmac.compare_digest(pendiente["hash"], _hash(id_usuario, codigo.strip())):
        pendiente["intentos"] += 1
        ref.update({"verificacion_email": pendiente})
        quedan = MAX_INTENTOS - pendiente["intentos"]
        raise HTTPException(400, f"Código incorrecto. Te quedan {quedan} intentos." if quedan else
                            "Código incorrecto. Pide un código nuevo.")
    ref.update({"email_verificado": True, "verificacion_email": None,
                "email_verificado_en": datetime.now(timezone.utc)})


def _enviar(destino: str, nombre: str, codigo: str) -> None:
    saludo = f"Hola, {nombre}:" if nombre else "Hola:"
    texto = (
        f"{saludo}\n\nTu código para confirmar tu correo en ¡Aprendamos inglés! es:\n\n"
        f"    {codigo}\n\nVence en {MINUTOS_VIGENCIA} minutos. Si no creaste una cuenta, ignora este correo."
    )
    html = f"""\
<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;color:#223345">
  <h2 style="color:#3aa9d6">¡Aprendamos inglés! 🦊</h2>
  <p>{escape(saludo)}</p>
  <p>Tu código para confirmar tu correo es:</p>
  <p style="font-size:32px;font-weight:bold;letter-spacing:8px;background:#eef4fa;
            border-radius:12px;padding:16px;text-align:center">{codigo}</p>
  <p style="color:#6b7c8f">Vence en {MINUTOS_VIGENCIA} minutos. Si no creaste una cuenta, ignora este correo.</p>
</div>"""
    enviar_correo(destino, f"{codigo} es tu código de confirmación", texto, html)
