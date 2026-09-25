import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.services.auth_service import require_role
from app.services.firebase_service import get_firestore_client

router = APIRouter(prefix="/api/auditoria", tags=["auditoria"])

CAMPOS = ["fecha", "tipo", "actor", "detalle"]


@router.get("/exportar.csv")
def exportar_csv(usuario: dict = Depends(require_role("admin"))):
    """RNF-AUD-07: exportación de los reportes de auditoría en un formato estándar.

    Los registros de esta colección se crean únicamente desde la API (ver
    `auth_service.registrar_auditoria`); nunca se editan ni se borran desde
    aquí ni desde el cliente (RNF-AUD-08, ver también `firebase/firestore.rules`).
    """
    db = get_firestore_client()
    documentos = db.collection("auditoria").order_by("fecha", direction="DESCENDING").stream()

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CAMPOS)
    writer.writeheader()
    for doc in documentos:
        data = doc.to_dict()
        writer.writerow(
            {
                "fecha": data.get("fecha"),
                "tipo": data.get("tipo"),
                "actor": data.get("actor"),
                "detalle": data.get("detalle"),
            }
        )
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=auditoria.csv"},
    )
