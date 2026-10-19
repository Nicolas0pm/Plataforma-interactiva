from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import RutaConTransaccion, get_db
from app.models.tablas import HistorialRecompensa
from app.services.auth_service import current_user, registrar_auditoria, verificar_acceso_estudiante

router = APIRouter(prefix="/api/recompensas", tags=["recompensas"], route_class=RutaConTransaccion)
_settings = get_settings()


def _exigir_secreto_dispositivo(x_device_secret: str | None = Header(default=None)) -> None:
    """La máquina de premios (ESP32) no tiene cuenta de usuario: se autentica con el
    secreto compartido `DEVICE_SHARED_SECRET` (ver esp32/README.md)."""
    if not _settings.device_shared_secret or x_device_secret != _settings.device_shared_secret:
        raise HTTPException(401, "Secreto de dispositivo inválido o no configurado")


@router.get("/estudiante/{id_usuario}")
def recompensas_de_estudiante(id_usuario: str, usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    """RF05/RF07: recompensas obtenidas, consultables por el estudiante, su
    docente, sus padres vinculados o un admin."""
    verificar_acceso_estudiante(usuario, id_usuario, db)
    consulta = (
        select(HistorialRecompensa).where(HistorialRecompensa.id_usuario == id_usuario)
        .order_by(HistorialRecompensa.fecha_entrega)
    )
    return [r.a_dict() for r in db.scalars(consulta)]


@router.get("/cola/{device_id}", dependencies=[Depends(_exigir_secreto_dispositivo)])
def cola_de_la_maquina(device_id: str, db: Session = Depends(get_db)):
    """Premios que la máquina `device_id` todavía tiene que soltar, del más antiguo al más
    nuevo. El ESP32 la consulta cada pocos segundos; cada premio sale de la cola cuando la
    máquina confirma su entrega."""
    consulta = (
        select(HistorialRecompensa)
        .where(HistorialRecompensa.device_id == device_id, HistorialRecompensa.estado == "pendiente")
        .order_by(HistorialRecompensa.fecha_entrega)
    )
    return [
        {"id_historial": r.id_historial, "id_usuario": r.id_usuario, "comando": "dispensar",
         "fecha": r.fecha_entrega, "emoji": r.emoji}
        for r in db.scalars(consulta)
    ]


@router.post("/{id_historial}/confirmar-entrega", dependencies=[Depends(_exigir_secreto_dispositivo)])
def confirmar_entrega(id_historial: str, db: Session = Depends(get_db)):
    """El ESP32 confirma que soltó el juguete: el premio sale de su cola y ya no se vuelve
    a entregar aunque la máquina se reinicie."""
    recompensa = db.get(HistorialRecompensa, id_historial)
    if recompensa is None:
        raise HTTPException(404, "Recompensa no encontrada")
    recompensa.estado = "entregada"
    registrar_auditoria(db, tipo="recompensa_entregada", actor="esp32", detalle={"id_historial": id_historial})
    return {"ok": True}
