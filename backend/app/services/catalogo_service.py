"""
Catálogo de lo que puede aprender un estudiante, en tres apartados:

- **vocabulario** y **gramatica**: el temario fijo de `app/curriculo.py`.
- **profesor**: los mundos que crea el docente del estudiante (colección `mundos_docente`),
  con preguntas de selección múltiple que el docente agrega. Sus lecciones se arman solas
  en grupos de `PREGUNTAS_POR_LECCION` preguntas, en el orden en que se crearon.

Los mundos del docente usan el id de unidad "prof-<id del mundo>" para no chocar con el
temario fijo.
"""
import math

from app.curriculo import ORDEN_POR_SECCION, PREGUNTAS_POR_LECCION, info_unidad

SECCION_PROFESOR = "profesor"
SECCIONES_TODAS = [*ORDEN_POR_SECCION, SECCION_PROFESOR]
PREFIJO_PROFESOR = "prof-"


def es_del_profesor(unidad: str) -> bool:
    return unidad.startswith(PREFIJO_PROFESOR)


def preguntas_activas(db, unidad: str) -> list[dict]:
    """Preguntas activas de una unidad, en orden. (Dos filtros de igualdad: no requiere
    índice compuesto en Firestore.)"""
    query = db.collection("actividades").where("unidad", "==", unidad).where("activo", "==", True)
    preguntas = [{**doc.to_dict(), "id_actividad": doc.id} for doc in query.stream()]
    return sorted(preguntas, key=lambda p: (p.get("leccion") or 0, p.get("orden") or 0))


def info_mundo_docente(doc, n_preguntas: int) -> dict:
    datos = doc.to_dict()
    titulo = datos.get("titulo", "")
    return {
        "id": PREFIJO_PROFESOR + doc.id,
        "seccion": SECCION_PROFESOR,
        "titulo": {"es": titulo, "en": titulo},
        "emoji": datos.get("emoji") or "🌟",
        "descripcion": datos.get("descripcion", ""),
        "lecciones": math.ceil(n_preguntas / PREGUNTAS_POR_LECCION),
        "explicacion": None,
    }


def mundos_de_docente(db, id_docente: str | None) -> list[dict]:
    """Mundos activos de un docente que ya tienen al menos una pregunta, en orden de creación.
    Una sola consulta: cada mundo guarda cuántas preguntas activas tiene (`n_preguntas`)."""
    if not id_docente:
        return []
    docs = [
        d for d in db.collection("mundos_docente").where("id_docente", "==", id_docente).stream()
        if d.to_dict().get("activo", True) and d.to_dict().get("n_preguntas", 0) > 0
    ]
    docs.sort(key=lambda d: d.to_dict().get("creado_en"))
    return [info_mundo_docente(doc, doc.to_dict()["n_preguntas"]) for doc in docs]


_CATALOGO_FIJO = {sec: [info_unidad(u) for u in unidades] for sec, unidades in ORDEN_POR_SECCION.items()}


def catalogo(db, id_estudiante: str, mundos_profe: list[dict] | None = None) -> dict:
    """{seccion: [info de cada unidad en orden]} para un estudiante concreto. El temario fijo
    se arma una sola vez al arrancar; solo los mundos del profe se consultan (o se reciben ya
    consultados, cuando se arma el panel de todo un salón)."""
    if mundos_profe is None:
        estudiante = db.collection("usuarios").document(id_estudiante).get().to_dict() or {}
        mundos_profe = mundos_de_docente(db, estudiante.get("docente_id"))
    return {**_CATALOGO_FIJO, SECCION_PROFESOR: mundos_profe}


def buscar_unidad(cat: dict, unidad: str) -> dict | None:
    return next((u for unidades in cat.values() for u in unidades if u["id"] == unidad), None)


def lecciones_de(cat: dict, seccion: str | None = None) -> list[tuple[str, int]]:
    """Lecciones de un apartado (o de todos), en el orden en que se desbloquean."""
    secciones = [seccion] if seccion else list(cat)
    return [(u["id"], n) for sec in secciones for u in cat[sec] for n in range(1, u["lecciones"] + 1)]


def preguntas_de_leccion(db, unidad: str, leccion: int) -> list[dict]:
    if es_del_profesor(unidad):
        inicio = (leccion - 1) * PREGUNTAS_POR_LECCION
        return preguntas_activas(db, unidad)[inicio:inicio + PREGUNTAS_POR_LECCION]
    query = (
        db.collection("actividades").where("unidad", "==", unidad)
        .where("leccion", "==", leccion).where("activo", "==", True)
    )
    return sorted(({**d.to_dict(), "id_actividad": d.id} for d in query.stream()), key=lambda p: p.get("orden") or 0)
