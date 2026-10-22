"""
Catálogo de lo que puede aprender un estudiante, en tres apartados:

- **vocabulario** y **gramatica**: el temario fijo de `app/curriculo.py`, menos los mundos
  que el coordinador apagó para toda la institución (`temario_global`, RF08) y los que el
  docente apagó en su salón, en el orden que él eligió (`temario_salon`, RF07). El docente
  también puede cambiar o esconder preguntas de esos mundos solo para su salón
  (`preguntas_salon`, ver `aplicar_cambios_salon`).
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
from app.models.tablas import Actividad, MundoDocente, PreguntaSalon, TemaGlobal, TemaSalon, Usuario

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


_INFO_FIJA = {u: info_unidad(u) for unidades in ORDEN_POR_SECCION.values() for u in unidades}


def apagados_globales(db: Session) -> set[str]:
    return set(db.scalars(select(TemaGlobal.unidad).where(TemaGlobal.activo.is_(False))))


def temario_salon(db: Session, id_docente: str | None, apagados: set[str] | None = None) -> dict:
    """{seccion: [{id, activo, global_activo}]} con TODOS los mundos del temario fijo, en el
    orden del salón. Lo usan el catálogo del niño y la vista «Temario» del docente."""
    if apagados is None:
        apagados = apagados_globales(db)
    filas = {}
    if id_docente:
        filas = {t.unidad: t for t in db.scalars(select(TemaSalon).where(TemaSalon.id_docente == id_docente))}
    salida = {}
    for seccion, unidades in ORDEN_POR_SECCION.items():
        posicion = {u: i for i, u in enumerate(unidades)}
        ordenadas = sorted(unidades, key=lambda u: (filas[u].orden if u in filas else posicion[u], posicion[u]))
        salida[seccion] = [
            {"id": u, "activo": filas[u].activo if u in filas else True, "global_activo": u not in apagados}
            for u in ordenadas
        ]
    return salida


def catalogo_de_docente(db: Session, id_docente: str | None, mundos_profe: list[dict] | None = None) -> dict:
    """{seccion: [info de cada unidad en orden]} para los niños de un salón (o sin docente)."""
    temario = temario_salon(db, id_docente)
    cat = {
        seccion: [_INFO_FIJA[t["id"]] for t in temas if t["activo"] and t["global_activo"]]
        for seccion, temas in temario.items()
    }
    cat[SECCION_PROFESOR] = mundos_de_docente(db, id_docente) if mundos_profe is None else mundos_profe
    return cat


def catalogo(db: Session, id_estudiante: str) -> dict:
    """El catálogo de un estudiante concreto: el de su salón."""
    docente_id = db.scalar(select(Usuario.docente_id).where(Usuario.id_usuario == id_estudiante))
    return catalogo_de_docente(db, docente_id)


def buscar_unidad(cat: dict, unidad: str) -> dict | None:
    return next((u for unidades in cat.values() for u in unidades if u["id"] == unidad), None)


def lecciones_de(cat: dict, seccion: str | None = None) -> list[tuple[str, int]]:
    """Lecciones de un apartado (o de todos), en el orden en que se desbloquean."""
    secciones = [seccion] if seccion else list(cat)
    return [(u["id"], n) for sec in secciones for u in cat[sec] for n in range(1, u["lecciones"] + 1)]


def aplicar_cambios_salon(db: Session, id_docente: str | None, preguntas: list[dict]) -> list[dict]:
    """Aplica a las preguntas del temario fijo los cambios que hizo el docente en su salón:
    otro enunciado u otras opciones, o la pregunta oculta. Las del profe no se tocan."""
    if not id_docente:
        return preguntas
    fijas = [p["id_actividad"] for p in preguntas if not es_del_profesor(p.get("unidad") or "")]
    if not fijas:
        return preguntas
    cambios = {
        c.id_actividad: c for c in db.scalars(
            select(PreguntaSalon).where(PreguntaSalon.id_docente == id_docente, PreguntaSalon.id_actividad.in_(fijas))
        )
    }
    salida = []
    for p in preguntas:
        cambio = cambios.get(p["id_actividad"])
        if cambio is None:
            salida.append(p)
        elif cambio.activo:
            salida.append({**p, "pregunta": cambio.pregunta, "opciones": list(cambio.opciones),
                           "respuesta_correcta": cambio.respuesta_correcta, "editada": True})
    return salida


def preguntas_de_leccion(db: Session, unidad: str, leccion: int, id_docente: str | None = None) -> list[dict]:
    """Preguntas de una lección tal como las ve el salón de `id_docente`."""
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
    return aplicar_cambios_salon(db, id_docente, [a.a_dict() for a in db.scalars(consulta)])
