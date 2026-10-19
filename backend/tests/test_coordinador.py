"""El coordinador crea las cuentas y asigna a cada niño su docente y sus acudientes
(app/routers/coordinador.py)."""
import pytest
from fastapi import HTTPException

from app.models.tablas import Usuario
from app.services.auth_service import MAX_FALLOS
from app.services.estudiantes_service import verificar_codigo_y_pin
from utilidades import auth, crear_adulto, crear_coordinador, crear_nino, login_nino


def test_solo_el_coordinador_usa_su_panel(client):
    _, token_coord = crear_coordinador()
    _, token_docente = crear_adulto(client, token_coord, "docente", "mgarcia")
    assert client.get("/api/coordinador/usuarios").status_code == 401
    assert client.get("/api/coordinador/usuarios", headers=auth(token_docente)).status_code == 403
    assert client.post("/api/coordinador/adultos", headers=auth(token_docente),
                       json={"nombre": "X", "rol": "docente", "usuario": "otro"}).status_code == 403
    assert client.get("/api/coordinador/usuarios", headers=auth(token_coord)).status_code == 200


def test_nadie_puede_registrarse_solo(client):
    assert client.post("/api/usuarios", json={"nombre": "X", "edad": 30, "rol": "docente"}).status_code in (404, 405)


def test_crear_profesor_padre_y_nino_asignados(client, db):
    _, token_coord = crear_coordinador()
    docente, _ = crear_adulto(client, token_coord, "docente", "mgarcia", "Marta")
    padre, token_padre = crear_adulto(client, token_coord, "padre", "cperez", "Carlos")
    nino = crear_nino(client, token_coord, docente_id=docente["id_usuario"], acudientes_ids=[padre["id_usuario"]])
    assert nino["docente_id"] == docente["id_usuario"] and nino["acudientes_ids"] == [padre["id_usuario"]]
    assert len(nino["codigo_acceso"]) == 6 and "pin_hash" not in nino

    # Queda la evidencia de la autorización de datos (Ley 1581): quién la dio y bajo qué versión.
    guardado = db.get(Usuario, nino["id_usuario"])
    assert guardado.autorizacion_rol == "admin" and guardado.autorizacion_version == "1.1"

    hijos = client.get(f"/api/usuarios/padre/{padre['id_usuario']}/hijos", headers=auth(token_padre)).json()
    assert [h["id_usuario"] for h in hijos] == [nino["id_usuario"]]

    lista = client.get("/api/coordinador/usuarios", headers=auth(token_coord)).json()
    assert [d["usuario"] for d in lista["docentes"]] == ["mgarcia"] and lista["docentes"][0]["estudiantes"] == 1
    assert lista["padres"][0]["hijos"] == 1 and len(lista["estudiantes"]) == 1
    assert "pin_hash" not in str(lista) and "password_hash" not in str(lista)


def test_registrar_nino_exige_autorizacion_y_docente_real(client):
    _, token_coord = crear_coordinador()
    padre, _ = crear_adulto(client, token_coord, "padre", "cperez")
    base = {"nombre": "Leo", "edad": 7, "pin": "1234", "autoriza_datos_menor": True}
    assert client.post("/api/coordinador/estudiantes", headers=auth(token_coord),
                       json={**base, "autoriza_datos_menor": False}).status_code == 400
    assert client.post("/api/coordinador/estudiantes", headers=auth(token_coord),
                       json={**base, "docente_id": padre["id_usuario"]}).status_code == 400  # no es docente
    for pin in ("12345", "12a4", "123"):
        assert client.post("/api/coordinador/estudiantes", headers=auth(token_coord),
                           json={**base, "pin": pin}).status_code == 422


def test_usuarios_unicos_y_validos(client):
    _, token_coord = crear_coordinador()
    crear_adulto(client, token_coord, "docente", "mgarcia")
    repetido = client.post("/api/coordinador/adultos", headers=auth(token_coord),
                           json={"nombre": "Otra", "rol": "padre", "usuario": "mgarcia"})
    assert repetido.status_code == 409
    for malo in ("ab", "Con Espacio", "MAYUS", "x" * 41):
        assert client.post("/api/coordinador/adultos", headers=auth(token_coord),
                           json={"nombre": "X", "rol": "docente", "usuario": malo}).status_code == 422


def test_reasignar_nino_y_heredar_la_maquina_del_salon(client):
    _, token_coord = crear_coordinador()
    profe1, _ = crear_adulto(client, token_coord, "docente", "profe1")
    profe2, token_profe2 = crear_adulto(client, token_coord, "docente", "profe2")
    client.put(f"/api/usuarios/docente/{profe2['id_usuario']}/dispensador", json={"device_id": "aula-7"},
               headers=auth(token_profe2))
    padre1, _ = crear_adulto(client, token_coord, "padre", "padre1")
    padre2, _ = crear_adulto(client, token_coord, "padre", "padre2")
    nino = crear_nino(client, token_coord, docente_id=profe1["id_usuario"])

    url = f"/api/coordinador/estudiantes/{nino['id_usuario']}"
    r = client.patch(url, headers=auth(token_coord), json={
        "docente_id": profe2["id_usuario"], "acudientes_ids": [padre1["id_usuario"], padre2["id_usuario"]]})
    assert r.status_code == 200
    assert r.json()["docente_id"] == profe2["id_usuario"] and r.json()["device_id"] == "aula-7"
    assert r.json()["acudientes_ids"] == [padre1["id_usuario"], padre2["id_usuario"]]

    # Lo que no se envía no cambia; quitar el docente lo deja sin salón ni máquina.
    r = client.patch(url, headers=auth(token_coord), json={"quitar_docente": True})
    assert r.json()["docente_id"] is None and r.json()["device_id"] is None
    assert len(r.json()["acudientes_ids"]) == 2


def test_restablecer_password_y_pin(client):
    _, token_coord = crear_coordinador()
    profe, _ = crear_adulto(client, token_coord, "docente", "mgarcia")
    nino = crear_nino(client, token_coord)

    nueva = client.post(f"/api/coordinador/usuarios/{profe['id_usuario']}/restablecer-password",
                        headers=auth(token_coord)).json()["password_temporal"]
    sesion = client.post("/api/usuarios/login", json={"usuario": "mgarcia", "password": nueva}).json()
    assert sesion["debe_cambiar_password"] is True

    assert client.post(f"/api/coordinador/estudiantes/{nino['id_usuario']}/pin", headers=auth(token_coord),
                       json={"pin": "4321"}).status_code == 200
    login_nino(client, nino, pin="4321")


def test_desactivar_cierra_la_sesion_y_no_deja_entrar(client):
    id_coord, token_coord = crear_coordinador()
    profe, token_profe = crear_adulto(client, token_coord, "docente", "mgarcia")
    nino = crear_nino(client, token_coord)
    token_nino = login_nino(client, nino)
    for cuenta in (profe, nino):
        assert client.patch(f"/api/coordinador/usuarios/{cuenta['id_usuario']}", headers=auth(token_coord),
                            json={"activo": False}).status_code == 200
    assert client.get("/api/usuarios/sesion", headers=auth(token_profe)).status_code == 401
    assert client.get("/api/lecciones/jugar", headers=auth(token_nino)).status_code == 401
    assert client.post("/api/usuarios/login", json={"usuario": "mgarcia", "password": "clave-segura-1"}).status_code == 401
    assert client.post("/api/usuarios/login-pin", json={"codigo": nino["codigo_acceso"], "pin": "1234"}).status_code == 401
    # Nadie se desactiva a sí mismo (se quedaría sin coordinador).
    assert client.patch(f"/api/coordinador/usuarios/{id_coord}", headers=auth(token_coord),
                        json={"activo": False}).status_code == 400


def test_codigo_se_bloquea_tras_varios_fallos_de_pin(client, db):
    _, token_coord = crear_coordinador()
    nino = crear_nino(client, token_coord)
    for _ in range(MAX_FALLOS):
        with pytest.raises(HTTPException):
            verificar_codigo_y_pin(db, nino["codigo_acceso"], "0000")
    # Bloqueado: ni siquiera el PIN correcto funciona hasta que pase el tiempo
    with pytest.raises(HTTPException) as exc:
        verificar_codigo_y_pin(db, nino["codigo_acceso"], "1234")
    assert exc.value.status_code == 429
