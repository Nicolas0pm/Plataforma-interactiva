from fastapi import APIRouter, Depends

from app.models.schemas import UsuarioOut, VincularConPin
from app.services.auth_service import require_role
from app.services.vinculacion_service import vincular_con_pin

router = APIRouter(prefix="/api/vinculacion", tags=["vinculacion"])


@router.post("", response_model=UsuarioOut)
def vincular(payload: VincularConPin, usuario: dict = Depends(require_role("docente", "padre"))):
    """
    RF07/RF11: un padre o docente se vincula con un estudiante que ya existe
    escribiendo el código de acceso y el PIN del niño.
    """
    return vincular_con_pin(payload.codigo, payload.pin, usuario)
