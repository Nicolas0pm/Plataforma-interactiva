from datetime import datetime, timedelta, timezone

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import RutaConTransaccion, get_db
from app.models.schemas import (
    CambiarPassword,
    DevLoginRequest,
    LoginRequest,
    PinLoginRequest,
    SesionOut,
    UsuarioCreate,
    UsuarioOut,
)
from app.models.tablas import Acudiente, Progreso, Usuario
from app.services.auth_service import (
    crear_token_dev,
    crear_token_sesion,
    current_user,
    hash_password,
    hash_pin,
    normalizar_email,
    registrar_auditoria,
    require_role,
    verificar_acceso_estudiante,
    verificar_credenciales,
    verificar_password,
)
from app.services.estudiantes_service import (
    generar_codigo_acceso,
    normalizar_codigo,
    verificar_codigo_y_pin,
)
from app.services.progreso_service import calcular_nivel, puntos_para_siguiente_nivel

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"], route_class=RutaConTransaccion)
_settings = get_settings()


@router.post("", response_model=UsuarioOut, status_code=201)
def crear_usuario(
    payload: UsuarioCreate, authorization: str | None = Header(default=None), db: Session = Depends(get_db)
):
    """RF01: registro de estudiantes, docentes y padres.

    - Un estudiante lo crea un docente, un padre o un admin ya autenticado (los
      niños no se auto-registran); requiere un PIN (RF01 CA3), que se guarda
      como hash, nunca en texto plano.
    - Un docente o padre se auto-registra con su correo y una contraseña (que se guarda
      como hash scrypt) y después entra con `POST /api/usuarios/login`. Las cuentas de
      admin no se auto-registran: se crean con `scripts/crear_admin.py`.
    """
    ahora = datetime.now(timezone.utc)
    nuevo = Usuario(
        nombre=payload.nombre, edad=payload.edad, rol=payload.rol, email=payload.email,
        docente_id=payload.docente_id, device_id=payload.device_id, activo=True, creado_en=ahora,
    )
    acudientes = list(dict.fromkeys(payload.acudientes_ids))

    if payload.rol == "estudiante":
        usuario = require_role("docente", "padre", "admin")(current_user(authorization, db))
        if not payload.pin_acceso:
            raise HTTPException(400, "El estudiante necesita un PIN de 4 dígitos")
        if not payload.autoriza_datos_menor:
            raise HTTPException(
                400, "Se necesita la autorización del padre, madre o acudiente para registrar al niño"
            )
        # Evidencia de la autorización (Ley 1581 / Decreto 1377): quién, cuándo y qué versión.
        nuevo.autorizacion_otorgada_por = usuario["id_usuario"]
        nuevo.autorizacion_rol = usuario["rol"]
        nuevo.autorizacion_fecha = ahora
        nuevo.autorizacion_version = _settings.terminos_version
        nuevo.pin_hash = hash_pin(payload.pin_acceso)
        nuevo.codigo_acceso = generar_codigo_acceso(db)
        if usuario["rol"] == "docente" and not nuevo.docente_id:
            nuevo.docente_id = usuario["id_usuario"]
        if usuario["rol"] == "docente" and not nuevo.device_id:
            # Si el salón tiene máquina de premios, el niño nuevo queda conectado a ella.
            nuevo.device_id = db.get(Usuario, usuario["id_usuario"]).device_id_aula
        if usuario["rol"] == "padre" and usuario["id_usuario"] not in acudientes:
            acudientes.append(usuario["id_usuario"])
        if nuevo.docente_id and _rol_de(db, nuevo.docente_id) != "docente":
            raise HTTPException(400, "El docente indicado no existe")
        if any(_rol_de(db, i) != "padre" for i in acudientes):
            raise HTTPException(400, "Alguno de los acudientes indicados no existe")
        nuevo.vinculos_acudientes = [Acudiente(id_acudiente=i) for i in acudientes]
    else:
        if payload.rol == "admin" and not _settings.use_fake_db:
            raise HTTPException(403, "Las cuentas de administrador se crean con scripts/crear_admin.py")
        if not payload.acepta_terminos:
            raise HTTPException(400, "Debes aceptar los Términos de uso y la Política de datos")
        nuevo.terminos_version, nuevo.terminos_fecha = _settings.terminos_version, ahora
        # Un adulto no se registra ya vinculado a nadie.
        nuevo.docente_id = None
        # Sin correo ni contraseña solo se puede en el modo de prueba (cuentas de desarrollo).
        if not _settings.use_fake_db and not (payload.email and payload.password):
            raise HTTPException(400, "Escribe tu correo y una contraseña")
        if payload.email:
            nuevo.email = normalizar_email(payload.email)
            if db.scalar(select(Usuario.id_usuario).where(Usuario.email == nuevo.email)):
                raise HTTPException(409, "Ya existe una cuenta con ese correo. Inicia sesión.")
        if payload.password:
            nuevo.password_hash = hash_password(payload.password)

    db.add(nuevo)
    db.flush()  # asigna el id_usuario

    if payload.rol == "estudiante":
        db.add(Progreso(id_usuario=nuevo.id_usuario, actualizado_en=ahora))
        registrar_auditoria(db, tipo="estudiante_creado", actor=None, detalle={"id_usuario": nuevo.id_usuario})
    else:
        registrar_auditoria(db, tipo="adulto_registrado", actor=nuevo.id_usuario, detalle={"rol": nuevo.rol})

    return nuevo.a_dict()


def _rol_de(db: Session, id_usuario: str) -> str | None:
    return db.scalar(select(Usuario.rol).where(Usuario.id_usuario == id_usuario))


def _estudiantes_de(db: Session, id_docente: str) -> list[Usuario]:
    consulta = select(Usuario).where(Usuario.docente_id == id_docente, Usuario.rol == "estudiante")
    return list(db.scalars(consulta))


@router.post("/login-pin", response_model=SesionOut)
def login_pin(payload: PinLoginRequest, db: Session = Depends(get_db)):
    """RF01 CA3: acceso simplificado del estudiante mediante código corto + PIN visual."""
    codigo = normalizar_codigo(payload.codigo)
    try:
        estudiante = verificar_codigo_y_pin(db, codigo, payload.pin)
    except HTTPException:
        registrar_auditoria(db, tipo="login_fallido", actor=None, detalle={"metodo": "pin", "codigo": codigo})
        raise

    registrar_auditoria(db, tipo="login_exitoso", actor=estudiante.id_usuario, detalle={"metodo": "pin", "codigo": codigo})
    return {
        "token": crear_token_sesion(estudiante.id_usuario, "estudiante"),
        "id_usuario": estudiante.id_usuario,
        "rol": "estudiante",
        "nombre": estudiante.nombre,
        "codigo_acceso": estudiante.codigo_acceso,
    }


@router.post("/login", response_model=SesionOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Docente/padre/admin: correo + contraseña. Tras 5 fallos seguidos ese correo queda
    bloqueado 10 minutos."""
    email = normalizar_email(payload.email)
    try:
        perfil = verificar_credenciales(db, email, payload.password)
    except HTTPException:
        registrar_auditoria(db, tipo="login_fallido", actor=None, detalle={"metodo": "correo", "email": email})
        raise
    registrar_auditoria(db, tipo="login_exitoso", actor=perfil.id_usuario, detalle={"metodo": "correo"})
    return {
        "token": crear_token_sesion(perfil.id_usuario, perfil.rol),
        "id_usuario": perfil.id_usuario,
        "rol": perfil.rol,
        "nombre": perfil.nombre,
    }


@router.post("/cambiar-password")
def cambiar_password(payload: CambiarPassword, usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    """El adulto cambia su contraseña (por ejemplo, la temporal que le dio el admin)."""
    perfil = db.get(Usuario, usuario["id_usuario"])
    if perfil.rol == "estudiante":
        raise HTTPException(400, "Los estudiantes entran con su PIN")
    if not verificar_password(payload.actual, perfil.password_hash):
        raise HTTPException(400, "La contraseña actual no es correcta")
    perfil.password_hash = hash_password(payload.nueva)
    registrar_auditoria(db, tipo="password_cambiada", actor=perfil.id_usuario)
    return {"ok": True}


@router.post("/login-dev", response_model=SesionOut)
def login_dev(payload: DevLoginRequest, db: Session = Depends(get_db)):
    """Login de desarrollo (solo con USE_FAKE_DB=true): permite entrar como
    docente/padre/admin sin contraseña."""
    perfil = db.get(Usuario, payload.id_usuario)
    if perfil is None or perfil.rol != payload.rol:
        raise HTTPException(404, "No existe ese usuario con ese rol")

    token = crear_token_dev(payload.id_usuario, payload.rol)
    return {"token": token, "id_usuario": payload.id_usuario, "rol": payload.rol, "nombre": perfil.nombre}


@router.get("/sesion", response_model=UsuarioOut)
def sesion_actual(usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    """Devuelve el perfil de quien está autenticado (para restaurar sesión en el frontend)."""
    perfil = db.get(Usuario, usuario["id_usuario"])
    if perfil is None:
        raise HTTPException(404, "Usuario no encontrado")
    return perfil.a_dict()


@router.get("/{id_usuario}", response_model=UsuarioOut)
def obtener_usuario(id_usuario: str, usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    perfil = db.get(Usuario, id_usuario)
    if perfil is None:
        raise HTTPException(404, "Usuario no encontrado")

    if perfil.rol == "estudiante":
        verificar_acceso_estudiante(usuario, id_usuario, db)
    elif usuario["rol"] != "admin" and usuario["id_usuario"] != id_usuario:
        raise HTTPException(403, "No tienes permiso para ver este perfil")

    return perfil.a_dict()


@router.get("/{id_usuario}/progreso")
def progreso_usuario(id_usuario: str, usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    """RF06/RF07/RF09: progreso consultable por el propio estudiante, su docente,
    sus padres vinculados o un admin."""
    verificar_acceso_estudiante(usuario, id_usuario, db)

    progreso = db.get(Progreso, id_usuario)
    if progreso is None:
        raise HTTPException(404, "Sin datos de progreso todavía")

    return {
        "puntaje_total": progreso.puntaje_total,
        "actividades_completadas": progreso.actividades_completadas,
        "actualizado_en": progreso.actualizado_en,
        "nivel_logrado": calcular_nivel(progreso.puntaje_total),
        "puntos_para_siguiente_nivel": puntos_para_siguiente_nivel(progreso.puntaje_total),
    }


@router.get("/docente/{id_docente}/estudiantes", response_model=list[UsuarioOut])
def estudiantes_de_docente(id_docente: str, usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    """RF06: panel del docente, lista de sus estudiantes."""
    if usuario["rol"] != "admin" and usuario["id_usuario"] != id_docente:
        raise HTTPException(403, "Solo el propio docente (o un admin) puede ver esta lista")

    return [e.a_dict() for e in _estudiantes_de(db, id_docente)]


@router.get("/docente/{id_docente}/estadisticas")
def estadisticas_docente(id_docente: str, usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    """RF06 CA3/RF09: estadísticas agregadas del grupo para el panel docente."""
    if usuario["rol"] != "admin" and usuario["id_usuario"] != id_docente:
        raise HTTPException(403, "Solo el propio docente (o un admin) puede ver estas estadísticas")

    estudiantes = _estudiantes_de(db, id_docente)
    progresos = {
        p.id_usuario: p
        for p in db.scalars(select(Progreso).where(Progreso.id_usuario.in_([e.id_usuario for e in estudiantes])))
    }

    hoy = datetime.now(timezone.utc).date()
    hace_7_dias = datetime.now(timezone.utc) - timedelta(days=7)

    total = len(estudiantes)
    suma_puntaje = 0
    activos_hoy = 0
    necesitan_ayuda = []

    for est in estudiantes:
        progreso = progresos.get(est.id_usuario)
        suma_puntaje += progreso.puntaje_total if progreso else 0

        actualizado_en = progreso.actualizado_en if progreso else None
        if actualizado_en and actualizado_en.date() == hoy:
            activos_hoy += 1
        if not actualizado_en or actualizado_en < hace_7_dias:
            necesitan_ayuda.append(UsuarioOut(**est.a_dict()))

    return {
        "total_estudiantes": total,
        "progreso_promedio": round(suma_puntaje / total, 1) if total else 0,
        "activos_hoy": activos_hoy,
        "necesitan_ayuda": necesitan_ayuda,
    }


@router.get("/padre/{id_padre}/hijos", response_model=list[UsuarioOut])
def hijos_de_padre(id_padre: str, usuario: dict = Depends(current_user), db: Session = Depends(get_db)):
    """RF07: panel de padres."""
    if usuario["rol"] != "admin" and usuario["id_usuario"] != id_padre:
        raise HTTPException(403, "Solo el propio padre/acudiente (o un admin) puede ver esta lista")

    consulta = (
        select(Usuario).join(Acudiente, Acudiente.id_estudiante == Usuario.id_usuario)
        .where(Acudiente.id_acudiente == id_padre).order_by(Usuario.nombre)
    )
    return [h.a_dict() for h in db.scalars(consulta)]


class DispensadorAula(BaseModel):
    device_id: Optional[str] = Field(default=None, max_length=60)


@router.put("/docente/{id_docente}/dispensador")
def asignar_dispensador(
    id_docente: str, payload: DispensadorAula, usuario: dict = Depends(current_user), db: Session = Depends(get_db)
):
    """RF05: la máquina de premios (ESP32) del salón. Se guarda en el docente y se asigna a
    todos sus estudiantes (y a los que registre después). Vacío = sin máquina: al completar
    un mundo los niños solo reciben la felicitación."""
    if usuario["rol"] not in ("docente", "admin") or (usuario["rol"] != "admin" and usuario["id_usuario"] != id_docente):
        raise HTTPException(403, "Solo el propio docente (o un admin) puede cambiar la máquina del salón")
    device_id = (payload.device_id or "").strip() or None
    docente = db.get(Usuario, id_docente)
    if docente is None:
        raise HTTPException(404, "Docente no encontrado")
    docente.device_id_aula = device_id
    estudiantes = _estudiantes_de(db, id_docente)
    for estudiante in estudiantes:
        estudiante.device_id = device_id
    n = len(estudiantes)
    registrar_auditoria(db, tipo="dispensador_asignado", actor=usuario["id_usuario"], detalle={"device_id": device_id, "estudiantes": n})
    return {"device_id": device_id, "estudiantes": n}
