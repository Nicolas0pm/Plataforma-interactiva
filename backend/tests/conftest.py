import os

# IMPORTANTE: estas variables deben quedar fijadas ANTES de importar cualquier
# módulo de `app`, porque `app.config.Settings` las lee al definirse la clase.
os.environ["USE_FAKE_DB"] = "true"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["JWT_SECRET"] = "test-secret"
os.environ["PIN_PEPPER"] = "test-pepper"
os.environ["DEVICE_SHARED_SECRET"] = "test-device-secret"
os.environ["CORS_ORIGINS"] = "http://localhost:5500"
os.environ["JWT_PIN_EXP_MINUTOS"] = "30"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from sqlalchemy.orm import Session  # noqa: E402

from app.db import Base, crear_tablas, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _base_datos_limpia():
    if engine.dialect.name == "postgresql":
        # Contra un PostgreSQL de verdad (TEST_DATABASE_URL), vaciar todo con una sola
        # sentencia es mucho más rápido que borrar y crear las tablas en cada prueba.
        crear_tablas()  # también aplica los cambios a tablas que ya existían
        tablas = ", ".join(t.name for t in Base.metadata.sorted_tables)
        with engine.begin() as conexion:
            conexion.exec_driver_sql(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE")
    else:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    """Sesión para preparar y revisar datos en las pruebas. Después de escribir, `db.commit()`
    (antes de llamar a la API); antes de leer lo que hizo la API, `db.commit()` también:
    así se descarta lo que la sesión tenía guardado en memoria."""
    with Session(engine) as sesion:
        yield sesion


@pytest.fixture
def client():
    return TestClient(app)
