from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.auth_service import registrar_auditoria, require_role
from app.services.firebase_service import get_firestore_client
from app.services.lecciones_service import guardar_progreso, leer_progreso
from app.services.tienda_service import ITEMS, comprar, equipar, perfil_de

router = APIRouter(prefix="/api/tienda", tags=["tienda"])


class Compra(BaseModel):
    item_id: str


class Equipar(BaseModel):
    item_id: Optional[str] = None
    tipo: Literal["avatar", "marco"] = "marco"


@router.get("")
def ver_tienda(usuario: dict = Depends(require_role("estudiante"))):
    """Artículos del perfil, el saldo de puntos y lo que el niño ya tiene."""
    progreso = leer_progreso(get_firestore_client(), usuario["id_usuario"])
    return {"items": ITEMS, "perfil": perfil_de(progreso)}


@router.post("/comprar")
def comprar_item(payload: Compra, usuario: dict = Depends(require_role("estudiante"))):
    db = get_firestore_client()
    progreso = leer_progreso(db, usuario["id_usuario"])
    perfil = comprar(progreso, payload.item_id)
    guardar_progreso(db, usuario["id_usuario"], progreso)
    registrar_auditoria(db, tipo="tienda_compra", actor=usuario["id_usuario"], detalle={"item": payload.item_id})
    return perfil


@router.post("/equipar")
def equipar_item(payload: Equipar, usuario: dict = Depends(require_role("estudiante"))):
    db = get_firestore_client()
    progreso = leer_progreso(db, usuario["id_usuario"])
    perfil = equipar(progreso, payload.item_id, payload.tipo)
    guardar_progreso(db, usuario["id_usuario"], progreso)
    return perfil
