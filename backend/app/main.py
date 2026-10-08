import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import actividades, auditoria, feedback, lecciones, mundos, recompensas, tienda, usuarios, vinculacion
from app.services.auth_service import registrar_auditoria
from app.services.firebase_service import get_firestore_client

logger = logging.getLogger("plataforma-ingles-kids")
settings = get_settings()

app = FastAPI(
    title="API - Plataforma de Inglés con Recompensas Físicas",
    description="API en Python (FastAPI) que conecta el frontend con Firebase.",
    version="1.0.0",
)

@app.middleware("http")
async def sin_cache(request: Request, call_next):
    """Las respuestas de la API tienen datos personales y de progreso: que ningún
    navegador ni proxy las guarde."""
    respuesta = await call_next(request)
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


# Los resúmenes (camino completo del niño, panel del salón) son JSON de varios KB:
# comprimidos viajan mucho más rápido por redes móviles.
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.use_fake_db:
    # Modo de prueba: la base de datos en memoria arranca vacía; se carga el temario para
    # que las lecciones se puedan jugar de inmediato.
    from app.services.lecciones_service import sembrar_temario

    sembrar_temario(get_firestore_client())

app.include_router(usuarios.router)
app.include_router(actividades.router)
app.include_router(lecciones.router)
app.include_router(mundos.router)
app.include_router(tienda.router)
app.include_router(feedback.router)
app.include_router(recompensas.router)
app.include_router(vinculacion.router)
app.include_router(auditoria.router)


@app.exception_handler(Exception)
async def manejador_errores_no_controlados(request: Request, exc: Exception):
    """RNF-AUD-06 / RNF-FB-03: cualquier error no controlado se registra para
    análisis posterior, sin exponer detalles internos al cliente."""
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    try:
        registrar_auditoria(
            get_firestore_client(),
            tipo="error_sistema",
            actor=None,
            detalle={"ruta": str(request.url.path), "error": str(exc)},
        )
    except Exception:
        logger.exception("No se pudo registrar el error en auditoría")
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


@app.get("/")
def salud():
    from app.services.correo_service import proveedor

    # "correo" dice cómo salen los correos (brevo, smtp o log = no se envían). Sin secretos.
    return {"status": "ok", "servicio": "plataforma-ingles-kids-api", "correo": proveedor()}
