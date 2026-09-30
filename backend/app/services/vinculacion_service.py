"""
RF07/RF11: vinculación de un estudiante que ya existe con un padre o un docente.

El padre o docente demuestra que tiene acceso a la cuenta del niño escribiendo su
código de acceso y su PIN (los mismos que usa el niño para entrar). Si son correctos,
queda vinculado de inmediato:
- un padre se agrega a `acudientes_ids` (un niño puede tener varios acudientes);
- un docente pasa a ser el `docente_id` del niño (un niño tiene un solo docente).

Si el niño todavía no está registrado, el padre o docente lo crea directamente con
`POST /api/usuarios` y queda vinculado desde el inicio.

`usuario` es siempre el resultado de `auth_service.current_user()` (identidad ya
verificada por token), nunca un valor que venga del cuerpo de la petición.
"""
from fastapi import HTTPException

from app.services.auth_service import registrar_auditoria
from app.services.estudiantes_service import normalizar_codigo, verificar_codigo_y_pin
from app.services.firebase_service import get_firestore_client


def vincular_con_pin(codigo: str, pin: str, usuario: dict) -> dict:
    id_usuario = usuario["id_usuario"]
    rol = usuario["rol"]
    if rol not in ("padre", "docente"):
        raise HTTPException(400, "Rol no válido para vincularse a un estudiante")

    db = get_firestore_client()
    try:
        estudiante = verificar_codigo_y_pin(db, codigo, pin)
    except HTTPException:
        registrar_auditoria(
            db, tipo="vinculacion_fallida", actor=id_usuario, detalle={"codigo": normalizar_codigo(codigo)}
        )
        raise

    data = estudiante.to_dict()
    if rol == "padre":
        acudientes = data.get("acudientes_ids", [])
        if id_usuario not in acudientes:
            acudientes.append(id_usuario)
        estudiante.reference.update({"acudientes_ids": acudientes})
        data["acudientes_ids"] = acudientes
    else:
        docente = db.collection("usuarios").document(id_usuario).get().to_dict() or {}
        cambios = {"docente_id": id_usuario}
        if docente.get("device_id_aula"):
            cambios["device_id"] = docente["device_id_aula"]
        estudiante.reference.update(cambios)
        data.update(cambios)

    registrar_auditoria(
        db, tipo="vinculacion_confirmada", actor=id_usuario,
        detalle={"id_estudiante": estudiante.id, "rol": rol},
    )
    data.pop("pin_hash", None)
    return {**data, "id_usuario": estudiante.id}
