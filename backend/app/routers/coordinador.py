"""
Panel del coordinador (rol `admin`): es quien crea las cuentas de la plataforma.

- Crea docentes, padres y otros coordinadores con un **usuario** y una contraseña temporal
  (que se muestra una sola vez). Al primer ingreso cada adulto la cambia y acepta los
  términos (`POST /api/usuarios/cambiar-password`).
- Registra a los niños (RF01) con su PIN y les asigna su docente y sus acudientes (RF07/RF11).
- Corrige los datos de una cuenta (nombre, edad del niño, correo del adulto).
- Restablece contraseñas y PIN olvidados, y desactiva o reactiva cuentas. Nada se borra:
  una cuenta desactivada no puede entrar y conserva su historial.
- Gestiona el temario fijo (RF08): apaga o vuelve a encender un mundo para toda la
  institución. Cada docente decide además qué mundos ve su salón (`routers/temario.py`).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import RutaConTransaccion, get_db
from pydantic import BaseModel

from app.curriculo import ORDEN_POR_SECCION
from app.models.schemas import AsignarEstudiante, CambiarEstado, CrearAdulto, CrearEstudiante, NuevoPin
from app.models.tablas import Acudiente, Progreso, TemaGlobal, Usuario
from app.services.auth_service import (
    hash_password,
    hash_pin,
    normalizar_email,
    password_temporal,
    registrar_auditoria,
    require_role,
)
from app.services.catalogo_service import apagados_globales
from app.services.estudiantes_service import generar_codigo_acceso

router = APIRouter(
    prefix="/api/coordinador", tags=["coordinador"], route_class=RutaConTransaccion,
    dependencies=[Depends(require_role("admin"))],
)
_settings = get_settings()
coordinador = require_role("admin")


def _adulto_con_rol(db: Session, id_usuario: str, rol: str) -> Usuario:
    usuario = db.get(Usuario, id_usuario)
    if usuario is None or usuario.rol != rol:
        raise HTTPException(400, f"No existe ese {'docente' if rol == 'docente' else 'acudiente'}")
    return usuario


def _asignar(db: Session, estudiante: Usuario, docente_id: str | None, acudientes_ids: list[str] | None) -> None:
    if docente_id is not None:
        docente = _adulto_con_rol(db, docente_id, "docente")
        estudiante.docente_id = docente.id_usuario
        # Si el salón tiene máquina de premios, el niño queda conectado a ella.
        estudiante.device_id = docente.device_id_aula
    if acudientes_ids is not None:
        ids = list(dict.fromkeys(acudientes_ids))
        for i in ids:
            _adulto_con_rol(db, i, "padre")
        actuales = {v.id_acudiente: v for v in estudiante.vinculos_acudientes}
        estudiante.vinculos_acudientes = [actuales.get(i) or Acudiente(id_acudiente=i) for i in ids]


@router.get("/usuarios")
def listar(db: Session = Depends(get_db)):
    """Todas las cuentas, separadas por rol, con lo que necesita el panel del coordinador."""
    usuarios = list(db.scalars(select(Usuario).order_by(Usuario.nombre)))
    ninos_por_docente = dict(db.execute(
        select(Usuario.docente_id, func.count()).where(Usuario.rol == "estudiante", Usuario.activo)
        .group_by(Usuario.docente_id)
    ).all())
    hijos_por_padre = dict(db.execute(
        select(Acudiente.id_acudiente, func.count()).group_by(Acudiente.id_acudiente)
    ).all())
    salida: dict[str, list] = {"coordinadores": [], "docentes": [], "padres": [], "estudiantes": []}
    for u in usuarios:
        datos = u.a_dict()
        if u.rol == "estudiante":
            salida["estudiantes"].append(datos)
            continue
        datos["debe_cambiar_password"] = u.debe_cambiar_password
        if u.rol == "docente":
            datos["estudiantes"] = ninos_por_docente.get(u.id_usuario, 0)
            salida["docentes"].append(datos)
        elif u.rol == "padre":
            datos["hijos"] = hijos_por_padre.get(u.id_usuario, 0)
            salida["padres"].append(datos)
        else:
            salida["coordinadores"].append(datos)
    return salida


@router.post("/adultos", status_code=201)
def crear_adulto(payload: CrearAdulto, yo: dict = Depends(coordinador), db: Session = Depends(get_db)):
    """Crea un docente, padre o coordinador. Devuelve su contraseña temporal UNA sola vez."""
    usuario = payload.usuario.lower()
    if db.scalar(select(Usuario.id_usuario).where(Usuario.usuario == usuario)):
        raise HTTPException(409, f"Ya existe una cuenta con el usuario «{usuario}»")
    email = normalizar_email(payload.email) if payload.email else None
    if email and db.scalar(select(Usuario.id_usuario).where(Usuario.email == email)):
        raise HTTPException(409, "Ya existe una cuenta con ese correo")
    temporal = password_temporal()
    nuevo = Usuario(
        nombre=payload.nombre.strip(), edad=0, rol=payload.rol, usuario=usuario, email=email,
        password_hash=hash_password(temporal), debe_cambiar_password=True, activo=True,
        creado_en=datetime.now(timezone.utc),
    )
    db.add(nuevo)
    db.flush()
    registrar_auditoria(db, tipo="cuenta_creada", actor=yo["id_usuario"],
                        detalle={"id_usuario": nuevo.id_usuario, "rol": nuevo.rol})
    return {**nuevo.a_dict(), "password_temporal": temporal}


@router.post("/estudiantes", status_code=201)
def crear_estudiante(payload: CrearEstudiante, yo: dict = Depends(coordinador), db: Session = Depends(get_db)):
    """RF01: registra a un niño. Devuelve su código de acceso (el PIN lo eligió el coordinador)."""
    if not payload.autoriza_datos_menor:
        raise HTTPException(400, "Se necesita la autorización del padre, madre o acudiente para registrar al niño")
    ahora = datetime.now(timezone.utc)
    nino = Usuario(
        nombre=payload.nombre.strip(), edad=payload.edad, rol="estudiante", activo=True, creado_en=ahora,
        pin_hash=hash_pin(payload.pin), codigo_acceso=generar_codigo_acceso(db),
        # Evidencia de la autorización (Ley 1581 / Decreto 1377): quién, cuándo y qué versión.
        autorizacion_otorgada_por=yo["id_usuario"], autorizacion_rol=yo["rol"],
        autorizacion_fecha=ahora, autorizacion_version=_settings.terminos_version,
    )
    _asignar(db, nino, payload.docente_id, payload.acudientes_ids)
    db.add(nino)
    db.flush()
    db.add(Progreso(id_usuario=nino.id_usuario, actualizado_en=ahora))
    registrar_auditoria(db, tipo="estudiante_creado", actor=yo["id_usuario"], detalle={"id_usuario": nino.id_usuario})
    return nino.a_dict()


@router.patch("/estudiantes/{id_estudiante}")
def asignar_estudiante(
    id_estudiante: str, payload: AsignarEstudiante, yo: dict = Depends(coordinador), db: Session = Depends(get_db)
):
    """Cambia el docente y/o los acudientes de un niño."""
    nino = db.get(Usuario, id_estudiante)
    if nino is None or nino.rol != "estudiante":
        raise HTTPException(404, "Estudiante no encontrado")
    if payload.quitar_docente:
        nino.docente_id, nino.device_id = None, None
    _asignar(db, nino, payload.docente_id, payload.acudientes_ids)
    registrar_auditoria(db, tipo="estudiante_asignado", actor=yo["id_usuario"],
                        detalle={"id_usuario": id_estudiante, "docente_id": nino.docente_id,
                                 "acudientes_ids": nino.acudientes_ids})
    db.flush()
    return nino.a_dict()


@router.post("/usuarios/{id_usuario}/restablecer-password")
def restablecer_password(id_usuario: str, yo: dict = Depends(coordinador), db: Session = Depends(get_db)):
    """Contraseña olvidada: una temporal nueva (se muestra una sola vez)."""
    adulto = db.get(Usuario, id_usuario)
    if adulto is None or adulto.rol == "estudiante":
        raise HTTPException(404, "No existe esa cuenta de adulto")
    temporal = password_temporal()
    adulto.password_hash, adulto.debe_cambiar_password = hash_password(temporal), True
    registrar_auditoria(db, tipo="password_restablecida", actor=yo["id_usuario"], detalle={"id_usuario": id_usuario})
    return {"usuario": adulto.usuario, "password_temporal": temporal}


@router.post("/estudiantes/{id_estudiante}/pin")
def cambiar_pin(id_estudiante: str, payload: NuevoPin, yo: dict = Depends(coordinador), db: Session = Depends(get_db)):
    nino = db.get(Usuario, id_estudiante)
    if nino is None or nino.rol != "estudiante":
        raise HTTPException(404, "Estudiante no encontrado")
    nino.pin_hash = hash_pin(payload.pin)
    registrar_auditoria(db, tipo="pin_cambiado", actor=yo["id_usuario"], detalle={"id_usuario": id_estudiante})
    return {"ok": True}


@router.patch("/usuarios/{id_usuario}")
def editar_usuario(id_usuario: str, payload: CambiarEstado, yo: dict = Depends(coordinador), db: Session = Depends(get_db)):
    """Corrige nombre, edad (niños) o correo (adultos) y/o desactiva (no puede entrar y se
    cierran sus sesiones) o reactiva una cuenta."""
    usuario = db.get(Usuario, id_usuario)
    if usuario is None:
        raise HTTPException(404, "Usuario no encontrado")
    cambios = payload.model_dump(exclude_unset=True)
    if cambios.get("activo") is False and id_usuario == yo["id_usuario"]:
        raise HTTPException(400, "No puedes desactivar tu propia cuenta")
    if "edad" in cambios and usuario.rol != "estudiante":
        raise HTTPException(400, "Solo los estudiantes tienen edad")
    if "email" in cambios:
        if usuario.rol == "estudiante":
            raise HTTPException(400, "Los estudiantes no tienen correo")
        email = normalizar_email(cambios["email"]) if cambios["email"] else None
        if email and db.scalar(select(Usuario.id_usuario).where(Usuario.email == email, Usuario.id_usuario != id_usuario)):
            raise HTTPException(409, "Ya existe una cuenta con ese correo")
        usuario.email = email
    if cambios.get("nombre"):
        usuario.nombre = cambios["nombre"].strip()
    if cambios.get("edad") is not None:
        usuario.edad = cambios["edad"]
    datos = {k: v for k, v in cambios.items() if k != "activo"}
    if datos:
        registrar_auditoria(db, tipo="cuenta_editada", actor=yo["id_usuario"],
                            detalle={"id_usuario": id_usuario, "campos": sorted(datos)})
    if cambios.get("activo") is not None and cambios["activo"] != usuario.activo:
        usuario.activo = cambios["activo"]
        registrar_auditoria(db, tipo="cuenta_activada" if usuario.activo else "cuenta_desactivada",
                            actor=yo["id_usuario"], detalle={"id_usuario": id_usuario})
    db.flush()
    return usuario.a_dict()


class TemaActivo(BaseModel):
    activo: bool


@router.get("/temario")
def ver_temario(db: Session = Depends(get_db)):
    """RF08: el temario fijo con su estado para toda la institución."""
    from app.routers.temario import con_info

    apagados = apagados_globales(db)
    return con_info({
        seccion: [{"id": u, "activo": u not in apagados} for u in unidades]
        for seccion, unidades in ORDEN_POR_SECCION.items()
    })


@router.patch("/temario/{unidad}")
def cambiar_tema(unidad: str, payload: TemaActivo, yo: dict = Depends(coordinador), db: Session = Depends(get_db)):
    """Apaga o enciende un mundo del temario para todos los salones. No se borra nada."""
    seccion = next((s for s, unidades in ORDEN_POR_SECCION.items() if unidad in unidades), None)
    if seccion is None:
        raise HTTPException(404, "No existe ese mundo en el temario")
    apagados = apagados_globales(db)
    if not payload.activo and all(u in apagados or u == unidad for u in ORDEN_POR_SECCION[seccion]):
        raise HTTPException(400, "Deja al menos un mundo activo en cada apartado")
    tema = db.get(TemaGlobal, unidad) or TemaGlobal(unidad=unidad)
    tema.activo = payload.activo
    db.add(tema)
    registrar_auditoria(db, tipo="temario_global", actor=yo["id_usuario"], detalle={"unidad": unidad, "activo": payload.activo})
    return {"id": unidad, "activo": payload.activo}
