"""Login propio de docentes y padres: correo + contraseña (ver app/services/auth_service.py)."""
import pytest

from app.config import get_settings
from app.models.tablas import Usuario
from app.services.auth_service import MAX_FALLOS, hash_password, verificar_password


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def produccion(monkeypatch):
    """Como en producción: sin login de desarrollo ni cuentas sin contraseña."""
    monkeypatch.setattr(get_settings(), "use_fake_db", False)


def _registrar(client, email="Marta@Escuela.co", password="clave-segura-1", rol="docente"):
    return client.post("/api/usuarios", json={
        "nombre": "Marta", "edad": 40, "rol": rol, "email": email, "password": password, "acepta_terminos": True,
    })


def _login(client, email="marta@escuela.co", password="clave-segura-1"):
    return client.post("/api/usuarios/login", json={"email": email, "password": password})


def test_la_contrasena_se_guarda_como_hash():
    guardado = hash_password("clave-segura-1")
    assert "clave-segura-1" not in guardado and guardado.startswith("scrypt$")
    assert verificar_password("clave-segura-1", guardado)
    assert not verificar_password("otra-clave-123", guardado)
    assert hash_password("clave-segura-1") != guardado  # cada hash lleva su propia sal


def test_registro_y_login_con_correo(client, db, produccion):
    perfil = _registrar(client)
    assert perfil.status_code == 201, perfil.text
    assert perfil.json()["email"] == "marta@escuela.co"  # se guarda en minúsculas
    assert "password" not in perfil.text and "scrypt" not in perfil.text

    sesion = _login(client, email="  MARTA@escuela.co ")
    assert sesion.status_code == 200
    assert sesion.json()["rol"] == "docente"
    yo = client.get("/api/usuarios/sesion", headers=_auth(sesion.json()["token"]))
    assert yo.status_code == 200 and yo.json()["id_usuario"] == perfil.json()["id_usuario"]
    assert db.get(Usuario, perfil.json()["id_usuario"]).password_hash.startswith("scrypt$")


def test_registro_exige_correo_contrasena_y_no_repite_correo(client, produccion):
    assert _registrar(client, password=None).status_code == 400
    assert _registrar(client, password="corta").status_code == 422
    assert _registrar(client, email="no-es-correo").status_code == 422
    assert _registrar(client).status_code == 201
    assert _registrar(client, email="MARTA@escuela.co").status_code == 409


def test_nadie_se_registra_como_admin(client, produccion):
    assert _registrar(client, rol="admin").status_code == 403


def test_credenciales_incorrectas_dan_el_mismo_error(client, produccion):
    _registrar(client)
    mala = _login(client, password="otra-clave-123")
    inexistente = _login(client, email="nadie@escuela.co")
    assert mala.status_code == inexistente.status_code == 401
    assert mala.json() == inexistente.json()


def test_el_correo_se_bloquea_tras_varios_fallos(client, produccion):
    _registrar(client)
    for _ in range(MAX_FALLOS):
        assert _login(client, password="otra-clave-123").status_code == 401
    assert _login(client).status_code == 429  # ni la contraseña correcta, por un rato


def test_cambiar_contrasena(client, produccion):
    _registrar(client)
    token = _login(client).json()["token"]
    cambio = {"actual": "equivocada-1", "nueva": "nueva-clave-2"}
    assert client.post("/api/usuarios/cambiar-password", json=cambio, headers=_auth(token)).status_code == 400
    cambio["actual"] = "clave-segura-1"
    assert client.post("/api/usuarios/cambiar-password", json=cambio, headers=_auth(token)).status_code == 200
    assert _login(client).status_code == 401
    assert _login(client, password="nueva-clave-2").status_code == 200


def test_una_cuenta_desactivada_pierde_la_sesion(client, db, produccion):
    perfil = _registrar(client).json()
    token = _login(client).json()["token"]
    db.get(Usuario, perfil["id_usuario"]).activo = False
    db.commit()
    assert client.get("/api/usuarios/sesion", headers=_auth(token)).status_code == 401
    assert _login(client).status_code == 401


def test_el_login_de_desarrollo_no_existe_en_produccion(client, db, produccion):
    perfil = _registrar(client).json()
    r = client.post("/api/usuarios/login-dev", json={"id_usuario": perfil["id_usuario"], "rol": "docente"})
    assert r.status_code == 403
