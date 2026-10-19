from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import RutaConTransaccion, get_db
from app.models.schemas import ActividadCreate, ActividadOut, ResultadoActividad
from app.models.tablas import Actividad, HistorialActividad, Progreso, Usuario
from app.services.auth_service import current_user, registrar_auditoria, require_role
from app.services.progreso_service import calcular_nivel
from app.services.recompensas_service import evaluar_recompensa

router = APIRouter(prefix="/api/actividades", tags=["actividades"], route_class=RutaConTransaccion)


@router.post("", response_model=ActividadOut, status_code=201)
def crear_actividad(
    payload: ActividadCreate, usuario: dict = Depends(require_role("docente", "admin")), db: Session = Depends(get_db)
):
    """RNF-ESC-01: agregar actividades no requiere tocar código, solo una fila nueva."""
    actividad = Actividad(**payload.model_dump(), activo=True)
    db.add(actividad)
    db.flush()
    registrar_auditoria(db, tipo="actividad_creada", actor=usuario["id_usuario"], detalle={"id_actividad": actividad.id_actividad})
    return actividad.a_dict()


@router.get("", response_model=list[ActividadOut])
def listar_actividades(nivel: int | None = None, usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    """RF04: actividades organizadas por nivel."""
    consulta = select(Actividad).where(Actividad.activo)
    if nivel is not None:
        consulta = consulta.where(Actividad.nivel == nivel)
    return [a.a_dict() for a in db.scalars(consulta.order_by(Actividad.id_actividad))]


@router.post("/completar/{id_usuario}")
def completar_actividad(
    id_usuario: str, payload: ResultadoActividad, usuario: dict = Depends(require_role("estudiante")),
    db: Session = Depends(get_db),
):
    """
    RF03/RF04/RF08/RF09: registra el intento de un estudiante, actualiza su progreso
    acumulado, calcula si subió de nivel y evalúa si desbloqueó una recompensa
    física (RF05). Solo el propio estudiante autenticado puede reportar sus
    resultados (nunca en nombre de otro).
    """
    if usuario["id_usuario"] != id_usuario:
        raise HTTPException(403, "Un estudiante solo puede registrar sus propios resultados")

    if db.get(Usuario, id_usuario) is None:
        raise HTTPException(404, "Usuario no encontrado")

    ahora = datetime.now(timezone.utc)
    historial = HistorialActividad(
        id_usuario=id_usuario,
        id_actividad=payload.id_actividad,
        fecha=ahora,
        tiempo_empleado=payload.tiempo_empleado,
        intentos=payload.intentos,
        puntaje_obtenido=payload.puntaje_obtenido,
    )
    db.add(historial)

    progreso = db.get(Progreso, id_usuario)
    if progreso is None:
        progreso = Progreso(id_usuario=id_usuario, puntaje_total=0, nivel_logrado=1, actividades_completadas=0)
        db.add(progreso)
    nivel_anterior = progreso.nivel_logrado
    progreso.puntaje_total += payload.puntaje_obtenido
    progreso.nivel_logrado = calcular_nivel(progreso.puntaje_total)
    progreso.actividades_completadas += 1
    progreso.actualizado_en = ahora
    db.flush()

    recompensa = evaluar_recompensa(db, id_usuario, progreso.puntaje_total)

    return {
        "id_historial": historial.id_historial,
        "puntaje_total": progreso.puntaje_total,
        "nivel_logrado": progreso.nivel_logrado,
        "subio_de_nivel": progreso.nivel_logrado > nivel_anterior,
        "recompensa_generada": recompensa,
    }
