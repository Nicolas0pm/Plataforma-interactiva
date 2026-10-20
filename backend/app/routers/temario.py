"""
RF07: el docente decide qué mundos del temario fijo ve su salón y en qué orden.

`GET /api/temario/salon` devuelve todos los mundos de vocabulario y gramática en el orden
del salón, con `activo` (lo decide el docente) y `global_activo` (lo decide el coordinador,
RF08: un mundo apagado por el coordinador no lo ve ningún salón). `PUT
/api/temario/salon/{seccion}` guarda el orden y los activos de un apartado completo. El
progreso de los niños no se borra: si un mundo se vuelve a activar, siguen donde iban.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.curriculo import ORDEN_POR_SECCION, info_unidad
from app.db import RutaConTransaccion, get_db
from app.models.tablas import TemaSalon
from app.services.auth_service import registrar_auditoria, require_role
from app.services.catalogo_service import temario_salon

router = APIRouter(prefix="/api/temario", tags=["temario"], route_class=RutaConTransaccion)


class TemaElegido(BaseModel):
    id: str = Field(max_length=40)
    activo: bool


class TemarioSeccion(BaseModel):
    unidades: list[TemaElegido]


def con_info(temario: dict) -> dict:
    """Agrega título, emoji y número de lecciones a cada mundo del temario."""
    salida = {}
    for seccion, temas in temario.items():
        salida[seccion] = []
        for t in temas:
            info = info_unidad(t["id"])
            salida[seccion].append({**t, "titulo": info["titulo"], "emoji": info["emoji"], "lecciones": info["lecciones"]})
    return salida


@router.get("/salon")
def ver_temario(usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    return con_info(temario_salon(db, usuario["id_usuario"]))


@router.put("/salon/{seccion}")
def guardar_temario(
    seccion: str, payload: TemarioSeccion, usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)
):
    unidades = ORDEN_POR_SECCION.get(seccion)
    if unidades is None:
        raise HTTPException(404, "No existe ese apartado")
    ids = [t.id for t in payload.unidades]
    if sorted(ids) != sorted(unidades):
        raise HTTPException(400, "Envía todos los mundos del apartado, cada uno una vez")
    if not any(t.activo for t in payload.unidades):
        raise HTTPException(400, "Deja al menos un mundo activo en cada apartado")
    id_docente = usuario["id_usuario"]
    db.execute(delete(TemaSalon).where(TemaSalon.id_docente == id_docente, TemaSalon.unidad.in_(unidades)))
    db.add_all(
        TemaSalon(id_docente=id_docente, unidad=t.id, activo=t.activo, orden=i) for i, t in enumerate(payload.unidades)
    )
    db.flush()
    registrar_auditoria(db, tipo="temario_salon", actor=id_docente,
                        detalle={"seccion": seccion, "activos": [t.id for t in payload.unidades if t.activo]})
    return con_info(temario_salon(db, id_docente))
