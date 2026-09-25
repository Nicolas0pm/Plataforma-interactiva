from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import ActividadCreate, ActividadOut, ResultadoActividad
from app.services.auth_service import current_user, registrar_auditoria, require_role
from app.services.firebase_service import get_firestore_client
from app.services.progreso_service import calcular_nivel
from app.services.recompensas_service import evaluar_recompensa

router = APIRouter(prefix="/api/actividades", tags=["actividades"])


@router.post("", response_model=ActividadOut, status_code=201)
def crear_actividad(payload: ActividadCreate, usuario: dict = Depends(require_role("docente", "admin"))):
    """RNF-ESC-01: agregar actividades no requiere tocar código, solo un documento nuevo."""
    db = get_firestore_client()
    data = payload.model_dump()
    data["activo"] = True
    ref = db.collection("actividades").document()
    ref.set(data)
    registrar_auditoria(db, tipo="actividad_creada", actor=usuario["id_usuario"], detalle={"id_actividad": ref.id})
    return {**data, "id_actividad": ref.id}


@router.get("", response_model=list[ActividadOut])
def listar_actividades(nivel: int | None = None, usuario: dict = Depends(current_user)):
    """RF04: actividades organizadas por nivel."""
    db = get_firestore_client()
    query = db.collection("actividades").where("activo", "==", True)
    if nivel is not None:
        query = query.where("nivel", "==", nivel)
    return [{**doc.to_dict(), "id_actividad": doc.id} for doc in query.stream()]


@router.post("/completar/{id_usuario}")
def completar_actividad(
    id_usuario: str, payload: ResultadoActividad, usuario: dict = Depends(require_role("estudiante"))
):
    """
    RF03/RF04/RF08/RF09: registra el intento de un estudiante, actualiza su progreso
    acumulado, calcula si subió de nivel y evalúa si desbloqueó una recompensa
    física (RF05). Solo el propio estudiante autenticado puede reportar sus
    resultados (nunca en nombre de otro).
    """
    if usuario["id_usuario"] != id_usuario:
        raise HTTPException(403, "Un estudiante solo puede registrar sus propios resultados")

    db = get_firestore_client()

    usuario_ref = db.collection("usuarios").document(id_usuario)
    if not usuario_ref.get().exists:
        raise HTTPException(404, "Usuario no encontrado")

    hist_ref = db.collection("historial_actividades").document()
    hist_ref.set(
        {
            "id_usuario": id_usuario,
            "id_actividad": payload.id_actividad,
            "fecha": datetime.now(timezone.utc),
            "tiempo_empleado": payload.tiempo_empleado,
            "intentos": payload.intentos,
            "puntaje_obtenido": payload.puntaje_obtenido,
        }
    )

    resultado_ref = usuario_ref.collection("resultados").document("actual")
    resultado_actual = resultado_ref.get().to_dict() or {
        "puntaje_total": 0,
        "nivel_logrado": 1,
        "actividades_completadas": 0,
    }
    nivel_anterior = resultado_actual["nivel_logrado"]
    nuevo_total = resultado_actual["puntaje_total"] + payload.puntaje_obtenido
    nuevo_nivel = calcular_nivel(nuevo_total)

    resultado_ref.set(
        {
            "puntaje_total": nuevo_total,
            "nivel_logrado": nuevo_nivel,
            "actividades_completadas": resultado_actual["actividades_completadas"] + 1,
            "actualizado_en": datetime.now(timezone.utc),
        },
        merge=True,
    )

    recompensa = evaluar_recompensa(id_usuario, nuevo_total)

    return {
        "id_historial": hist_ref.id,
        "puntaje_total": nuevo_total,
        "nivel_logrado": nuevo_nivel,
        "subio_de_nivel": nuevo_nivel > nivel_anterior,
        "recompensa_generada": recompensa,
    }
