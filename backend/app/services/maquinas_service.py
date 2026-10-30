"""
Máquinas de premios (ESP32): registro, asignación a un salón y configuración desde la página.

- **Registro.** La primera vez que la máquina tiene internet (el WiFi se le da una sola vez
  desde su propia red «Maquina-Premios», ver esp32/README.md) envía su dirección MAC y una
  clave que inventa ella misma. Su identificador es `MAQ-` + los 6 últimos dígitos de la MAC.
  Solo se guarda el hash de la clave.
- **Asignación.** El docente ve en su panel las máquinas registradas que no tienen salón y
  elige la suya. Desvincularla la deja libre otra vez.
- **Configuración remota.** El docente puede pedirle a su máquina otro WiFi; la máquina lo
  recibe en su próxima consulta (`wifi_pendiente`), prueba la red nueva y avisa el resultado.
- **Autenticación.** La máquina se identifica con `X-Device-Id` y `X-Device-Token`. Se sigue
  aceptando el secreto compartido `DEVICE_SHARED_SECRET` para una máquina configurada a mano.
- Una máquina está «en línea» si consultó la plataforma hace menos de `SEGUNDOS_EN_LINEA`.
"""
import hashlib
import hmac
import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import ahora
from app.models.tablas import HistorialRecompensa, Maquina, Usuario
from app.services.auth_service import registrar_auditoria

SEGUNDOS_EN_LINEA = 30
_MAC = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def en_linea(maquina: Maquina) -> bool:
    ultima = maquina.ultima_conexion
    return bool(ultima and ahora() - ultima < timedelta(seconds=SEGUNDOS_EN_LINEA))


def asignar_dispensador(db: Session, docente: Usuario, device_id: str | None) -> int:
    """La máquina del salón queda en el docente y en todos sus estudiantes. → nº de estudiantes."""
    docente.device_id_aula = device_id
    estudiantes = list(db.scalars(select(Usuario).where(Usuario.docente_id == docente.id_usuario,
                                                       Usuario.rol == "estudiante")))
    for estudiante in estudiantes:
        estudiante.device_id = device_id
    return len(estudiantes)


# ----------------------------------------------------------------- lado de la máquina


def registrar(db: Session, mac: str, clave: str) -> dict:
    """La máquina se presenta con su MAC. Si ya estaba registrada, la clave tiene que
    coincidir; si es otra (la máquina se reprogramó) solo se acepta mientras no tenga salón."""
    mac = mac.strip().upper().replace("-", ":")
    if not _MAC.match(mac) or len(clave) < 16:
        raise HTTPException(422, "MAC o clave no válidas")
    device_id = "MAQ-" + mac.replace(":", "")[-6:]
    maquina = db.scalar(select(Maquina).where(Maquina.mac == mac))
    if maquina is None:
        maquina = Maquina(device_id=device_id, mac=mac, token_hash=_hash(clave))
        db.add(maquina)
        registrar_auditoria(db, tipo="maquina_registrada", actor="esp32", detalle={"device_id": device_id})
    elif not hmac.compare_digest(maquina.token_hash, _hash(clave)):
        if maquina.id_docente:
            raise HTTPException(409, "Esta máquina ya está asignada a un salón con otra clave")
        maquina.token_hash = _hash(clave)
    maquina.ultima_conexion = ahora()
    return {"device_id": maquina.device_id}


def autenticar(db: Session, device_id: str, token: str | None, secreto: str | None) -> Maquina | None:
    """Comprueba que quien pregunta es la máquina `device_id`. Con su token devuelve la
    máquina; con el secreto compartido (configuración manual) devuelve None. Si no, 401."""
    if token:
        maquina = db.get(Maquina, device_id)
        if maquina and hmac.compare_digest(maquina.token_hash, _hash(token)):
            maquina.ultima_conexion = ahora()
            return maquina
        raise HTTPException(401, "Token de máquina inválido")
    compartido = get_settings().device_shared_secret
    if compartido and secreto and hmac.compare_digest(secreto, compartido):
        return None
    raise HTTPException(401, "Secreto de dispositivo inválido o no configurado")


def para_la_maquina(maquina: Maquina, red: str | None) -> dict:
    """Lo que la máquina necesita saber en cada consulta: si tiene salón y si hay WiFi nuevo."""
    if red:
        maquina.red_actual = red[:64]
    return {"device_id": maquina.device_id, "vinculada": maquina.id_docente is not None,
            "wifi": maquina.wifi_pendiente}


def resultado_wifi(db: Session, maquina: Maquina, ok: bool, red: str, detalle: str | None) -> None:
    maquina.wifi_pendiente = None
    if ok:
        maquina.red_actual = red[:64]
        maquina.wifi_estado = None
    else:
        maquina.wifi_estado = (detalle or f"No se pudo conectar a «{red}»")[:200]
    registrar_auditoria(db, tipo="maquina_wifi", actor="esp32",
                        detalle={"device_id": maquina.device_id, "ok": ok, "red": red})


# ----------------------------------------------------------------- lado del docente


def _de_docente(db: Session, docente: Usuario) -> Maquina | None:
    return db.scalar(select(Maquina).where(Maquina.id_docente == docente.id_usuario))


def _resumen(maquina: Maquina) -> dict:
    return {"device_id": maquina.device_id, "en_linea": en_linea(maquina), "ultima_conexion": maquina.ultima_conexion,
            "red_actual": maquina.red_actual}


def disponibles(db: Session) -> list[dict]:
    """Máquinas registradas que no tienen salón, primero las conectadas hace menos tiempo."""
    libres = db.scalars(select(Maquina).where(Maquina.id_docente.is_(None)))
    return sorted((_resumen(m) for m in libres), key=lambda m: (not m["en_linea"], m["device_id"]))


def vincular(db: Session, docente: Usuario, device_id: str) -> dict:
    maquina = db.get(Maquina, device_id.strip().upper())
    if maquina is None:
        raise HTTPException(404, "Esa máquina no se ha registrado: primero debe conectarse a internet")
    if maquina.id_docente and maquina.id_docente != docente.id_usuario:
        raise HTTPException(409, "Esa máquina ya está asignada a otro salón")
    anterior = _de_docente(db, docente)
    if anterior and anterior.device_id != maquina.device_id:
        anterior.id_docente = None
    maquina.id_docente = docente.id_usuario
    n = asignar_dispensador(db, docente, maquina.device_id)
    registrar_auditoria(db, tipo="maquina_vinculada", actor=docente.id_usuario,
                        detalle={"device_id": maquina.device_id, "estudiantes": n})
    return estado(db, docente)


def desvincular(db: Session, docente: Usuario) -> None:
    maquina = _de_docente(db, docente)
    if maquina:
        maquina.id_docente = None
        maquina.wifi_pendiente = None
    asignar_dispensador(db, docente, None)
    registrar_auditoria(db, tipo="maquina_desvinculada", actor=docente.id_usuario, detalle={})


def estado(db: Session, docente: Usuario) -> dict:
    maquina = _de_docente(db, docente)
    if maquina is None:
        return {"device_id": None, "vinculada": False, "en_linea": False}
    return _resumen(maquina) | {"vinculada": True, "wifi_pendiente": maquina.wifi_pendiente is not None
                                and {"ssid": maquina.wifi_pendiente["ssid"]}, "wifi_estado": maquina.wifi_estado}


def cambiar_wifi(db: Session, docente: Usuario, ssid: str, password: str) -> dict:
    maquina = _de_docente(db, docente)
    if maquina is None:
        raise HTTPException(400, "El salón no tiene una máquina vinculada")
    maquina.wifi_pendiente = {"ssid": ssid, "password": password}
    maquina.wifi_estado = None
    registrar_auditoria(db, tipo="maquina_wifi_pedido", actor=docente.id_usuario,
                        detalle={"device_id": maquina.device_id, "red": ssid})
    return estado(db, docente)


def probar(db: Session, docente: Usuario) -> dict:
    """Pone un premio de prueba en la cola de la máquina del salón."""
    maquina = _de_docente(db, docente)
    if maquina is None:
        raise HTTPException(400, "El salón no tiene una máquina vinculada")
    prueba = HistorialRecompensa(id_usuario=docente.id_usuario, tipo="prueba", estado="pendiente",
                                 device_id=maquina.device_id, emoji="🧪")
    db.add(prueba)
    db.flush()
    registrar_auditoria(db, tipo="maquina_prueba", actor=docente.id_usuario,
                        detalle={"device_id": maquina.device_id, "id_historial": prueba.id_historial})
    return {"id_historial": prueba.id_historial, "device_id": maquina.device_id}
