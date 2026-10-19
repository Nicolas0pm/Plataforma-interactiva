from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import RutaConTransaccion, get_db
from app.models.schemas import ResultadoLeccion
from app.models.tablas import Usuario
from app.services.auth_service import (
    current_user,
    registrar_auditoria,
    require_role,
    verificar_acceso_estudiante,
)
from app.services.catalogo_service import catalogo, mundos_de_docente
from app.services.lecciones_service import (
    armar_leccion,
    leer_progresos,
    motivos_de_ayuda,
    registrar_resultado,
    resumen_aprendizaje,
)

router = APIRouter(prefix="/api/lecciones", tags=["lecciones"], route_class=RutaConTransaccion)
ZONA = timezone(timedelta(hours=get_settings().zona_horaria_utc))


def _como_local(fecha: datetime | None) -> datetime | None:
    if fecha is None:
        return None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(ZONA)


@router.get("/jugar")
def jugar(
    seccion: str = "vocabulario",
    unidad: str | None = None,
    leccion: int | None = None,
    usuario: dict = Depends(require_role("estudiante")),
    db: Session = Depends(get_db),
):
    """RF03/RF04: con `seccion` ("vocabulario" o "gramatica") entrega la lección que le toca
    en ese camino (el niño elige el camino; la lección la elige la plataforma).
    Con `unidad` y `leccion` solo permite repetir una lección ya aprobada (práctica)."""
    return armar_leccion(db, usuario["id_usuario"], unidad, leccion, seccion)


@router.post("/resultado")
def resultado(payload: ResultadoLeccion, usuario: dict = Depends(require_role("estudiante")), db: Session = Depends(get_db)):
    """RF03/RF04/RF05/RF08/RF09: califica la lección en el servidor, guarda en qué acertó y
    en qué se equivocó, suma puntos y evalúa recompensas."""
    datos = registrar_resultado(
        db, usuario["id_usuario"], payload.unidad, payload.leccion,
        [r.model_dump() for r in payload.respuestas],
    )
    registrar_auditoria(
        db, tipo="leccion_terminada", actor=usuario["id_usuario"],
        detalle={"unidad": payload.unidad, "leccion": payload.leccion, "aprobada": datos["aprobada"],
                 "aciertos": datos["aciertos"], "total": datos["total"]},
    )
    return datos


@router.get("/resumen/{id_usuario}")
def resumen(id_usuario: str, usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    """Camino, precisión por tema, últimos intentos y errores frecuentes de un estudiante.
    Lo ven el propio niño, su docente y sus padres vinculados."""
    verificar_acceso_estudiante(usuario, id_usuario, db)
    return resumen_aprendizaje(db, id_usuario)


@router.get("/docente/{id_docente}")
def resumen_docente(
    id_docente: str, usuario: dict = Depends(require_role("docente", "admin")), db: Session = Depends(get_db)
):
    """RF06/RF09: todo lo que necesita el panel del docente en una sola llamada."""
    if usuario["rol"] != "admin" and usuario["id_usuario"] != id_docente:
        raise HTTPException(403, "Solo el propio docente (o un admin) puede ver este resumen")

    ahora = datetime.now(timezone.utc)
    hoy = ahora.astimezone(ZONA).date()
    estudiantes = list(db.scalars(
        select(Usuario).where(Usuario.docente_id == id_docente, Usuario.rol == "estudiante")
    ))

    filas = []
    por_tema: dict[str, dict] = {}
    info_tema: dict[str, dict] = {}
    cat = catalogo(db, "", mundos_profe=mundos_de_docente(db, id_docente))  # igual para todo el salón
    progresos = leer_progresos(db, [e.id_usuario for e in estudiantes])
    for estudiante in estudiantes:
        r = resumen_aprendizaje(db, estudiante.id_usuario, progreso=progresos[estudiante.id_usuario], cat=cat)
        actualizado = _como_local(r["ultima_actividad"])
        horas_hoy = sorted(f for f in (_como_local(x) for x in r["actividad"]) if f.date() == hoy)
        motivos = motivos_de_ayuda(r, ahora)
        for unidad in r["unidades"]:
            if unidad["precision"] is not None:
                info_tema[unidad["id"]] = {"titulo": unidad["titulo"], "emoji": unidad["emoji"], "seccion": unidad["seccion"]}
                tema = por_tema.setdefault(unidad["id"], {"suma": 0.0, "n": 0})
                tema["suma"] += unidad["precision"]
                tema["n"] += 1
        filas.append({
            "id_usuario": estudiante.id_usuario,
            "nombre": estudiante.nombre,
            "codigo_acceso": estudiante.codigo_acceso,
            "perfil": {"avatar_emoji": r["perfil"]["avatar_emoji"], "marco": r["perfil"]["marco"]},
            "mundos_completados": r["mundos_completados"],
            "nivel_logrado": r["nivel_logrado"],
            "puntaje_total": r["puntaje_total"],
            "lecciones_aprobadas": r["lecciones_aprobadas"],
            "total_lecciones": r["total_lecciones"],
            "precision": r["precision"],
            "siguiente": r["siguiente"],
            "activo_hoy": bool(horas_hoy),
            "ultima_actividad": actualizado,
            "horas_hoy": horas_hoy,
            "necesita_ayuda": bool(motivos),
            "motivos": motivos,
        })

    filas.sort(key=lambda f: (f["nombre"] or "").lower())
    total = len(filas)
    temas = sorted(
        (
            {"unidad": u, **info_tema[u], "precision": round(t["suma"] / t["n"], 2)}
            for u, t in por_tema.items()
        ),
        key=lambda t: t["precision"],
    )
    return {
        "estudiantes": filas,
        "total_estudiantes": total,
        "activos_hoy": sum(1 for f in filas if f["activo_hoy"]),
        "necesitan_ayuda": sum(1 for f in filas if f["necesita_ayuda"]),
        "progreso_promedio": round(sum(f["lecciones_aprobadas"] / f["total_lecciones"] for f in filas) / total * 100)
        if total else 0,
        "temas": temas,
        "dispensador": db.scalar(select(Usuario.device_id_aula).where(Usuario.id_usuario == id_docente)),
    }
