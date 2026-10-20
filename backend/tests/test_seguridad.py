"""Controles contra el abuso: PIN fáciles de adivinar, límite de peticiones por IP y
tamaño máximo de las peticiones; y los comentarios del docente (RF07)."""
import pytest

from app.models.tablas import Usuario
from app.services import limites
from app.services.auth_service import hash_pin
from utilidades import auth, crear_adulto, crear_coordinador, crear_nino, login_nino


@pytest.mark.parametrize("pin", ["0000", "1111", "1234", "6789", "9876", "3210", "1212"])
def test_no_se_asignan_pin_faciles(client, pin):
    _, token_coord = crear_coordinador()
    r = client.post("/api/coordinador/estudiantes", headers=auth(token_coord), json={
        "nombre": "Leo", "edad": 7, "pin": pin, "autoriza_datos_menor": True,
    })
    assert r.status_code == 422 and "fácil" in r.text
    nino = crear_nino(client, token_coord)
    r = client.post(f"/api/coordinador/estudiantes/{nino['id_usuario']}/pin", headers=auth(token_coord), json={"pin": pin})
    assert r.status_code == 422


def test_un_nino_con_pin_facil_anterior_puede_seguir_entrando(client, db):
    _, token_coord = crear_coordinador()
    nino = crear_nino(client, token_coord)
    db.get(Usuario, nino["id_usuario"]).pin_hash = hash_pin("1234")
    db.commit()
    login_nino(client, nino, pin="1234")


def test_limite_de_intentos_de_login_por_ip(client, monkeypatch):
    monkeypatch.setattr(limites._settings, "limite_login_por_minuto", 3)
    datos = {"usuario": "nadie", "password": "clave-incorrecta"}
    for _ in range(3):
        assert client.post("/api/usuarios/login", json=datos).status_code == 401
    bloqueado = client.post("/api/usuarios/login", json=datos)
    assert bloqueado.status_code == 429 and int(bloqueado.headers["Retry-After"]) > 0
    # Otra IP (la que agrega el proxy al final de X-Forwarded-For) no está bloqueada,
    # aunque el cliente intente hacerse pasar por la IP bloqueada al principio de la lista.
    otra = client.post("/api/usuarios/login", json=datos, headers={"X-Forwarded-For": "testclient, 10.0.0.7"})
    assert otra.status_code == 401
    # El resto de la API tiene su propio límite, más alto.
    assert client.get("/api/usuarios/sesion").status_code == 401


def test_limite_general_de_la_api(client, monkeypatch):
    monkeypatch.setattr(limites._settings, "limite_api_por_minuto", 5)
    codigos = [client.get("/api/usuarios/sesion").status_code for _ in range(6)]
    assert codigos == [401] * 5 + [429]


def test_la_ventana_del_limite_se_renueva():
    limite = limites.LimitePorIP()
    assert all(limite.permitir("1.2.3.4", "login", 2, ahora=t) == 0 for t in (0, 1))
    assert limite.permitir("1.2.3.4", "login", 2, ahora=30) > 0
    assert limite.permitir("1.2.3.4", "login", 2, ahora=61) == 0


def test_peticiones_demasiado_grandes(client):
    _, token_coord = crear_coordinador()
    profe, token_profe = crear_adulto(client, token_coord, "docente", "mgarcia")
    nino = crear_nino(client, token_coord, docente_id=profe["id_usuario"])
    enorme = {"id_estudiante": nino["id_usuario"], "comentario": "a" * 1_100_000}
    assert client.post("/api/feedback", headers=auth(token_profe), json=enorme).status_code == 413

    # Sin Content-Length (envío por partes) también se corta
    def partes():
        for _ in range(12):
            yield b"a" * 100_000

    r = client.post("/api/feedback", headers={**auth(token_profe), "Content-Type": "application/json"}, content=partes())
    assert r.status_code == 413
    # Una petición normal sigue funcionando
    normal = {"id_estudiante": nino["id_usuario"], "comentario": "Muy bien"}
    assert client.post("/api/feedback", headers=auth(token_profe), json=normal).status_code == 201


def test_comentarios_del_docente_para_los_padres(client):
    _, token_coord = crear_coordinador()
    profe, token_profe = crear_adulto(client, token_coord, "docente", "mgarcia")
    otro_profe, token_otro = crear_adulto(client, token_coord, "docente", "jrestrepo")
    padre, token_padre = crear_adulto(client, token_coord, "padre", "cperez")
    ajeno, token_ajeno = crear_adulto(client, token_coord, "padre", "lgomez")
    nino = crear_nino(client, token_coord, docente_id=profe["id_usuario"], acudientes_ids=[padre["id_usuario"]])

    visible = {"id_estudiante": nino["id_usuario"], "comentario": "Practiquen los colores en casa."}
    privado = {**visible, "comentario": "Nota interna", "visible_para_padres": False}
    assert client.post("/api/feedback", headers=auth(token_profe), json=visible).status_code == 201
    assert client.post("/api/feedback", headers=auth(token_profe), json=privado).status_code == 201
    # Un docente de otro salón y un padre no pueden escribir comentarios
    assert client.post("/api/feedback", headers=auth(token_otro), json=visible).status_code == 403
    assert client.post("/api/feedback", headers=auth(token_padre), json=visible).status_code == 403

    url = f"/api/feedback/estudiante/{nino['id_usuario']}"
    assert len(client.get(url, headers=auth(token_profe)).json()) == 2
    del_padre = client.get(url, headers=auth(token_padre)).json()
    assert [c["comentario"] for c in del_padre] == ["Practiquen los colores en casa."]
    assert client.get(url, headers=auth(token_ajeno)).status_code == 403
