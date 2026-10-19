"""
Conexión a la base de datos relacional (PostgreSQL en Neon; SQLite en memoria en modo
de prueba) con SQLAlchemy.

- `DATABASE_URL` (ver `app/config.py`) dice a qué base conectarse.
- Cada petición HTTP recibe su propia sesión con `Depends(get_db)`: si la petición
  termina bien (o con un error esperado, un `HTTPException`), se guardan sus cambios
  ANTES de enviar la respuesta (`RutaConTransaccion`); si falla por un error inesperado,
  se deshacen.
- Las tablas se crean solas al arrancar (`crear_tablas`): solo agrega las que falten,
  nunca borra datos.
"""
from collections.abc import Callable, Iterator
from datetime import datetime, timezone

from fastapi import HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.routing import APIRoute
from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from app.config import get_settings

_settings = get_settings()


class Base(DeclarativeBase):
    pass


class FechaUTC(TypeDecorator):
    """Fecha con zona horaria que SIEMPRE vuelve en UTC (SQLite las devuelve sin zona)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def _crear_engine():
    url = _settings.database_url
    if not url:
        raise RuntimeError("Falta DATABASE_URL (la cadena de conexión de Neon). Ver backend/.env.example")
    if url.startswith("sqlite"):
        # Modo de prueba: una sola conexión compartida para que la base en memoria
        # sea la misma en toda la API (y en los tests).
        motor = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(motor, "connect")
        def _activar_llaves_foraneas(conexion, _):
            # SQLite no revisa las llaves foráneas si no se le pide (PostgreSQL siempre).
            conexion.execute("PRAGMA foreign_keys=ON")

        return motor
    # Neon cierra las conexiones inactivas (la base "duerme"): pre_ping las revisa antes
    # de usarlas y pool_recycle las renueva cada 5 minutos.
    return create_engine(url, pool_pre_ping=True, pool_recycle=300, pool_size=5, max_overflow=5)


engine = _crear_engine()
SesionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición.

    Un `HTTPException` es una respuesta esperada (PIN incorrecto, sin permiso...), y lo
    que se alcanzó a escribir antes también se guarda: por ejemplo, el contador de
    intentos fallidos de PIN o el registro de auditoría del login fallido."""
    db = SesionLocal()
    request.state.db = db
    try:
        yield db
        db.commit()
    except HTTPException:
        db.commit()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class RutaConTransaccion(APIRoute):
    """FastAPI cierra las dependencias con `yield` DESPUÉS de enviar la respuesta: si el
    commit quedara solo en `get_db`, el frontend podría recibir "listo" y pedir los datos
    antes de que estén guardados (o no enterarse si el guardado falla). Esta ruta guarda
    los cambios justo antes de responder; si el guardado falla, la respuesta es un 500."""

    def get_route_handler(self) -> Callable:
        manejador = super().get_route_handler()

        async def con_commit(request: Request) -> Response:
            respuesta = await manejador(request)
            db = getattr(request.state, "db", None)
            if db is not None:
                await run_in_threadpool(db.commit)
            return respuesta

        return con_commit


# Cambios a tablas que ya existían en PostgreSQL (`create_all` solo crea tablas nuevas).
# Cada sentencia se puede repetir sin efecto; se agregan al final, nunca se editan.
_CAMBIOS_DE_ESQUEMA = [
    # Login propio en vez de Firebase Authentication (sin confirmación del correo).
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_hash VARCHAR(200)",
    "ALTER TABLE usuarios DROP COLUMN IF EXISTS auth_uid",
    "ALTER TABLE usuarios DROP COLUMN IF EXISTS email_verificado",
    "ALTER TABLE usuarios DROP COLUMN IF EXISTS email_verificado_en",
    "UPDATE usuarios SET email = lower(trim(email)) WHERE email <> lower(trim(email))",
    "DROP INDEX IF EXISTS ix_usuarios_email",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_email ON usuarios (email)",
    "DROP TABLE IF EXISTS intentos_pin",
    # El coordinador crea las cuentas; los adultos entran con usuario y contraseña.
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS usuario VARCHAR(40)",
    "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS debe_cambiar_password BOOLEAN NOT NULL DEFAULT false",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_usuario ON usuarios (usuario)",
]


def crear_tablas() -> None:
    import app.models.tablas  # noqa: F401 - registra las tablas en Base.metadata

    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conexion:
            for sentencia in _CAMBIOS_DE_ESQUEMA:
                conexion.exec_driver_sql(sentencia)
