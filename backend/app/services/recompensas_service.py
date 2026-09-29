"""
RF05: Sistema de recompensas físicas.

Cuando un estudiante cruza un umbral de puntos, se crea un registro en
`historial_recompensas` (Firestore, fuente de verdad) y, si hay un dispositivo ESP32
asociado, se escribe un comando en Realtime Database `cola_recompensas/{device_id}`
para que el hardware lo recoja. Esto último es opcional hoy (fase futura) y se activa
solo si FIREBASE_REALTIME_DB_URL está configurado.
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

    if device_id and _settings.realtime_db_url:
        get_realtime_ref(f"cola_recompensas/{device_id}").set(
            {
                "id_usuario": id_usuario,
                "id_historial_recompensa": recompensa_ref.id,
                "comando": "dispensar",
                "estado": "pendiente",
                "timestamp": datetime.now(timezone.utc).timestamp(),
            }
        )

    return {**recompensa, "id_historial": recompensa_ref.id}
