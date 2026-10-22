"""Exámenes cada N mundos (ver `services/examenes_service.py`).

- `GET /api/examenes`: los exámenes del estudiante (pendientes primero).
- `GET /api/examenes/{id}`: las preguntas, sin la respuesta correcta.
- `POST /api/examenes/{id}/resultado`: califica en el servidor; aprobar el de los mundos
  del profe por primera vez deja el premio en la cola de la máquina.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import RutaConTransaccion, get_db
from app.models.schemas import RespuestaLeccion
from app.services.auth_service import require_role
from app.services.catalogo_service import catalogo
from app.services.examenes_service import armar_examen, calificar_examen, examenes_de

router = APIRouter(prefix="/api/examenes", tags=["exámenes"], route_class=RutaConTransaccion)
estudiante = require_role("estudiante")


class ResultadoExamen(BaseModel):
    respuestas: list[RespuestaLeccion] = Field(min_length=1, max_length=50)


@router.get("")
def mis_examenes(usuario: dict = Depends(estudiante), db: Session = Depends(get_db)):
    return examenes_de(db, usuario["id_usuario"], catalogo(db, usuario["id_usuario"]))


@router.get("/{id_examen}")
def jugar_examen(id_examen: str, usuario: dict = Depends(estudiante), db: Session = Depends(get_db)):
    return armar_examen(db, id_examen, usuario["id_usuario"], catalogo(db, usuario["id_usuario"]))


@router.post("/{id_examen}/resultado")
def resultado_examen(id_examen: str, payload: ResultadoExamen, usuario: dict = Depends(estudiante),
                     db: Session = Depends(get_db)):
    return calificar_examen(db, id_examen, usuario["id_usuario"], [r.model_dump() for r in payload.respuestas],
                            catalogo(db, usuario["id_usuario"]))
