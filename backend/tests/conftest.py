import os

# IMPORTANTE: estas variables deben quedar fijadas ANTES de importar cualquier
# módulo de `app`, porque `app.config.Settings` las lee al definirse la clase.
os.environ["USE_FAKE_DB"] = "true"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["PIN_PEPPER"] = "test-pepper"
os.environ["DEVICE_SHARED_SECRET"] = "test-device-secret"
os.environ["FIREBASE_PROJECT_ID"] = "test-project"
os.environ["CORS_ORIGINS"] = "http://localhost:5500"
os.environ["JWT_PIN_EXP_MINUTOS"] = "30"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.firebase_service import get_firestore_client  # noqa: E402


@pytest.fixture(autouse=True)
def _base_datos_limpia():
    get_firestore_client().reset()
    yield


@pytest.fixture
def db():
    return get_firestore_client()


@pytest.fixture
def client():
    return TestClient(app)
