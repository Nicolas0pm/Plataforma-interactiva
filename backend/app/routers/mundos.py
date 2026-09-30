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

from app.services.auth_service import registrar_auditoria, require_role
from app.services.catalogo_service import PREFIJO_PROFESOR, SECCION_PROFESOR, preguntas_activas
from app.services.firebase_service import get_firestore_client

router = APIRouter(prefix="/api/mundos", tags=["mundos del docente"])

# Imagen ya achicada en el navegador (~480 px). El límite deja espacio de sobra dentro del
# máximo de 1 MB por documento de Firestore.
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


def _mundo_propio(db, id_mundo: str, usuario: dict):
    ref = db.collection("mundos_docente").document(id_mundo)
    doc = ref.get()
    if not doc.exists or not doc.to_dict().get("activo", True):
        raise HTTPException(404, "No existe ese mundo")
    if usuario["rol"] != "admin" and doc.to_dict().get("id_docente") != usuario["id_usuario"]:
        raise HTTPException(403, "Ese mundo es de otro docente")
    return ref, doc.to_dict()


def _contar(db, id_mundo: str) -> int:
    """Recalcula y guarda cuántas preguntas activas tiene el mundo (lo lee el catálogo)."""
    n = len(preguntas_activas(db, PREFIJO_PROFESOR + id_mundo))
    db.collection("mundos_docente").document(id_mundo).update({"n_preguntas": n})
    return n


def _salida_mundo(db, id_mundo: str, datos: dict) -> dict:
    n = datos.get("n_preguntas", 0)
    return {
        "id_mundo": id_mundo,
        "titulo": datos.get("titulo"),
        "emoji": datos.get("emoji"),
        "descripcion": datos.get("descripcion", ""),
        "preguntas": n,
        "lecciones": -(-n // 8),
        "creado_en": datos.get("creado_en"),
    }


@router.get("")
def mis_mundos(usuario: dict = Depends(require_role("docente", "admin"))):
    db = get_firestore_client()
    docs = [
        d for d in db.collection("mundos_docente").where("id_docente", "==", usuario["id_usuario"]).stream()
        if d.to_dict().get("activo", True)
    ]
    docs.sort(key=lambda d: d.to_dict().get("creado_en"))
    return [_salida_mundo(db, d.id, d.to_dict()) for d in docs]


@router.post("", status_code=201)
def crear_mundo(payload: MundoCrear, usuario: dict = Depends(require_role("docente", "admin"))):
    db = get_firestore_client()
    ref = db.collection("mundos_docente").document()
    datos = {**payload.model_dump(), "id_docente": usuario["id_usuario"], "activo": True,
             "creado_en": datetime.now(timezone.utc), "n_preguntas": 0}
    ref.set(datos)
    registrar_auditoria(db, tipo="mundo_creado", actor=usuario["id_usuario"], detalle={"id_mundo": ref.id})
    return _salida_mundo(db, ref.id, datos)


@router.delete("/{id_mundo}")
def borrar_mundo(id_mundo: str, usuario: dict = Depends(require_role("docente", "admin"))):
    db = get_firestore_client()
    ref, _ = _mundo_propio(db, id_mundo, usuario)
    ref.update({"activo": False})
    registrar_auditoria(db, tipo="mundo_desactivado", actor=usuario["id_usuario"], detalle={"id_mundo": id_mundo})
    return {"ok": True}


@router.get("/{id_mundo}/preguntas")
def preguntas_del_mundo(id_mundo: str, usuario: dict = Depends(require_role("docente", "admin"))):
    db = get_firestore_client()
    _mundo_propio(db, id_mundo, usuario)
    return [
        {k: p.get(k) for k in ("id_actividad", "pregunta", "opciones", "respuesta_correcta", "icono", "imagen")}
        for p in preguntas_activas(db, PREFIJO_PROFESOR + id_mundo)
    ]


@router.post("/{id_mundo}/preguntas", status_code=201)
def agregar_pregunta(id_mundo: str, payload: PreguntaCrear, usuario: dict = Depends(require_role("docente", "admin"))):
    db = get_firestore_client()
    _, mundo = _mundo_propio(db, id_mundo, usuario)
    ahora = datetime.now(timezone.utc)
    ref = db.collection("actividades").document()
    datos = {
        "nombre": f"{mundo.get('titulo')} · {payload.pregunta[:30]}",
        "descripcion": "",
        "seccion": SECCION_PROFESOR,
        "unidad": PREFIJO_PROFESOR + id_mundo,
        "leccion": None,  # las lecciones se arman solas en grupos de 8
        "orden": int(ahora.timestamp() * 1000),
        "nivel": 1,
        "tipo": "profesor",
        "puntaje_maximo": 10,
        "pregunta": payload.pregunta,
        "opciones": payload.opciones,
        "respuesta_correcta": payload.respuesta_correcta,
        "icono": payload.icono,
        "imagen": payload.imagen,
        "formato_opciones": "texto",
        "id_docente": usuario["id_usuario"],
        "activo": True,
        "creado_en": ahora,
    }
    ref.set(datos)
    _contar(db, id_mundo)
    return {"id_actividad": ref.id, **{k: datos[k] for k in ("pregunta", "opciones", "respuesta_correcta", "icono", "imagen")}}


@router.delete("/{id_mundo}/preguntas/{id_actividad}")
def borrar_pregunta(id_mundo: str, id_actividad: str, usuario: dict = Depends(require_role("docente", "admin"))):
    db = get_firestore_client()
    _mundo_propio(db, id_mundo, usuario)
    ref = db.collection("actividades").document(id_actividad)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("unidad") != PREFIJO_PROFESOR + id_mundo:
        raise HTTPException(404, "Esa pregunta no es de este mundo")
    ref.update({"activo": False})
    _contar(db, id_mundo)
    return {"ok": True}
