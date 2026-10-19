"""
RF07/RF11: vinculación de un estudiante que ya existe con un padre o un docente.

El padre o docente demuestra que tiene acceso a la cuenta del niño escribiendo su
código de acceso y su PIN (los mismos que usa el niño para entrar). Si son correctos,
queda vinculado de inmediato:
- un padre se agrega a la tabla `acudientes` (un niño puede tener varios);
- un docente pasa a ser el `docente_id` del niño (un niño tiene un solo docente).

Si el niño todavía no está registrado, el padre o docente lo crea directamente con
`POST /api/usuarios` y queda vinculado desde el inicio.

`usuario` es siempre el resultado de `auth_service.current_user()` (identidad ya
verificada por token), nunca un valor que venga del cuerpo de la petición.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.tablas import Acudiente, Usuario
from app.services.auth_service import registrar_auditoria
from app.services.estudiantes_service import normalizar_codigo, verificar_codigo_y_pin


def vincular_con_pin(db: Session, codigo: str, pin: str, usuario: dict) -> dict:
    id_usuario = usuario["id_usuario"]
    rol = usuario["rol"]
    if rol not in ("padre", "docente"):
        raise HTTPException(400, "Rol no válido para vincularse a un estudiante")

    try:
        estudiante = verificar_codigo_y_pin(db, codigo, pin)
    except HTTPException:
        registrar_auditoria(
            db, tipo="vinculacion_fallida", actor=id_usuario, detalle={"codigo": normalizar_codigo(codigo)}
        )
        raise

    if rol == "padre":
        if id_usuario not in estudiante.acudientes_ids:
            estudiante.vinculos_acudientes.append(Acudiente(id_acudiente=id_usuario))
    else:
        estudiante.docente_id = id_usuario
        docente = db.get(Usuario, id_usuario)
        if docente and docente.device_id_aula:
            estudiante.device_id = docente.device_id_aula

    registrar_auditoria(
        db, tipo="vinculacion_confirmada", actor=id_usuario,
        detalle={"id_estudiante": estudiante.id_usuario, "rol": rol},
    )
    db.flush()
    return estudiante.a_dict()
