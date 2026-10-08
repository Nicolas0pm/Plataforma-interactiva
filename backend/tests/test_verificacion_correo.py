"""Confirmación del correo de docentes y padres (enlace de Firebase Authentication,
ver `auth_service.sincronizar_verificacion`)."""
from app.services.auth_service import sincronizar_verificacion


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _registrar(client, email="marta@escuela.co"):
    perfil = client.post("/api/usuarios", json={
        "nombre": "Marta", "edad": 40, "rol": "docente", "acudientes_ids": [], "docente_id": None,
        "email": email, "acepta_terminos": True,
    }).json()
    token = client.post("/api/usuarios/login-dev", json={"id_usuario": perfil["id_usuario"], "rol": "docente"}).json()["token"]
    return perfil, token


def test_sin_confirmar_el_correo_solo_ve_su_sesion(client):
    perfil, token = _registrar(client)
    assert perfil["email_verificado"] is False
    # Ve su sesión (así el frontend sabe que falta confirmar), pero nada más.
    sesion = client.get("/api/usuarios/sesion", headers=_auth(token))
    assert sesion.status_code == 200 and sesion.json()["email_verificado"] is False
    r = client.get("/api/mundos", headers=_auth(token))
    assert r.status_code == 403 and "confirma tu correo" in r.json()["detail"]


def test_al_confirmar_en_firebase_el_perfil_queda_verificado(client, db):
    perfil, token = _registrar(client)
    datos = db.collection("usuarios").document(perfil["id_usuario"]).get().to_dict()

    # Token de Firebase todavía sin confirmar: sigue bloqueado y no se escribe nada.
    assert sincronizar_verificacion(db, perfil["id_usuario"], datos, False) is False
    assert db.collection("usuarios").document(perfil["id_usuario"]).get().to_dict()["email_verificado"] is False

    # Abrió el enlace: el siguiente token trae email_verified y se copia al perfil.
    assert sincronizar_verificacion(db, perfil["id_usuario"], datos, True) is True
    assert db.collection("usuarios").document(perfil["id_usuario"]).get().to_dict()["email_verificado"] is True
    assert client.get("/api/mundos", headers=_auth(token)).status_code == 200


def test_cuentas_de_prueba_sin_correo_y_perfiles_antiguos_no_piden_confirmar(client, db):
    perfil, token = _registrar(client, email=None)
    assert perfil["email_verificado"] is True
    assert client.get("/api/mundos", headers=_auth(token)).status_code == 200

    # Perfil creado antes de existir la verificación (sin el campo): sigue entrando.
    db.collection("usuarios").document("viejo").set({"nombre": "Antiguo", "rol": "padre", "email": "a@b.co", "activo": True})
    token_viejo = client.post("/api/usuarios/login-dev", json={"id_usuario": "viejo", "rol": "padre"}).json()["token"]
    assert client.get("/api/usuarios/padre/viejo/hijos", headers=_auth(token_viejo)).status_code == 200
