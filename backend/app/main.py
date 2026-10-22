import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import SesionLocal, crear_tablas
from app.routers import actividades, auditoria, coordinador, examenes, feedback, lecciones, mundos, recompensas, temario, tienda, usuarios
from app.services.auth_service import registrar_auditoria
from app.services.lecciones_service import sembrar_temario, temario_cargado
from app.services.limites import TamanoMaximo, limitar_por_ip

logger = logging.getLogger("plataforma-ingles-kids")
settings = get_settings()

app = FastAPI(
    title="API - Plataforma de Inglés con Recompensas Físicas",
    description="API en Python (FastAPI) que conecta el frontend con la base de datos PostgreSQL.",
    version="1.0.0",
)

@app.middleware("http")
async def sin_cache(request: Request, call_next):
    """Las respuestas de la API tienen datos personales y de progreso: que ningún
    navegador ni proxy las guarde."""
    respuesta = await call_next(request)
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


# Límite de peticiones por IP (429) y tamaño máximo del cuerpo (413). Se registran antes
# que CORS para que esas respuestas también lleven sus encabezados.
app.middleware("http")(limitar_por_ip)
app.add_middleware(TamanoMaximo, maximo=settings.max_cuerpo_bytes)

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

# Crea las tablas que falten y, si la base está recién creada (o es la de prueba, que
# arranca vacía), carga el temario para que las lecciones se puedan jugar de inmediato.
# Para actualizar el temario después de cambiar app/curriculo.py: scripts/verificar_conexion.py --sembrar
crear_tablas()
with SesionLocal.begin() as _db:
    if not temario_cargado(_db):
        sembrar_temario(_db)
    if settings.use_fake_db:
        # Modo de prueba (base en memoria): un coordinador para poder entrar y crear cuentas.
        from app.services.auth_service import crear_coordinador_de_prueba

        crear_coordinador_de_prueba(_db)

app.include_router(usuarios.router)
app.include_router(actividades.router)
app.include_router(lecciones.router)
app.include_router(examenes.router)
app.include_router(mundos.router)
app.include_router(temario.router)
app.include_router(tienda.router)
app.include_router(feedback.router)
app.include_router(recompensas.router)
app.include_router(coordinador.router)
app.include_router(auditoria.router)


@app.exception_handler(Exception)
async def manejador_errores_no_controlados(request: Request, exc: Exception):
    """RNF-AUD-06 / RNF-FB-03: cualquier error no controlado se registra para
    análisis posterior, sin exponer detalles internos al cliente."""
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    try:
        with SesionLocal.begin() as db:
            registrar_auditoria(
                db, tipo="error_sistema", actor=None,
                detalle={"ruta": str(request.url.path), "error": str(exc)[:500]},
            )
    except Exception:
        logger.exception("No se pudo registrar el error en auditoría")
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


@app.get("/")
def salud():
    return {"status": "ok", "servicio": "plataforma-ingles-kids-api"}
