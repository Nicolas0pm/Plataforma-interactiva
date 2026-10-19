from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import RutaConTransaccion, get_db
from app.models.schemas import UsuarioOut, VincularConPin
from app.services.auth_service import require_role
from app.services.vinculacion_service import vincular_con_pin

router = APIRouter(prefix="/api/vinculacion", tags=["vinculacion"], route_class=RutaConTransaccion)


@router.post("", response_model=UsuarioOut)
def vincular(payload: VincularConPin, usuario: dict = Depends(require_role("docente", "padre")), db: Session = Depends(get_db)):
    """
    RF07/RF11: un padre o docente se vincula con un estudiante que ya existe
    escribiendo el código de acceso y el PIN del niño.
    """
    return vincular_con_pin(db, payload.codigo, payload.pin, usuario)
