from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import get_settings
from app.services.auth_service import current_user, registrar_auditoria, verificar_acceso_estudiante
from app.services.firebase_service import get_firestore_client

router = APIRouter(prefix="/api/recompensas", tags=["recompensas"])
_settings = get_settings()


@router.get("/estudiante/{id_usuario}")
def recompensas_de_estudiante(id_usuario: str, usuario: dict = Depends(current_user)):
    """RF05/RF07: recompensas obtenidas, consultables por el estudiante, su
    docente, sus padres vinculados o un admin."""
    db = get_firestore_client()
    verificar_acceso_estudiante(usuario, id_usuario, db)
    query = db.collection("historial_recompensas").where("id_usuario", "==", id_usuario)
    return [{**doc.to_dict(), "id_historial": doc.id} for doc in query.stream()]


@router.post("/{id_historial}/confirmar-entrega")
def confirmar_entrega(id_historial: str, x_device_secret: str | None = Header(default=None)):
    """El ESP32 confirma que la recompensa física fue entregada. No usa un token
    de usuario (el dispensador no tiene cuenta): se autentica con un secreto
    compartido configurado en `DEVICE_SHARED_SECRET` (ver esp32/README.md)."""
    if not _settings.device_shared_secret or x_device_secret != _settings.device_shared_secret:
        raise HTTPException(401, "Secreto de dispositivo inválido o no configurado")

    db = get_firestore_client()
    ref = db.collection("historial_recompensas").document(id_historial)
    if not ref.get().exists:
        raise HTTPException(404, "Recompensa no encontrada")
    ref.update({"estado": "entregada"})
    registrar_auditoria(db, tipo="recompensa_entregada", actor="esp32", detalle={"id_historial": id_historial})
    return {"ok": True}
