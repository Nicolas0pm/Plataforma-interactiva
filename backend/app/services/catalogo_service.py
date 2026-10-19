"""
Catálogo de lo que puede aprender un estudiante, en tres apartados:

- **vocabulario** y **gramatica**: el temario fijo de `app/curriculo.py`.
- **profesor**: los mundos que crea el docente del estudiante (tabla `mundos_docente`),
  con preguntas de selección múltiple que el docente agrega. Sus lecciones se arman solas
  en grupos de `PREGUNTAS_POR_LECCION` preguntas, en el orden en que se crearon.

Los mundos del docente usan el id de unidad "prof-<id del mundo>" para no chocar con el
temario fijo.
"""
import math

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.curriculo import ORDEN_POR_SECCION, PREGUNTAS_POR_LECCION, info_unidad
from app.models.tablas import Actividad, MundoDocente, Usuario

SECCION_PROFESOR = "profesor"
SECCIONES_TODAS = [*ORDEN_POR_SECCION, SECCION_PROFESOR]
PREFIJO_PROFESOR = "prof-"


def es_del_profesor(unidad: str) -> bool:
    return unidad.startswith(PREFIJO_PROFESOR)


def _orden_preguntas():
    return Actividad.leccion.nulls_first(), Actividad.orden.nulls_first(), Actividad.id_actividad


def preguntas_activas(db: Session, unidad: str) -> list[dict]:
    """Preguntas activas de una unidad, en orden."""
    consulta = select(Actividad).where(Actividad.unidad == unidad, Actividad.activo).order_by(*_orden_preguntas())
    return [a.a_dict() for a in db.scalars(consulta)]


def contar_preguntas(db: Session, ids_mundos: list[str]) -> dict[str, int]:
    """Cuántas preguntas activas tiene cada mundo, en una sola consulta."""
    if not ids_mundos:
        return {}
    consulta = (
        select(Actividad.id_mundo, func.count())
        .where(Actividad.id_mundo.in_(ids_mundos), Actividad.activo)
        .group_by(Actividad.id_mundo)
    )
    return dict(db.execute(consulta).all())


def info_mundo_docente(mundo: MundoDocente, n_preguntas: int) -> dict:
    return {
        "id": PREFIJO_PROFESOR + mundo.id_mundo,
        "seccion": SECCION_PROFESOR,
        "titulo": {"es": mundo.titulo, "en": mundo.titulo},
        "emoji": mundo.emoji or "🌟",
        "descripcion": mundo.descripcion or "",
        "lecciones": math.ceil(n_preguntas / PREGUNTAS_POR_LECCION),
        "explicacion": None,
    }


def mundos_activos(db: Session, id_docente: str) -> list[MundoDocente]:
    consulta = (
        select(MundoDocente)
        .where(MundoDocente.id_docente == id_docente, MundoDocente.activo)
        .order_by(MundoDocente.creado_en)
    )
    return list(db.scalars(consulta))


def mundos_de_docente(db: Session, id_docente: str | None) -> list[dict]:
    """Mundos activos de un docente que ya tienen al menos una pregunta, en orden de creación."""
    if not id_docente:
        return []
    mundos = mundos_activos(db, id_docente)
    conteo = contar_preguntas(db, [m.id_mundo for m in mundos])
    return [info_mundo_docente(m, conteo[m.id_mundo]) for m in mundos if conteo.get(m.id_mundo)]


_CATALOGO_FIJO = {sec: [info_unidad(u) for u in unidades] for sec, unidades in ORDEN_POR_SECCION.items()}


def catalogo(db: Session, id_estudiante: str, mundos_profe: list[dict] | None = None) -> dict:
    """{seccion: [info de cada unidad en orden]} para un estudiante concreto. El temario fijo
    se arma una sola vez al arrancar; solo los mundos del profe se consultan (o se reciben ya
    consultados, cuando se arma el panel de todo un salón)."""
    if mundos_profe is None:
        docente_id = db.scalar(select(Usuario.docente_id).where(Usuario.id_usuario == id_estudiante))
        mundos_profe = mundos_de_docente(db, docente_id)
    return {**_CATALOGO_FIJO, SECCION_PROFESOR: mundos_profe}


def buscar_unidad(cat: dict, unidad: str) -> dict | None:
    return next((u for unidades in cat.values() for u in unidades if u["id"] == unidad), None)


def lecciones_de(cat: dict, seccion: str | None = None) -> list[tuple[str, int]]:
    """Lecciones de un apartado (o de todos), en el orden en que se desbloquean."""
    secciones = [seccion] if seccion else list(cat)
    return [(u["id"], n) for sec in secciones for u in cat[sec] for n in range(1, u["lecciones"] + 1)]


def preguntas_de_leccion(db: Session, unidad: str, leccion: int) -> list[dict]:
    if es_del_profesor(unidad):
        consulta = (
            select(Actividad).where(Actividad.unidad == unidad, Actividad.activo).order_by(*_orden_preguntas())
            .offset((leccion - 1) * PREGUNTAS_POR_LECCION).limit(PREGUNTAS_POR_LECCION)
        )
    else:
        consulta = (
            select(Actividad).where(Actividad.unidad == unidad, Actividad.leccion == leccion, Actividad.activo)
            .order_by(*_orden_preguntas())
        )
    return [a.a_dict() for a in db.scalars(consulta)]
