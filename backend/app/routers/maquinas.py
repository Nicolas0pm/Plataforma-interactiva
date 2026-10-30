"""
Máquina de premios del salón, desde el panel del docente (ver `maquinas_service.py`):

- `POST /api/maquinas/vincular`: crea la máquina del salón y devuelve su `device_id` y su
  token. La página se los pasa a la ESP32 por USB; el token no se vuelve a mostrar.
- `GET /api/maquinas/estado`: si hay máquina, si está en línea y cuándo se conectó por última vez.
- `POST /api/maquinas/probar`: pone un premio de prueba en la cola para comprobar el motor.
- `DELETE /api/maquinas`: desvincula la máquina (su token deja de servir).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import RutaConTransaccion, get_db
from app.models.tablas import Usuario
from app.services import maquinas_service
from app.services.auth_service import require_role

router = APIRouter(prefix="/api/maquinas", tags=["maquinas"], route_class=RutaConTransaccion)


def _docente(usuario: dict, db: Session) -> Usuario:
    docente = db.get(Usuario, usuario["id_usuario"])
    if docente is None:
        raise HTTPException(404, "Docente no encontrado")
    return docente


@router.post("/vincular", status_code=201)
def vincular(usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    return maquinas_service.vincular(db, _docente(usuario, db))


@router.get("/estado")
def estado(usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    return maquinas_service.estado(db, _docente(usuario, db))


@router.post("/probar")
def probar(usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    return maquinas_service.probar(db, _docente(usuario, db))


@router.delete("")
def desvincular(usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    maquinas_service.desvincular(db, _docente(usuario, db))
    return {"ok": True}
