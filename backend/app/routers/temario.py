"""
RF07: el docente decide qué mundos del temario fijo ve su salón y en qué orden, y puede
cambiar u ocultar preguntas de esos mundos solo para su salón (tabla `preguntas_salon`).

`GET /api/temario/salon` devuelve todos los mundos de vocabulario y gramática en el orden
del salón, con `activo` (lo decide el docente) y `global_activo` (lo decide el coordinador,
RF08: un mundo apagado por el coordinador no lo ve ningún salón). `PUT
/api/temario/salon/{seccion}` guarda el orden y los activos de un apartado completo. El
progreso de los niños no se borra: si un mundo se vuelve a activar, siguen donde iban.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.curriculo import ORDEN_POR_SECCION, ORDEN_UNIDADES, info_unidad
from app.db import RutaConTransaccion, get_db
from app.models.tablas import Actividad, PreguntaSalon, TemaSalon
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


# ---------------------------------------------------------------------------------------
# Preguntas del temario fijo, cambiadas solo para el salón del docente

MIN_PREGUNTAS_VISIBLES = 4


class PreguntaEditada(BaseModel):
    pregunta: str = Field(min_length=1, max_length=200)
    opciones: list[str] = Field(min_length=2, max_length=4)
    respuesta_correcta: str

    @model_validator(mode="after")
    def validar(self):
        self.pregunta = self.pregunta.strip()
        self.opciones = [o.strip() for o in self.opciones]
        self.respuesta_correcta = self.respuesta_correcta.strip()
        if any(not o or len(o) > 60 for o in self.opciones):
            raise ValueError("Cada opción debe tener entre 1 y 60 caracteres")
        if len({o.lower() for o in self.opciones}) != len(self.opciones):
            raise ValueError("Las opciones no se pueden repetir")
        if self.respuesta_correcta not in self.opciones:
            raise ValueError("La respuesta correcta tiene que ser una de las opciones")
        return self


class PreguntaVisible(BaseModel):
    activo: bool


def _pregunta_del_temario(db: Session, id_actividad: str) -> Actividad:
    actividad = db.get(Actividad, id_actividad)
    if actividad is None or not actividad.activo or actividad.unidad not in ORDEN_UNIDADES:
        raise HTTPException(404, "No existe esa pregunta en el temario")
    return actividad


def _cambio(db: Session, id_docente: str, actividad: Actividad) -> PreguntaSalon:
    cambio = db.get(PreguntaSalon, (id_docente, actividad.id_actividad))
    if cambio is None:
        cambio = PreguntaSalon(id_docente=id_docente, id_actividad=actividad.id_actividad,
                               pregunta=actividad.pregunta, opciones=list(actividad.opciones),
                               respuesta_correcta=actividad.respuesta_correcta, activo=True)
        db.add(cambio)
    return cambio


@router.get("/salon/{unidad}/preguntas")
def preguntas_de_mundo(unidad: str, usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    """Todas las preguntas de un mundo del temario, por lección, como las ve el salón."""
    if unidad not in ORDEN_UNIDADES:
        raise HTTPException(404, "No existe ese mundo en el temario")
    originales = list(db.scalars(
        select(Actividad).where(Actividad.unidad == unidad, Actividad.activo).order_by(Actividad.leccion, Actividad.orden)
    ))
    cambios = {c.id_actividad: c for c in db.scalars(
        select(PreguntaSalon).where(PreguntaSalon.id_docente == usuario["id_usuario"],
                                    PreguntaSalon.id_actividad.in_([a.id_actividad for a in originales]))
    )}
    lecciones: dict[int, list] = {}
    for a in originales:
        c = cambios.get(a.id_actividad)
        lecciones.setdefault(a.leccion, []).append({
            "id_actividad": a.id_actividad,
            "pregunta": c.pregunta if c else a.pregunta,
            "opciones": list(c.opciones) if c else list(a.opciones),
            "respuesta_correcta": c.respuesta_correcta if c else a.respuesta_correcta,
            "icono": a.icono,
            "formato_opciones": a.formato_opciones,
            "editada": bool(c) and (c.pregunta, list(c.opciones), c.respuesta_correcta)
            != (a.pregunta, list(a.opciones), a.respuesta_correcta),
            "visible": c.activo if c else True,
        })
    info = info_unidad(unidad)
    return {"id": unidad, "titulo": info["titulo"], "emoji": info["emoji"],
            "lecciones": [{"numero": n, "preguntas": p} for n, p in sorted(lecciones.items())]}


@router.put("/salon/preguntas/{id_actividad}")
def editar_pregunta(id_actividad: str, payload: PreguntaEditada, usuario: dict = Depends(require_role("docente")),
                    db: Session = Depends(get_db)):
    actividad = _pregunta_del_temario(db, id_actividad)
    cambio = _cambio(db, usuario["id_usuario"], actividad)
    cambio.pregunta, cambio.opciones, cambio.respuesta_correcta = payload.pregunta, payload.opciones, payload.respuesta_correcta
    cambio.actualizado_en = datetime.now(timezone.utc)
    registrar_auditoria(db, tipo="pregunta_salon_editada", actor=usuario["id_usuario"], detalle={"id_actividad": id_actividad})
    return {"ok": True}


@router.patch("/salon/preguntas/{id_actividad}")
def mostrar_u_ocultar(id_actividad: str, payload: PreguntaVisible, usuario: dict = Depends(require_role("docente")),
                      db: Session = Depends(get_db)):
    actividad = _pregunta_del_temario(db, id_actividad)
    if not payload.activo:
        de_la_leccion = [a.id_actividad for a in db.scalars(
            select(Actividad).where(Actividad.unidad == actividad.unidad, Actividad.leccion == actividad.leccion,
                                    Actividad.activo)
        )]
        ocultas = set(db.scalars(select(PreguntaSalon.id_actividad).where(
            PreguntaSalon.id_docente == usuario["id_usuario"], PreguntaSalon.id_actividad.in_(de_la_leccion),
            PreguntaSalon.activo.is_(False),
        ))) | {id_actividad}
        if len(de_la_leccion) - len(ocultas) < MIN_PREGUNTAS_VISIBLES:
            raise HTTPException(400, f"Cada lección debe conservar al menos {MIN_PREGUNTAS_VISIBLES} preguntas")
    cambio = _cambio(db, usuario["id_usuario"], actividad)
    cambio.activo = payload.activo
    cambio.actualizado_en = datetime.now(timezone.utc)
    registrar_auditoria(db, tipo="pregunta_salon_visible" if payload.activo else "pregunta_salon_oculta",
                        actor=usuario["id_usuario"], detalle={"id_actividad": id_actividad})
    return {"ok": True}


@router.delete("/salon/preguntas/{id_actividad}")
def restaurar_pregunta(id_actividad: str, usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    """Vuelve a la pregunta original del temario (visible y sin cambios)."""
    _pregunta_del_temario(db, id_actividad)
    cambio = db.get(PreguntaSalon, (usuario["id_usuario"], id_actividad))
    if cambio is not None:
        db.delete(cambio)
        registrar_auditoria(db, tipo="pregunta_salon_restaurada", actor=usuario["id_usuario"],
                            detalle={"id_actividad": id_actividad})
    return {"ok": True}
