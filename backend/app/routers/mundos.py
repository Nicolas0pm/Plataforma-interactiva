"""
Mundos que crea el docente (apartado "Del profe" del niño).

Solo preguntas de **selección múltiple** (2 a 4 opciones, una correcta): no hay preguntas
abiertas. Cada pregunta puede llevar un emoji y/o una imagen: el navegador del docente la
achica antes de subirla y se guarda como data URL dentro de la misma actividad.
Las lecciones se arman solas en grupos de 8 preguntas (ver `catalogo_service`).
Borrar un mundo o una pregunta los desactiva (no se pierde el historial de los niños).
"""
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.db import RutaConTransaccion, get_db
from app.models.tablas import Actividad, MundoDocente
from app.services.auth_service import registrar_auditoria, require_role
from app.services.catalogo_service import (
    PREFIJO_PROFESOR,
    SECCION_PROFESOR,
    contar_preguntas,
    mundos_activos,
    preguntas_activas,
)

router = APIRouter(prefix="/api/mundos", tags=["mundos del docente"], route_class=RutaConTransaccion)

# Imagen ya achicada en el navegador (~480 px). El límite evita que unas pocas fotos
# llenen la base de datos (ver docs/data-model.md).
MAX_IMAGEN = 300_000
IMAGEN_VALIDA = re.compile(r"^data:image/(jpeg|png|webp|gif);base64,[A-Za-z0-9+/]+=*$")


class MundoCrear(BaseModel):
    titulo: str = Field(min_length=1, max_length=40)
    emoji: str = Field(default="🌟", min_length=1, max_length=8)
    descripcion: str = Field(default="", max_length=140)

    @field_validator("titulo", "descripcion", "emoji")
    @classmethod
    def sin_espacios_sobrantes(cls, valor: str) -> str:
        return valor.strip()


class PreguntaCrear(BaseModel):
    pregunta: str = Field(min_length=1, max_length=200)
    opciones: list[str] = Field(min_length=2, max_length=4)
    respuesta_correcta: str
    icono: Optional[str] = Field(default=None, max_length=8)
    imagen: Optional[str] = Field(default=None, max_length=MAX_IMAGEN)

    @model_validator(mode="after")
    def validar_opciones(self):
        self.pregunta = self.pregunta.strip()
        self.opciones = [o.strip() for o in self.opciones]
        self.respuesta_correcta = self.respuesta_correcta.strip()
        self.icono = (self.icono or "").strip() or None
        self.imagen = self.imagen or None
        if self.imagen and not IMAGEN_VALIDA.match(self.imagen):
            raise ValueError("La imagen debe ser JPG, PNG, WEBP o GIF")
        if any(not o or len(o) > 60 for o in self.opciones):
            raise ValueError("Cada opción debe tener entre 1 y 60 caracteres")
        if len({o.lower() for o in self.opciones}) != len(self.opciones):
            raise ValueError("Las opciones no se pueden repetir")
        if self.respuesta_correcta not in self.opciones:
            raise ValueError("La respuesta correcta tiene que ser una de las opciones")
        return self


def _mundo_propio(db: Session, id_mundo: str, usuario: dict) -> MundoDocente:
    mundo = db.get(MundoDocente, id_mundo)
    if mundo is None or not mundo.activo:
        raise HTTPException(404, "No existe ese mundo")
    if usuario["rol"] != "admin" and mundo.id_docente != usuario["id_usuario"]:
        raise HTTPException(403, "Ese mundo es de otro docente")
    return mundo


def _salida_mundo(mundo: MundoDocente, n: int) -> dict:
    return {
        "id_mundo": mundo.id_mundo,
        "titulo": mundo.titulo,
        "emoji": mundo.emoji,
        "descripcion": mundo.descripcion or "",
        "preguntas": n,
        "lecciones": -(-n // 8),
        "creado_en": mundo.creado_en,
    }


def _salida_pregunta(actividad: Actividad) -> dict:
    return {"id_actividad": actividad.id_actividad,
            **{k: getattr(actividad, k) for k in ("pregunta", "opciones", "respuesta_correcta", "icono", "imagen")}}


@router.get("")
def mis_mundos(usuario: dict = Depends(require_role("docente", "admin")), db: Session = Depends(get_db)):
    mundos = mundos_activos(db, usuario["id_usuario"])
    conteo = contar_preguntas(db, [m.id_mundo for m in mundos])
    return [_salida_mundo(m, conteo.get(m.id_mundo, 0)) for m in mundos]


@router.post("", status_code=201)
def crear_mundo(payload: MundoCrear, usuario: dict = Depends(require_role("docente", "admin")), db: Session = Depends(get_db)):
    mundo = MundoDocente(**payload.model_dump(), id_docente=usuario["id_usuario"], activo=True,
                         creado_en=datetime.now(timezone.utc))
    db.add(mundo)
    db.flush()
    registrar_auditoria(db, tipo="mundo_creado", actor=usuario["id_usuario"], detalle={"id_mundo": mundo.id_mundo})
    return _salida_mundo(mundo, 0)


@router.delete("/{id_mundo}")
def borrar_mundo(id_mundo: str, usuario: dict = Depends(require_role("docente", "admin")), db: Session = Depends(get_db)):
    _mundo_propio(db, id_mundo, usuario).activo = False
    registrar_auditoria(db, tipo="mundo_desactivado", actor=usuario["id_usuario"], detalle={"id_mundo": id_mundo})
    return {"ok": True}


@router.get("/{id_mundo}/preguntas")
def preguntas_del_mundo(id_mundo: str, usuario: dict = Depends(require_role("docente", "admin")), db: Session = Depends(get_db)):
    _mundo_propio(db, id_mundo, usuario)
    return [
        {k: p.get(k) for k in ("id_actividad", "pregunta", "opciones", "respuesta_correcta", "icono", "imagen")}
        for p in preguntas_activas(db, PREFIJO_PROFESOR + id_mundo)
    ]


@router.post("/{id_mundo}/preguntas", status_code=201)
def agregar_pregunta(
    id_mundo: str, payload: PreguntaCrear, usuario: dict = Depends(require_role("docente", "admin")),
    db: Session = Depends(get_db),
):
    mundo = _mundo_propio(db, id_mundo, usuario)
    ahora = datetime.now(timezone.utc)
    actividad = Actividad(
        nombre=f"{mundo.titulo} · {payload.pregunta[:30]}",
        descripcion="",
        seccion=SECCION_PROFESOR,
        unidad=PREFIJO_PROFESOR + id_mundo,
        leccion=None,  # las lecciones se arman solas en grupos de 8
        orden=int(ahora.timestamp() * 1000),
        nivel=1,
        tipo="profesor",
        puntaje_maximo=10,
        pregunta=payload.pregunta,
        opciones=payload.opciones,
        respuesta_correcta=payload.respuesta_correcta,
        icono=payload.icono,
        imagen=payload.imagen,
        formato_opciones="texto",
        id_docente=usuario["id_usuario"],
        id_mundo=id_mundo,
        activo=True,
        creado_en=ahora,
    )
    db.add(actividad)
    db.flush()
    return _salida_pregunta(actividad)


@router.delete("/{id_mundo}/preguntas/{id_actividad}")
def borrar_pregunta(
    id_mundo: str, id_actividad: str, usuario: dict = Depends(require_role("docente", "admin")),
    db: Session = Depends(get_db),
):
    _mundo_propio(db, id_mundo, usuario)
    actividad = db.get(Actividad, id_actividad)
    if actividad is None or actividad.id_mundo != id_mundo:
        raise HTTPException(404, "Esa pregunta no es de este mundo")
    actividad.activo = False
    return {"ok": True}
