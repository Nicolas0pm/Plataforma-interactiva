"""Confirmación del correo de docentes y padres con un código (app/services/verificacion_service.py)."""
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.services import correo_service, verificacion_service


@pytest.fixture
def correos(monkeypatch):
    """Captura los correos en vez de enviarlos."""
    enviados = []
    monkeypatch.setattr(correo_service, "enviar_correo", lambda destino, asunto, texto, html: enviados.append((destino, texto)))
    monkeypatch.setattr(verificacion_service, "enviar_correo", lambda destino, asunto, texto, html: enviados.append((destino, texto)))
    return enviados


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _codigo(correos):
    return re.search(r"\b(\d{6})\b", correos[-1][1]).group(1)


def _registrar(client, email="marta@escuela.co"):
    perfil = client.post("/api/usuarios", json={
        "nombre": "Marta", "edad": 40, "rol": "docente", "acudientes_ids": [], "docente_id": None,
        "email": email, "acepta_terminos": True,
    }).json()
    token = client.post("/api/usuarios/login-dev", json={"id_usuario": perfil["id_usuario"], "rol": "docente"}).json()["token"]
    return perfil, token


def test_registro_envia_codigo_y_bloquea_hasta_confirmar(client, db, correos):
    perfil, token = _registrar(client)
    assert perfil["email_verificado"] is False
    assert correos and correos[0][0] == "marta@escuela.co"
    guardado = db.collection("usuarios").document(perfil["id_usuario"]).get().to_dict()
    assert _codigo(correos) not in str(guardado)  # el código se guarda solo como hash

    # Sin confirmar: ve su sesión (para saber que falta el código) pero nada más.
    assert client.get("/api/usuarios/sesion", headers=_auth(token)).json()["email_verificado"] is False
    assert client.get("/api/mundos", headers=_auth(token)).status_code == 403

    malo = "000000" if _codigo(correos) != "000000" else "111111"
    r = client.post("/api/usuarios/verificacion/confirmar", json={"codigo": malo}, headers=_auth(token))
    assert r.status_code == 400 and "4 intentos" in r.json()["detail"]

    r = client.post("/api/usuarios/verificacion/confirmar", json={"codigo": _codigo(correos)}, headers=_auth(token))
    assert r.status_code == 200
    assert client.get("/api/usuarios/sesion", headers=_auth(token)).json()["email_verificado"] is True
    assert client.get("/api/mundos", headers=_auth(token)).status_code == 200


def test_reenviar_espera_y_el_codigo_viejo_deja_de_servir(client, db, correos):
    perfil, token = _registrar(client)
    viejo = _codigo(correos)
    assert client.post("/api/usuarios/verificacion/reenviar", headers=_auth(token)).status_code == 429

    # Pasado el minuto de espera sí se puede pedir otro.
    ref = db.collection("usuarios").document(perfil["id_usuario"])
    pendiente = ref.get().to_dict()["verificacion_email"]
    pendiente["enviado_en"] = datetime.now(timezone.utc) - timedelta(minutes=2)
    ref.update({"verificacion_email": pendiente})
    assert client.post("/api/usuarios/verificacion/reenviar", headers=_auth(token)).status_code == 200
    nuevo = _codigo(correos)
    if viejo != nuevo:
        r = client.post("/api/usuarios/verificacion/confirmar", json={"codigo": viejo}, headers=_auth(token))
        assert r.status_code == 400
    assert client.post("/api/usuarios/verificacion/confirmar", json={"codigo": nuevo}, headers=_auth(token)).status_code == 200


def test_codigo_vencido_o_con_demasiados_intentos(client, db, correos):
    perfil, token = _registrar(client)
    codigo = _codigo(correos)
    malo = "000000" if codigo != "000000" else "111111"
    for _ in range(verificacion_service.MAX_INTENTOS):
        client.post("/api/usuarios/verificacion/confirmar", json={"codigo": malo}, headers=_auth(token))
    r = client.post("/api/usuarios/verificacion/confirmar", json={"codigo": codigo}, headers=_auth(token))
    assert r.status_code == 400 and "Demasiados intentos" in r.json()["detail"]

    ref = db.collection("usuarios").document(perfil["id_usuario"])
    pendiente = ref.get().to_dict()["verificacion_email"]
    pendiente.update(intentos=0, expira=datetime.now(timezone.utc) - timedelta(minutes=1))
    ref.update({"verificacion_email": pendiente})
    r = client.post("/api/usuarios/verificacion/confirmar", json={"codigo": codigo}, headers=_auth(token))
    assert r.status_code == 400 and "venció" in r.json()["detail"]


def test_cuentas_de_prueba_sin_correo_y_perfiles_antiguos_no_piden_codigo(client, db, correos):
    perfil, token = _registrar(client, email=None)
    assert perfil["email_verificado"] is True and not correos
    assert client.get("/api/mundos", headers=_auth(token)).status_code == 200

    # Perfil creado antes de existir la verificación (sin el campo): sigue entrando.
    viejo = db.collection("usuarios").document("viejo")
    viejo.set({"nombre": "Antiguo", "rol": "padre", "email": "a@b.co", "activo": True})
    token_viejo = client.post("/api/usuarios/login-dev", json={"id_usuario": "viejo", "rol": "padre"}).json()["token"]
    assert client.get("/api/usuarios/padre/viejo/hijos", headers=_auth(token_viejo)).status_code == 200


def test_si_el_correo_no_sale_avisa_y_deja_reintentar(client, monkeypatch):
    def falla(*_):
        raise correo_service.CorreoNoEnviado("remitente no verificado")

    monkeypatch.setattr(verificacion_service, "enviar_correo", falla)
    perfil, token = _registrar(client)
    assert perfil["email_verificado"] is False and "No pudimos enviar" in perfil["aviso_correo"]
    # Sin esperar el minuto: el intento fallido no cuenta.
    r = client.post("/api/usuarios/verificacion/reenviar", headers=_auth(token))
    assert r.status_code == 502
