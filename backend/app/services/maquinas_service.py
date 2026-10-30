"""
Máquinas de premios (ESP32): vinculación desde el panel del docente y autenticación.

- El docente conecta la ESP32 por USB y pulsa «Conectar máquina». La API crea un `device_id`
  y un token propio de esa máquina; la página se los envía a la ESP32 por el cable (Web
  Serial) junto con el WiFi del salón, así la máquina sirve en cualquier red.
- La máquina se identifica con `X-Device-Token`. Solo se guarda el hash del token: si la
  base de datos se filtra, el token no sirve. Se sigue aceptando el secreto compartido
  `DEVICE_SHARED_SECRET` para las máquinas configuradas a mano.
- Una máquina está «en línea» si consultó su cola hace menos de `SEGUNDOS_EN_LINEA`.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import ahora
from app.models.tablas import HistorialRecompensa, Maquina, Usuario
from app.services.auth_service import registrar_auditoria

SEGUNDOS_EN_LINEA = 30


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def asignar_dispensador(db: Session, docente: Usuario, device_id: str | None) -> int:
    """La máquina del salón queda en el docente y en todos sus estudiantes. → nº de estudiantes."""
    docente.device_id_aula = device_id
    estudiantes = list(db.scalars(select(Usuario).where(Usuario.docente_id == docente.id_usuario,
                                                       Usuario.rol == "estudiante")))
    for estudiante in estudiantes:
        estudiante.device_id = device_id
    return len(estudiantes)


def vincular(db: Session, docente: Usuario) -> dict:
    """Crea una máquina nueva para el salón (reemplaza la anterior y anula su token)."""
    for vieja in db.scalars(select(Maquina).where(Maquina.id_docente == docente.id_usuario)):
        db.delete(vieja)
    device_id = f"maq-{secrets.token_hex(3)}"
    token = secrets.token_urlsafe(32)
    db.add(Maquina(device_id=device_id, id_docente=docente.id_usuario, token_hash=_hash(token)))
    n = asignar_dispensador(db, docente, device_id)
    registrar_auditoria(db, tipo="maquina_vinculada", actor=docente.id_usuario,
                        detalle={"device_id": device_id, "estudiantes": n})
    return {"device_id": device_id, "token": token}


def desvincular(db: Session, docente: Usuario) -> None:
    for maquina in db.scalars(select(Maquina).where(Maquina.id_docente == docente.id_usuario)):
        db.delete(maquina)
    asignar_dispensador(db, docente, None)
    registrar_auditoria(db, tipo="maquina_desvinculada", actor=docente.id_usuario, detalle={})


def estado(db: Session, docente: Usuario) -> dict:
    device_id = docente.device_id_aula
    maquina = db.get(Maquina, device_id) if device_id else None
    ultima = maquina.ultima_conexion if maquina else None
    en_linea = bool(ultima and ahora() - ultima < timedelta(seconds=SEGUNDOS_EN_LINEA))
    return {"device_id": device_id, "vinculada": maquina is not None, "ultima_conexion": ultima, "en_linea": en_linea}


def probar(db: Session, docente: Usuario) -> dict:
    """Pone un premio de prueba en la cola de la máquina del salón."""
    if not docente.device_id_aula:
        raise HTTPException(400, "El salón no tiene una máquina vinculada")
    prueba = HistorialRecompensa(id_usuario=docente.id_usuario, tipo="prueba", estado="pendiente",
                                 device_id=docente.device_id_aula, emoji="🧪")
    db.add(prueba)
    db.flush()
    registrar_auditoria(db, tipo="maquina_prueba", actor=docente.id_usuario,
                        detalle={"device_id": docente.device_id_aula, "id_historial": prueba.id_historial})
    return {"id_historial": prueba.id_historial, "device_id": docente.device_id_aula}


def autenticar(db: Session, device_id: str, token: str | None, secreto: str | None) -> Maquina | None:
    """Comprueba que quien pregunta es la máquina `device_id`. Con el token propio devuelve la
    máquina; con el secreto compartido (configuración manual) devuelve None. Si no, 401."""
    if token:
        maquina = db.get(Maquina, device_id)
        if maquina and hmac.compare_digest(maquina.token_hash, _hash(token)):
            return maquina
        raise HTTPException(401, "Token de máquina inválido")
    compartido = get_settings().device_shared_secret
    if compartido and secreto and hmac.compare_digest(secreto, compartido):
        return None
    raise HTTPException(401, "Secreto de dispositivo inválido o no configurado")
