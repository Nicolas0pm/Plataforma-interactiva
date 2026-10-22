"""
Exámenes cada N mundos.

Cada vez que un estudiante completa N mundos de un apartado (vocabulario, gramática o los
del profe) que aún no ha evaluado, se le arma un examen con preguntas de esos N mundos. N
es el mismo número que elige su docente (`premio_cada_mundos`, de 1 a 5; sin docente, 1).

- El examen tiene hasta `PREGUNTAS_POR_EXAMEN` preguntas elegidas al azar, repartidas entre
  los mundos que evalúa, y se aprueba con `APROBAR_CON` de aciertos. No gasta vidas y se
  puede repetir hasta aprobarlo; no bloquea el avance por el camino.
- Las preguntas del temario fijo se toman como las ve el salón (con los cambios del
  docente, ver `catalogo_service.aplicar_cambios_salon`).
- **Premio físico solo en los mundos del profe**: aprobar por primera vez un examen del
  apartado "profesor" deja un premio en la cola de la máquina del salón. Los mundos del
  temario fijo se pueden jugar a cualquier hora (en casa, de noche), cuando no hay máquina
  cerca: su examen evalúa, pero no da premio físico.
- El servidor califica: las respuestas correctas no se envían al navegador antes de
  terminar el examen.
"""
import math
import random

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.curriculo import info_unidad, seccion_de
from app.db import ahora
from app.models.tablas import Actividad, Examen, Usuario
from app.services.auth_service import registrar_auditoria
from app.services.catalogo_service import SECCION_PROFESOR, aplicar_cambios_salon, buscar_unidad, es_del_profesor
from app.services.recompensas_service import premio_por_examen

PREGUNTAS_POR_EXAMEN = 10
APROBAR_CON = 0.7


def seccion_de_unidad(unidad: str) -> str:
    return SECCION_PROFESOR if es_del_profesor(unidad) else seccion_de(unidad)


def docente_de(db: Session, id_usuario: str) -> Usuario | None:
    estudiante = db.get(Usuario, id_usuario)
    return db.get(Usuario, estudiante.docente_id) if estudiante and estudiante.docente_id else None


def cada_cuantos_mundos(docente: Usuario | None) -> int:
    return max(1, (docente.premio_cada_mundos or 1) if docente else 1)


def _examenes(db: Session, id_usuario: str, seccion: str | None = None) -> list[Examen]:
    consulta = select(Examen).where(Examen.id_usuario == id_usuario)
    if seccion:
        consulta = consulta.where(Examen.seccion == seccion)
    return list(db.scalars(consulta.order_by(Examen.creado_en)))


def _preguntas_de_unidades(db: Session, unidades: list[str], id_docente: str | None) -> dict[str, list[dict]]:
    filas = db.scalars(select(Actividad).where(Actividad.unidad.in_(unidades), Actividad.activo))
    preguntas = aplicar_cambios_salon(db, id_docente, [a.a_dict() for a in filas])
    por_unidad: dict[str, list[dict]] = {u: [] for u in unidades}
    for p in preguntas:
        por_unidad[p["unidad"]].append(p)
    return por_unidad


def elegir_preguntas(por_unidad: dict[str, list[dict]], azar: random.Random | None = None) -> list[str]:
    """Hasta PREGUNTAS_POR_EXAMEN preguntas al azar, repartidas por turnos entre los mundos."""
    azar = azar or random.Random()
    montones = []
    for preguntas in por_unidad.values():
        copia = list(preguntas)
        azar.shuffle(copia)
        montones.append(copia)
    elegidas: list[str] = []
    while len(elegidas) < PREGUNTAS_POR_EXAMEN and any(montones):
        for monton in montones:
            if monton and len(elegidas) < PREGUNTAS_POR_EXAMEN:
                elegidas.append(monton.pop()["id_actividad"])
    azar.shuffle(elegidas)
    return elegidas


def nuevo_examen_si_toca(db: Session, id_usuario: str, seccion: str, progreso: dict, cat: dict) -> dict:
    """Después de completar un mundo: arma el examen si ya van N mundos sin evaluar en ese
    apartado. Devuelve {"examen": info o None, "faltan_mundos": n, "cada_mundos": N}."""
    docente = docente_de(db, id_usuario)
    cada = cada_cuantos_mundos(docente)
    evaluados = {u for e in _examenes(db, id_usuario, seccion) for u in e.unidades}
    completados = sorted(
        (fecha, unidad) for unidad, fecha in progreso["mundos_completados"].items()
        if seccion_de_unidad(unidad) == seccion
    )
    sin_evaluar = [unidad for _, unidad in completados if unidad not in evaluados]
    if len(sin_evaluar) < cada:
        return {"examen": None, "faltan_mundos": cada - len(sin_evaluar), "cada_mundos": cada}

    unidades = sin_evaluar[:cada]
    preguntas = elegir_preguntas(_preguntas_de_unidades(db, unidades, docente.id_usuario if docente else None))
    if not preguntas:
        return {"examen": None, "faltan_mundos": 0, "cada_mundos": cada}
    examen = Examen(id_usuario=id_usuario, seccion=seccion, unidades=unidades, preguntas=preguntas,
                    estado="pendiente", creado_en=ahora())
    db.add(examen)
    db.flush()
    registrar_auditoria(db, tipo="examen_creado", actor=id_usuario,
                        detalle={"id_examen": examen.id_examen, "seccion": seccion, "unidades": unidades})
    return {"examen": info_examen(examen, cat), "faltan_mundos": 0, "cada_mundos": cada}


def _info_unidades(unidades: list[str], cat: dict) -> list[dict]:
    salida = []
    for unidad in unidades:
        info = buscar_unidad(cat, unidad)
        if info is None and not es_del_profesor(unidad):
            info = info_unidad(unidad)  # el docente lo apagó después: se muestra igual
        salida.append({"id": unidad, "titulo": (info or {}).get("titulo") or {"es": "Mundo", "en": "World"},
                       "emoji": (info or {}).get("emoji") or "🌟"})
    return salida


def info_examen(examen: Examen, cat: dict) -> dict:
    return {
        "id_examen": examen.id_examen,
        "seccion": examen.seccion,
        "mundos": _info_unidades(examen.unidades, cat),
        "estado": examen.estado,
        "intentos": examen.intentos,
        "mejor": examen.mejor,
        "total": len(examen.preguntas),
        "da_premio": examen.seccion == SECCION_PROFESOR,
        "creado_en": examen.creado_en,
        "aprobado_en": examen.aprobado_en,
    }


def examenes_de(db: Session, id_usuario: str, cat: dict) -> list[dict]:
    """Exámenes del estudiante: primero los pendientes, después los aprobados (recientes primero)."""
    examenes = _examenes(db, id_usuario)
    pendientes = [e for e in examenes if e.estado == "pendiente"]
    aprobados = sorted((e for e in examenes if e.estado == "aprobado"), key=lambda e: e.aprobado_en, reverse=True)
    return [info_examen(e, cat) for e in pendientes + aprobados]


def _examen_propio(db: Session, id_examen: str, id_usuario: str) -> Examen:
    examen = db.get(Examen, id_examen)
    if examen is None or examen.id_usuario != id_usuario:
        raise HTTPException(404, "No existe ese examen")
    return examen


def _preguntas_del_examen(db: Session, examen: Examen) -> list[dict]:
    """Las preguntas elegidas, como las ve hoy el salón (si el docente ocultó alguna, sale)."""
    docente = docente_de(db, examen.id_usuario)
    filas = {a.id_actividad: a.a_dict() for a in db.scalars(
        select(Actividad).where(Actividad.id_actividad.in_(examen.preguntas), Actividad.activo)
    )}
    vigentes = aplicar_cambios_salon(db, docente.id_usuario if docente else None,
                                     [filas[i] for i in examen.preguntas if i in filas])
    if not vigentes:
        raise HTTPException(404, "Este examen ya no tiene preguntas")
    return vigentes


def armar_examen(db: Session, id_examen: str, id_usuario: str, cat: dict) -> dict:
    examen = _examen_propio(db, id_examen, id_usuario)
    return {
        **info_examen(examen, cat),
        "aprobar_con": APROBAR_CON,
        "preguntas": [
            {k: p.get(k) for k in ("id_actividad", "pregunta", "opciones", "icono", "imagen", "formato_opciones")}
            for p in _preguntas_del_examen(db, examen)
        ],
    }


def calificar_examen(db: Session, id_examen: str, id_usuario: str, respuestas: list[dict], cat: dict) -> dict:
    examen = _examen_propio(db, id_examen, id_usuario)
    preguntas = {p["id_actividad"]: p for p in _preguntas_del_examen(db, examen)}
    ids = [r["id_actividad"] for r in respuestas]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Cada pregunta se responde una sola vez")
    if any(i not in preguntas for i in ids):
        raise HTTPException(400, "Una de las respuestas no pertenece a este examen")

    dadas = {r["id_actividad"]: r["respuesta"] for r in respuestas}
    errores = [
        {"id_actividad": i, "pregunta": p.get("pregunta"), "icono": p.get("icono"),
         "respuesta_dada": dadas.get(i), "respuesta_correcta": p.get("respuesta_correcta"),
         "formato_opciones": p.get("formato_opciones", "texto")}
        for i, p in preguntas.items() if dadas.get(i) != p.get("respuesta_correcta")
    ]
    total = len(preguntas)
    aciertos = total - len(errores)
    necesarios = math.ceil(APROBAR_CON * total - 1e-9)
    aprobado = aciertos >= necesarios

    primera_vez = aprobado and examen.estado != "aprobado"
    examen.intentos += 1
    examen.mejor = max(examen.mejor, aciertos)
    recompensa = None
    if primera_vez:
        examen.estado, examen.aprobado_en = "aprobado", ahora()
        if examen.seccion == SECCION_PROFESOR:
            mundos = _info_unidades(examen.unidades, cat)
            recompensa = premio_por_examen(db, id_usuario, examen.id_examen, mundos)
            examen.id_historial = recompensa["id_historial"]
    registrar_auditoria(db, tipo="examen_terminado", actor=id_usuario,
                        detalle={"id_examen": examen.id_examen, "aciertos": aciertos, "total": total,
                                 "aprobado": aprobado, "con_premio": bool(recompensa and recompensa["device_id"])})
    return {
        "aprobado": aprobado,
        "primera_vez": primera_vez,
        "aciertos": aciertos,
        "total": total,
        "necesarios": necesarios,
        "errores": errores,
        "recompensa": recompensa,
        "examen": info_examen(examen, cat),
    }
