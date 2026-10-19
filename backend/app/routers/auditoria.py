import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import RutaConTransaccion, get_db
from app.models.tablas import Auditoria
from app.services.auth_service import require_role

router = APIRouter(prefix="/api/auditoria", tags=["auditoria"], route_class=RutaConTransaccion)

CAMPOS = ["fecha", "tipo", "actor", "detalle"]


@router.get("/exportar.csv")
def exportar_csv(usuario: dict = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """RNF-AUD-07: exportación de los reportes de auditoría en un formato estándar.

    Los registros de esta tabla se crean únicamente desde la API (ver
    `auth_service.registrar_auditoria`); nunca se editan ni se borran (RNF-AUD-08).
    """
    registros = db.scalars(select(Auditoria).order_by(Auditoria.fecha.desc(), Auditoria.id.desc()))

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CAMPOS)
    writer.writeheader()
    for registro in registros:
        writer.writerow(
            {"fecha": registro.fecha, "tipo": registro.tipo, "actor": registro.actor, "detalle": registro.detalle}
        )
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=auditoria.csv"},
    )
