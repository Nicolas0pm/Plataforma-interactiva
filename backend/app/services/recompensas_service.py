"""
RF05: Sistema de recompensas físicas.

El premio real llega cuando el estudiante **completa un mundo** (`recompensa_por_mundo`):
se crea un registro en `historial_recompensas`. Si el estudiante tiene una máquina de
premios (ESP32) asignada, queda en estado "pendiente" con el `device_id` de la máquina:
esa es su cola. La máquina pregunta cada pocos segundos por sus premios pendientes
(`GET /api/recompensas/cola/{device_id}`), suelta un juguete por cada uno y confirma la
entrega (ver `routers/recompensas.py` y `esp32/README.md`). Sin máquina, el logro queda
registrado como "celebrada" (solo felicitación).

El docente elige cada cuántos mundos completados se entrega el premio físico (RF06,
`premio_cada_mundos`, de 1 a 5): los mundos intermedios también quedan como "celebrada" y
la respuesta le dice al niño cuántos le faltan para el próximo premio.

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


def recompensa_por_mundo(db: Session, id_usuario: str, info_unidad: dict, mundos_completados: int = 1) -> dict:
    """El estudiante completó un mundo (el número `mundos_completados` en total): premio
    físico si le toca según su docente y tiene máquina; felicitación si no."""
    usuario = db.get(Usuario, id_usuario)
    docente = db.get(Usuario, usuario.docente_id) if usuario and usuario.docente_id else None
    cada = max(1, (docente.premio_cada_mundos or 1) if docente else 1)
    toca = mundos_completados % cada == 0
    device_id = usuario.device_id if usuario and toca else None
    recompensa = HistorialRecompensa(
        id_usuario=id_usuario, tipo="mundo", unidad=info_unidad["id"],
        titulo_es=info_unidad["titulo"]["es"], titulo_en=info_unidad["titulo"]["en"], emoji=info_unidad["emoji"],
        fecha_entrega=ahora(), puntos_consumidos=0,
        estado="pendiente" if device_id else "celebrada", device_id=device_id,
    )
    db.add(recompensa)
    db.flush()
    registrar_auditoria(
        db, tipo="mundo_completado", actor=id_usuario,
        detalle={"id_historial": recompensa.id_historial, "unidad": info_unidad["id"], "con_maquina": bool(device_id),
                 "toca_premio": toca},
    )
    return {
        **recompensa.a_dict(),
        "toca_premio": toca,
        "hay_maquina": bool(usuario and usuario.device_id),
        "cada_mundos": cada,
        # Mundos que le faltan para el próximo premio (si hoy le tocó, empieza de nuevo).
        "faltan_mundos": cada - mundos_completados % cada,
    }
