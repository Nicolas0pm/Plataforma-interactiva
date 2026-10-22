"""
RF05: Sistema de recompensas físicas.

El premio real llega cuando el estudiante **aprueba el examen de los mundos del profe**
(`premio_por_examen`): se crea un registro en `historial_recompensas`. Si el estudiante
tiene una máquina de premios (ESP32) asignada, queda en estado "pendiente" con el
`device_id` de la máquina: esa es su cola. La máquina pregunta cada pocos segundos por sus premios pendientes
(`GET /api/recompensas/cola/{device_id}`), suelta un juguete por cada uno y confirma la
entrega (ver `routers/recompensas.py` y `esp32/README.md`). Sin máquina, el logro queda
registrado como "celebrada" (solo felicitación).

El docente elige cada cuántos mundos sale un examen (RF06, `premio_cada_mundos`, de 1 a 5;
ver `examenes_service.py`). El premio físico llega al aprobar el examen de los mundos del
profe; completar un mundo solo deja el logro ("celebrada").

Cada premio es una fila propia: si dos niños ganan casi al mismo tiempo, ninguno se pierde.

(`evaluar_recompensa`, por umbral de puntos, queda solo para el endpoint antiguo
`/api/actividades/completar`; los puntos ahora se gastan en la tienda del perfil.)
"""
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import ahora
from app.models.tablas import HistorialRecompensa, Usuario
from app.services.auth_service import registrar_auditoria

_settings = get_settings()


def evaluar_recompensa(db: Session, id_usuario: str, puntaje_total: int, puntaje_anterior: int | None = None) -> dict | None:
    """Genera una recompensa cada vez que el puntaje cruza un múltiplo del umbral.

    Con `puntaje_anterior` se detecta el cruce aunque el total no caiga justo en el
    múltiplo (las lecciones suman de a 10 puntos por acierto). Sin él, se mantiene el
    comportamiento original: solo al caer exactamente en un múltiplo.
    """
    umbral = _settings.reward_threshold
    if puntaje_total < umbral:
        return None
    if puntaje_anterior is not None:
        if puntaje_total // umbral <= puntaje_anterior // umbral:
            return None
    elif puntaje_total % umbral != 0:
        return None

    usuario = db.get(Usuario, id_usuario)
    device_id = usuario.device_id if usuario else None  # se asigna cuando exista hardware asociado

    recompensa = HistorialRecompensa(
        id_usuario=id_usuario, tipo="umbral", fecha_entrega=ahora(),
        puntos_consumidos=_settings.reward_threshold, estado="pendiente", device_id=device_id,
    )
    db.add(recompensa)
    db.flush()  # asigna el id_historial
    registrar_auditoria(
        db, tipo="recompensa_generada", actor=id_usuario,
        detalle={"id_historial": recompensa.id_historial, "puntos_consumidos": _settings.reward_threshold},
    )
    return recompensa.a_dict()


def logro_de_mundo(db: Session, id_usuario: str, info_unidad: dict) -> dict:
    """El estudiante completó un mundo: queda el logro (lo ve en "Mundos completados"). El
    premio físico ya no es por mundo: llega al aprobar el examen de los mundos del profe
    (`premio_por_examen`)."""
    logro = HistorialRecompensa(
        id_usuario=id_usuario, tipo="mundo", unidad=info_unidad["id"],
        titulo_es=info_unidad["titulo"]["es"], titulo_en=info_unidad["titulo"]["en"], emoji=info_unidad["emoji"],
        fecha_entrega=ahora(), puntos_consumidos=0, estado="celebrada", device_id=None,
    )
    db.add(logro)
    db.flush()
    registrar_auditoria(db, tipo="mundo_completado", actor=id_usuario,
                        detalle={"id_historial": logro.id_historial, "unidad": info_unidad["id"]})
    return logro.a_dict()


def premio_por_examen(db: Session, id_usuario: str, id_examen: str, mundos: list[dict]) -> dict:
    """Aprobó (por primera vez) el examen de N mundos del profe: premio físico si tiene
    máquina asignada (queda "pendiente" en su cola); si no, solo la felicitación."""
    usuario = db.get(Usuario, id_usuario)
    device_id = usuario.device_id if usuario else None
    nombres_es = ", ".join(m["titulo"]["es"] for m in mundos)
    nombres_en = ", ".join(m["titulo"]["en"] for m in mundos)
    premio = HistorialRecompensa(
        id_usuario=id_usuario, tipo="examen", unidad=f"examen-{id_examen}"[:80],
        titulo_es=f"Examen: {nombres_es}"[:80], titulo_en=f"Exam: {nombres_en}"[:80], emoji="📝",
        fecha_entrega=ahora(), puntos_consumidos=0,
        estado="pendiente" if device_id else "celebrada", device_id=device_id,
    )
    db.add(premio)
    db.flush()
    registrar_auditoria(db, tipo="premio_examen", actor=id_usuario,
                        detalle={"id_historial": premio.id_historial, "id_examen": id_examen,
                                 "con_maquina": bool(device_id)})
    return premio.a_dict()
