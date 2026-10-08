from datetime import datetime, timedelta, timezone

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models.schemas import (
    CodigoVerificacion,
    DevLoginRequest,
    PinLoginRequest,
    SesionOut,
    UsuarioCreate,
    UsuarioOut,
)
from app.services.auth_service import (
    crear_token_dev,
    crear_token_sesion,
    current_user,
    hash_pin,
    registrar_auditoria,
    require_role,
    usuario_autenticado,
    verificar_acceso_estudiante,
    verificar_id_token_firebase_crudo,
)
from app.services.estudiantes_service import (
    generar_codigo_acceso,
    normalizar_codigo,
    verificar_codigo_y_pin,
)
from app.services.firebase_service import get_firestore_client
from app.services.progreso_service import calcular_nivel, puntos_para_siguiente_nivel
from app.services.verificacion_service import confirmar_codigo, enviar_codigo

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])
_settings = get_settings()


@router.post("", response_model=UsuarioOut, status_code=201)
def crear_usuario(payload: UsuarioCreate, authorization: str | None = Header(default=None)):
    """RF01: registro de estudiantes, docentes y padres.

    - Un estudiante lo crea un docente, un padre o un admin ya autenticado (los
      niños no se auto-registran); requiere un PIN (RF01 CA3), que se guarda
      como hash, nunca en texto plano.
    - Un docente/padre/admin se auto-registra: primero crea su cuenta con el SDK
      web de Firebase Authentication y llama a este endpoint con el ID token
      resultante en `Authorization`, para vincular ese `auth_uid` a su perfil.
      Queda con `email_verificado: False` y se le envía un código al correo
      (`POST /verificacion/confirmar`); hasta confirmarlo no puede usar la API.
    """
    db = get_firestore_client()
    data = payload.model_dump(exclude={"pin_acceso", "auth_uid", "acepta_terminos", "autoriza_datos_menor"})
    data["activo"] = True
    ahora = datetime.now(timezone.utc)
    data["creado_en"] = ahora

    if payload.rol == "estudiante":
        usuario = require_role("docente", "padre", "admin")(current_user(authorization))
        if not payload.pin_acceso:
            raise HTTPException(400, "El estudiante necesita un PIN de 4 dígitos")
        if not payload.autoriza_datos_menor:
            raise HTTPException(
                400, "Se necesita la autorización del padre, madre o acudiente para registrar al niño"
            )
        # Evidencia de la autorización (Ley 1581 / Decreto 1377): quién, cuándo y qué versión.
        data["autorizacion_datos"] = {
            "otorgada_por": usuario["id_usuario"],
            "rol": usuario["rol"],
            "fecha": ahora,
            "version_terminos": _settings.terminos_version,
        }
        data["pin_hash"] = hash_pin(payload.pin_acceso)
        data["codigo_acceso"] = generar_codigo_acceso(db)
        data["auth_uid"] = None
        if usuario["rol"] == "docente" and not data.get("docente_id"):
            data["docente_id"] = usuario["id_usuario"]
        if usuario["rol"] == "docente" and not data.get("device_id"):
            # Si el salón tiene máquina de premios, el niño nuevo queda conectado a ella.
            docente = db.collection("usuarios").document(usuario["id_usuario"]).get().to_dict() or {}
            data["device_id"] = docente.get("device_id_aula")
        if usuario["rol"] == "padre" and usuario["id_usuario"] not in data.get("acudientes_ids", []):
            data.setdefault("acudientes_ids", []).append(usuario["id_usuario"])
    else:
        if not payload.acepta_terminos:
            raise HTTPException(400, "Debes aceptar los Términos de uso y la Política de datos")
        data["terminos_aceptados"] = {"version": _settings.terminos_version, "fecha": ahora}
        if _settings.use_fake_db:
            # Modo dev: no hay Firebase Authentication real, se confía en el auth_uid enviado.
            data["auth_uid"] = payload.auth_uid or f"dev-{payload.email or payload.nombre}"
        else:
            info = verificar_id_token_firebase_crudo(authorization)
            data["auth_uid"] = info["auth_uid"]
            data["email"] = payload.email or info["email"]
        # Sin correo solo se puede en el modo de prueba (cuentas de desarrollo).
        data["email_verificado"] = not data.get("email")

    ref = db.collection("usuarios").document()
    ref.set(data)

    aviso_correo = None
    if not data.get("email_verificado", True):
        try:
            enviar_codigo(db, ref.id, data, forzar=True)
        except HTTPException as exc:
            # La cuenta queda creada; desde la pantalla de confirmación puede pedir otro código.
            aviso_correo = exc.detail

    if payload.rol == "estudiante":
        ref.collection("resultados").document("actual").set(
            {
                "puntaje_total": 0,
                "nivel_logrado": 1,
                "actividades_completadas": 0,
                "actualizado_en": datetime.now(timezone.utc),
            }
        )
        registrar_auditoria(db, tipo="estudiante_creado", actor=None, detalle={"id_usuario": ref.id})

    return {**data, "id_usuario": ref.id, "aviso_correo": aviso_correo}


@router.post("/login-pin", response_model=SesionOut)
def login_pin(payload: PinLoginRequest):
    """RF01 CA3: acceso simplificado del estudiante mediante código corto + PIN visual."""
    db = get_firestore_client()
    codigo = normalizar_codigo(payload.codigo)
    try:
        doc = verificar_codigo_y_pin(db, codigo, payload.pin)
    except HTTPException:
        registrar_auditoria(db, tipo="login_fallido", actor=None, detalle={"metodo": "pin", "codigo": codigo})
        raise

    registrar_auditoria(db, tipo="login_exitoso", actor=doc.id, detalle={"metodo": "pin", "codigo": codigo})
    data = doc.to_dict()
    token = crear_token_sesion(doc.id, "estudiante")
    return {
        "token": token,
        "id_usuario": doc.id,
        "rol": "estudiante",
        "nombre": data.get("nombre"),
        "codigo_acceso": data.get("codigo_acceso"),
    }


@router.post("/login-dev", response_model=SesionOut)
def login_dev(payload: DevLoginRequest):
    """Login de desarrollo (solo con USE_FAKE_DB=true): permite entrar como
    docente/padre/admin sin un proyecto de Firebase Authentication real."""
    db = get_firestore_client()
    doc = db.collection("usuarios").document(payload.id_usuario).get()
    if not doc.exists or doc.to_dict().get("rol") != payload.rol:
        raise HTTPException(404, "No existe ese usuario con ese rol")

    token = crear_token_dev(payload.id_usuario, payload.rol)
    return {
        "token": token,
        "id_usuario": payload.id_usuario,
        "rol": payload.rol,
        "nombre": doc.to_dict().get("nombre"),
    }


@router.post("/verificacion/reenviar")
def reenviar_codigo(usuario: dict = Depends(usuario_autenticado)):
    """Envía un código nuevo al correo del adulto (el anterior deja de servir)."""
    db = get_firestore_client()
    datos = db.collection("usuarios").document(usuario["id_usuario"]).get().to_dict() or {}
    if datos.get("email_verificado", True):
        return {"ok": True, "ya_verificado": True}
    enviar_codigo(db, usuario["id_usuario"], datos)
    return {"ok": True, "email": datos.get("email")}


@router.post("/verificacion/confirmar")
def confirmar_correo(payload: CodigoVerificacion, usuario: dict = Depends(usuario_autenticado)):
    db = get_firestore_client()
    confirmar_codigo(db, usuario["id_usuario"], payload.codigo)
    datos = db.collection("usuarios").document(usuario["id_usuario"]).get().to_dict() or {}
    if not _settings.use_fake_db and datos.get("auth_uid"):
        # Que Firebase Authentication también lo marque como verificado.
        try:
            from app.services.firebase_service import get_firebase_auth

            get_firebase_auth().update_user(datos["auth_uid"], email_verified=True)
        except Exception:
            pass
    registrar_auditoria(db, tipo="email_verificado", actor=usuario["id_usuario"])
    return {"ok": True}


@router.get("/sesion", response_model=UsuarioOut)
def sesion_actual(usuario: dict = Depends(usuario_autenticado)):
    """Devuelve el perfil de quien está autenticado (para restaurar sesión en el frontend).
    Responde aunque no haya confirmado su correo: así el frontend sabe que debe pedir el código."""
    db = get_firestore_client()
    doc = db.collection("usuarios").document(usuario["id_usuario"]).get()
    if not doc.exists:
        raise HTTPException(404, "Usuario no encontrado")
    return {**doc.to_dict(), "id_usuario": doc.id}


@router.get("/{id_usuario}", response_model=UsuarioOut)
def obtener_usuario(id_usuario: str, usuario: dict = Depends(current_user)):
    db = get_firestore_client()
    doc = db.collection("usuarios").document(id_usuario).get()
    if not doc.exists:
        raise HTTPException(404, "Usuario no encontrado")

    data = doc.to_dict()
    if data.get("rol") == "estudiante":
        verificar_acceso_estudiante(usuario, id_usuario, db)
    elif usuario["rol"] != "admin" and usuario["id_usuario"] != id_usuario:
        raise HTTPException(403, "No tienes permiso para ver este perfil")

    return {**data, "id_usuario": doc.id}


@router.get("/{id_usuario}/progreso")
def progreso_usuario(id_usuario: str, usuario: dict = Depends(current_user)):
    """RF06/RF07/RF09: progreso consultable por el propio estudiante, su docente,
    sus padres vinculados o un admin."""
    db = get_firestore_client()
    verificar_acceso_estudiante(usuario, id_usuario, db)

    resultado = (
        db.collection("usuarios").document(id_usuario).collection("resultados").document("actual").get()
    )
    if not resultado.exists:
        raise HTTPException(404, "Sin datos de progreso todavía")

    data = resultado.to_dict()
    return {
        **data,
        "nivel_logrado": calcular_nivel(data.get("puntaje_total", 0)),
        "puntos_para_siguiente_nivel": puntos_para_siguiente_nivel(data.get("puntaje_total", 0)),
    }


@router.get("/docente/{id_docente}/estudiantes", response_model=list[UsuarioOut])
def estudiantes_de_docente(id_docente: str, usuario: dict = Depends(current_user)):
    """RF06: panel del docente, lista de sus estudiantes."""
    if usuario["rol"] != "admin" and usuario["id_usuario"] != id_docente:
        raise HTTPException(403, "Solo el propio docente (o un admin) puede ver esta lista")

    db = get_firestore_client()
    query = db.collection("usuarios").where("docente_id", "==", id_docente).where(
        "rol", "==", "estudiante"
    )
    return [{**doc.to_dict(), "id_usuario": doc.id} for doc in query.stream()]


@router.get("/docente/{id_docente}/estadisticas")
def estadisticas_docente(id_docente: str, usuario: dict = Depends(current_user)):
    """RF06 CA3/RF09: estadísticas agregadas del grupo para el panel docente."""
    if usuario["rol"] != "admin" and usuario["id_usuario"] != id_docente:
        raise HTTPException(403, "Solo el propio docente (o un admin) puede ver estas estadísticas")

    db = get_firestore_client()
    estudiantes = list(
        db.collection("usuarios").where("docente_id", "==", id_docente).where(
            "rol", "==", "estudiante"
        ).stream()
    )

    hoy = datetime.now(timezone.utc).date()
    hace_7_dias = datetime.now(timezone.utc) - timedelta(days=7)

    total = len(estudiantes)
    suma_puntaje = 0
    activos_hoy = 0
    necesitan_ayuda = []

    for est in estudiantes:
        resultado = (
            db.collection("usuarios").document(est.id).collection("resultados").document("actual").get()
        )
        r = resultado.to_dict() or {"puntaje_total": 0, "actualizado_en": None}
        suma_puntaje += r.get("puntaje_total", 0)

        actualizado_en = r.get("actualizado_en")
        if actualizado_en and getattr(actualizado_en, "date", lambda: None)() == hoy:
            activos_hoy += 1
        if not actualizado_en or actualizado_en < hace_7_dias:
            necesitan_ayuda.append(UsuarioOut(**est.to_dict(), id_usuario=est.id))

    return {
        "total_estudiantes": total,
        "progreso_promedio": round(suma_puntaje / total, 1) if total else 0,
        "activos_hoy": activos_hoy,
        "necesitan_ayuda": necesitan_ayuda,
    }


@router.get("/padre/{id_padre}/hijos", response_model=list[UsuarioOut])
def hijos_de_padre(id_padre: str, usuario: dict = Depends(current_user)):
    """RF07: panel de padres."""
    if usuario["rol"] != "admin" and usuario["id_usuario"] != id_padre:
        raise HTTPException(403, "Solo el propio padre/acudiente (o un admin) puede ver esta lista")

    db = get_firestore_client()
    query = db.collection("usuarios").where("acudientes_ids", "array_contains", id_padre)
    return [{**doc.to_dict(), "id_usuario": doc.id} for doc in query.stream()]


class DispensadorAula(BaseModel):
    device_id: Optional[str] = Field(default=None, max_length=60)


@router.put("/docente/{id_docente}/dispensador")
def asignar_dispensador(id_docente: str, payload: DispensadorAula, usuario: dict = Depends(current_user)):
    """RF05: la máquina de premios (ESP32) del salón. Se guarda en el docente y se asigna a
    todos sus estudiantes (y a los que registre después). Vacío = sin máquina: al completar
    un mundo los niños solo reciben la felicitación."""
    if usuario["rol"] not in ("docente", "admin") or (usuario["rol"] != "admin" and usuario["id_usuario"] != id_docente):
        raise HTTPException(403, "Solo el propio docente (o un admin) puede cambiar la máquina del salón")
    device_id = (payload.device_id or "").strip() or None
    db = get_firestore_client()
    db.collection("usuarios").document(id_docente).update({"device_id_aula": device_id})
    estudiantes = db.collection("usuarios").where("docente_id", "==", id_docente).where("rol", "==", "estudiante")
    n = 0
    for doc in estudiantes.stream():
        doc.reference.update({"device_id": device_id})
        n += 1
    registrar_auditoria(db, tipo="dispensador_asignado", actor=usuario["id_usuario"], detalle={"device_id": device_id, "estudiantes": n})
    return {"device_id": device_id, "estudiantes": n}
