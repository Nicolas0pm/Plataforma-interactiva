"""
Envío de correos (por ahora, solo el código para confirmar el correo de un adulto).

Se elige el proveedor según las variables de entorno (ver `.env.example`):

- **Brevo** (`BREVO_API_KEY`): API HTTP, plan gratis de 300 correos/día. Es la opción
  recomendada en Render, porque el plan gratis de Render bloquea los puertos SMTP.
- **SMTP** (`SMTP_HOST`, `SMTP_USUARIO`, `SMTP_CLAVE`): cualquier servidor SMTP, por
  ejemplo Gmail con una "contraseña de aplicación".
- **Ninguno**: el correo no se envía; se escribe en el log del servidor. Sirve para
  desarrollar en local (con `USE_FAKE_DB=true` el código aparece en la consola). En
  producción además cuenta como error, para que la persona vea que el correo no salió.
"""
import json
import logging
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from app.config import get_settings

log = logging.getLogger("uvicorn.error")
_settings = get_settings()


class CorreoNoEnviado(Exception):
    pass


def proveedor() -> str:
    if _settings.brevo_api_key:
        return "brevo"
    if _settings.smtp_host:
        return "smtp"
    return "log"


def enviar_correo(destino: str, asunto: str, texto: str, html: str) -> None:
    """Envía el correo o lanza `CorreoNoEnviado`."""
    try:
        match proveedor():
            case "brevo":
                _enviar_brevo(destino, asunto, texto, html)
            case "smtp":
                _enviar_smtp(destino, asunto, texto, html)
            case _:
                log.warning("Sin proveedor de correo configurado. Correo para %s — %s:\n%s", destino, asunto, texto)
                if not _settings.use_fake_db:
                    raise CorreoNoEnviado("No hay proveedor de correo configurado (BREVO_API_KEY o SMTP_HOST)")
    except CorreoNoEnviado as exc:
        log.error("No se pudo enviar el correo a %s: %s", destino, exc)
        raise
    except Exception as exc:  # red, credenciales, remitente no verificado...
        log.exception("No se pudo enviar el correo a %s", destino)
        raise CorreoNoEnviado(str(exc)) from exc


def _enviar_brevo(destino: str, asunto: str, texto: str, html: str) -> None:
    cuerpo = {
        "sender": {"name": _settings.email_remitente_nombre, "email": _settings.email_remitente},
        "to": [{"email": destino}],
        "subject": asunto,
        "textContent": texto,
        "htmlContent": html,
    }
    peticion = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(cuerpo).encode(),
        headers={"api-key": _settings.brevo_api_key, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=15) as respuesta:
            if respuesta.status >= 300:
                raise CorreoNoEnviado(f"Brevo respondió {respuesta.status}")
    except urllib.error.HTTPError as exc:
        # Brevo explica el motivo en el cuerpo (API key inválida, remitente no verificado...).
        raise CorreoNoEnviado(f"Brevo respondió {exc.code}: {exc.read().decode(errors='replace')[:300]}") from exc


def _enviar_smtp(destino: str, asunto: str, texto: str, html: str) -> None:
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = f"{_settings.email_remitente_nombre} <{_settings.email_remitente or _settings.smtp_usuario}>"
    mensaje["To"] = destino
    mensaje.set_content(texto)
    mensaje.add_alternative(html, subtype="html")
    if _settings.smtp_port == 465:
        servidor = smtplib.SMTP_SSL(_settings.smtp_host, 465, timeout=15)
    else:
        servidor = smtplib.SMTP(_settings.smtp_host, _settings.smtp_port, timeout=15)
        servidor.starttls()
    with servidor:
        if _settings.smtp_usuario:
            servidor.login(_settings.smtp_usuario, _settings.smtp_clave)
        servidor.send_message(mensaje)
