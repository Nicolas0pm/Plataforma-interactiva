"""
Máquinas de premios (ver `maquinas_service.py`).

Para la máquina (ESP32):
- `POST /api/maquinas/registro`: se presenta con su MAC y su clave; devuelve su `device_id`.
- `GET /api/maquinas/yo`: si tiene salón y si el docente le pidió otro WiFi.
- `POST /api/maquinas/yo/wifi`: avisa si pudo conectarse a la red nueva.

Para el docente:
- `GET /api/maquinas/disponibles`: máquinas registradas sin salón, para elegir la suya.
- `POST /api/maquinas/vincular`, `DELETE /api/maquinas`: asignar o soltar la máquina del salón.
- `GET /api/maquinas/estado`: si está en línea, su red y el resultado del último cambio de WiFi.
- `POST /api/maquinas/wifi`: pedirle a la máquina que se conecte a otra red.
- `POST /api/maquinas/probar`: un premio de prueba.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import RutaConTransaccion, get_db
from app.models.tablas import Maquina, Usuario
from app.services import maquinas_service
from app.services.auth_service import require_role

router = APIRouter(prefix="/api/maquinas", tags=["maquinas"], route_class=RutaConTransaccion)


class Registro(BaseModel):
    mac: str = Field(max_length=17)
    clave: str = Field(min_length=16, max_length=100)


class ResultadoWifi(BaseModel):
    ok: bool
    red: str = Field(max_length=64)
    detalle: str | None = Field(default=None, max_length=200)


class Vincular(BaseModel):
    device_id: str = Field(max_length=60)


class Wifi(BaseModel):
    ssid: str = Field(min_length=1, max_length=32)
    password: str = Field(default="", max_length=64)


def _maquina(db: Session, x_device_id: str | None, x_device_token: str | None) -> Maquina:
    if not x_device_id or not x_device_token:
        raise HTTPException(401, "Faltan las credenciales de la máquina")
    return maquinas_service.autenticar(db, x_device_id, x_device_token, None)


def _docente(usuario: dict, db: Session) -> Usuario:
    docente = db.get(Usuario, usuario["id_usuario"])
    if docente is None:
        raise HTTPException(404, "Docente no encontrado")
    return docente


# ----------------------------------------------------------------- máquina


@router.post("/registro")
def registro(payload: Registro, db: Session = Depends(get_db)):
    return maquinas_service.registrar(db, payload.mac, payload.clave)


@router.get("/yo")
def yo(
    red: str | None = None,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return maquinas_service.para_la_maquina(_maquina(db, x_device_id, x_device_token), red)


@router.post("/yo/wifi")
def yo_wifi(
    payload: ResultadoWifi,
    x_device_id: str | None = Header(default=None),
    x_device_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    maquinas_service.resultado_wifi(db, _maquina(db, x_device_id, x_device_token), payload.ok, payload.red, payload.detalle)
    return {"ok": True}


# ----------------------------------------------------------------- docente


@router.get("/disponibles")
def disponibles(usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    return maquinas_service.disponibles(db)


@router.post("/vincular")
def vincular(payload: Vincular, usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    return maquinas_service.vincular(db, _docente(usuario, db), payload.device_id)


@router.get("/estado")
def estado(usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    return maquinas_service.estado(db, _docente(usuario, db))


@router.post("/wifi")
def wifi(payload: Wifi, usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    return maquinas_service.cambiar_wifi(db, _docente(usuario, db), payload.ssid, payload.password)


@router.post("/probar")
def probar(usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    return maquinas_service.probar(db, _docente(usuario, db))


@router.delete("")
def desvincular(usuario: dict = Depends(require_role("docente")), db: Session = Depends(get_db)):
    maquinas_service.desvincular(db, _docente(usuario, db))
    return {"ok": True}
