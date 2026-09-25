from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.models.schemas import FeedbackCreate, FeedbackOut
from app.services.auth_service import current_user, registrar_auditoria, require_role, verificar_acceso_estudiante
from app.services.firebase_service import get_firestore_client

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=201)
def crear_feedback(payload: FeedbackCreate, usuario: dict = Depends(require_role("docente"))):
    """Feedback del docente sobre el progreso de un estudiante, visible para padres."""
    db = get_firestore_client()
    verificar_acceso_estudiante(usuario, payload.id_estudiante, db)

    data = payload.model_dump()
    data["id_docente"] = usuario["id_usuario"]
    data["fecha"] = datetime.now(timezone.utc)
    ref = db.collection("feedback").document()
    ref.set(data)
    registrar_auditoria(db, tipo="feedback_creado", actor=usuario["id_usuario"], detalle={"id_feedback": ref.id})
    return {**data, "id_feedback": ref.id}


@router.get("/estudiante/{id_estudiante}", response_model=list[FeedbackOut])
def feedback_de_estudiante(id_estudiante: str, usuario: dict = Depends(current_user)):
    db = get_firestore_client()
    verificar_acceso_estudiante(usuario, id_estudiante, db)

    query = (
        db.collection("feedback")
        .where("id_estudiante", "==", id_estudiante)
        .order_by("fecha", direction="DESCENDING")
    )
    resultados = [{**doc.to_dict(), "id_feedback": doc.id} for doc in query.stream()]
    if usuario["rol"] == "padre":
        resultados = [f for f in resultados if f.get("visible_para_padres", True)]
    return resultados
