from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import RutaConTransaccion, get_db
from app.models.schemas import FeedbackCreate, FeedbackOut
from app.models.tablas import Feedback
from app.services.auth_service import current_user, registrar_auditoria, require_role, verificar_acceso_estudiante

router = APIRouter(prefix="/api/feedback", tags=["feedback"], route_class=RutaConTransaccion)


@router.post("", response_model=FeedbackOut, status_code=201)
def crear_feedback(payload: FeedbackCreate, usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    """Feedback del docente sobre el progreso de un estudiante, visible para padres."""
    verificar_acceso_estudiante(usuario, payload.id_estudiante, db)

    feedback = Feedback(**payload.model_dump(), id_docente=usuario["id_usuario"])
    db.add(feedback)
    db.flush()
    registrar_auditoria(db, tipo="feedback_creado", actor=usuario["id_usuario"], detalle={"id_feedback": feedback.id_feedback})
    return feedback.a_dict()


@router.get("/estudiante/{id_estudiante}", response_model=list[FeedbackOut])
def feedback_de_estudiante(id_estudiante: str, usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    verificar_acceso_estudiante(usuario, id_estudiante, db)

    consulta = select(Feedback).where(Feedback.id_estudiante == id_estudiante)
    if usuario["rol"] == "padre":
        consulta = consulta.where(Feedback.visible_para_padres)
    return [f.a_dict() for f in db.scalars(consulta.order_by(Feedback.fecha.desc()))]
