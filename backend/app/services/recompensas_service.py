"""
RF05: Sistema de recompensas físicas.

El premio real llega cuando el estudiante **completa un mundo** (`recompensa_por_mundo`):
se crea un registro en `historial_recompensas` (Firestore, fuente de verdad) y, si el
estudiante tiene una máquina de premios (ESP32) asignada, se encola un pedido en Realtime
Database `cola_recompensas/{device_id}/{id_historial}` para que la máquina suelte un
juguete. Sin máquina, el logro queda registrado como "celebrada" (solo felicitación).

Cada pedido es un nodo propio dentro de la cola del dispositivo: si dos niños ganan casi
al mismo tiempo, ninguno sobrescribe al otro. La máquina borra el nodo al confirmar la
entrega (ver `routers/recompensas.py` y `esp32/README.md`).

(`evaluar_recompensa`, por umbral de puntos, queda solo para el endpoint antiguo
`/api/actividades/completar`; los puntos ahora se gastan en la tienda del perfil.)
"""
from datetime import datetime, timezone

from app.config import get_settings
from app.services.auth_service import registrar_auditoria
from app.services.firebase_service import get_firestore_client, get_realtime_ref

_settings = get_settings()


def evaluar_recompensa(id_usuario: str, puntaje_total: int, puntaje_anterior: int | None = None) -> dict | None:
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

    db = get_firestore_client()
    usuario = db.collection("usuarios").document(id_usuario).get().to_dict() or {}
    device_id = usuario.get("device_id")  # se asigna cuando exista hardware asociado

    recompensa_ref = db.collection("historial_recompensas").document()
    recompensa = {
        "id_usuario": id_usuario,
        "fecha_entrega": datetime.now(timezone.utc),
        "puntos_consumidos": _settings.reward_threshold,
        "estado": "pendiente",
        "device_id": device_id,
    }
    recompensa_ref.set(recompensa)
    registrar_auditoria(
        db, tipo="recompensa_generada", actor=id_usuario,
        detalle={"id_historial": recompensa_ref.id, "puntos_consumidos": _settings.reward_threshold},
    )

    _encolar_para_maquina(device_id, id_usuario, recompensa_ref.id)
    return {**recompensa, "id_historial": recompensa_ref.id}


def _encolar_para_maquina(device_id: str | None, id_usuario: str, id_historial: str) -> None:
    if not (device_id and _settings.realtime_db_url):
        return
    get_realtime_ref(f"cola_recompensas/{device_id}/{id_historial}").set(
        {
            "id_usuario": id_usuario,
            "id_historial_recompensa": id_historial,
            "comando": "dispensar",
            "estado": "pendiente",
            "timestamp": datetime.now(timezone.utc).timestamp(),
        }
    )


def recompensa_por_mundo(db, id_usuario: str, info_unidad: dict) -> dict:
    """El estudiante completó un mundo: premio físico si tiene máquina, felicitación si no."""
    usuario = db.collection("usuarios").document(id_usuario).get().to_dict() or {}
    device_id = usuario.get("device_id")
    recompensa = {
        "id_usuario": id_usuario,
        "tipo": "mundo",
        "unidad": info_unidad["id"],
        "titulo": info_unidad["titulo"],
        "emoji": info_unidad["emoji"],
        "fecha_entrega": datetime.now(timezone.utc),
        "puntos_consumidos": 0,
        "estado": "pendiente" if device_id else "celebrada",
        "device_id": device_id,
    }
    ref = db.collection("historial_recompensas").document()
    ref.set(recompensa)
    registrar_auditoria(
        db, tipo="mundo_completado", actor=id_usuario,
        detalle={"id_historial": ref.id, "unidad": info_unidad["id"], "con_maquina": bool(device_id)},
    )
    _encolar_para_maquina(device_id, id_usuario, ref.id)
    return {**recompensa, "id_historial": ref.id}
