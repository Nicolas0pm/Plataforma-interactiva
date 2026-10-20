"""
Pruebas de integración de punta a punta sobre la API (con USE_FAKE_DB=true,
ver conftest.py), cubriendo el flujo real: el coordinador crea las cuentas, autenticación
por rol, RF03/RF04/RF05 (actividad -> progreso -> recompensa), RF07/RF11 (padres) y las
garantías de la base de datos (transacciones, largos de columna).
"""
from fastapi.testclient import TestClient

from utilidades import auth, crear_adulto, crear_coordinador, crear_nino


def test_endpoints_protegidos_exigen_token(client):
    assert client.get("/api/actividades").status_code == 401


def test_flujo_completo_docente_estudiante_padre(client):
    _, token_coord = crear_coordinador()
    docente, token_docente = crear_adulto(client, token_coord, "docente", "mgarcia", "Marta")
    padre, token_padre = crear_adulto(client, token_coord, "padre", "cperez", "Carlos")
    estudiante = crear_nino(client, token_coord, docente_id=docente["id_usuario"], acudientes_ids=[padre["id_usuario"]])
    assert estudiante["docente_id"] == docente["id_usuario"]
    assert len(estudiante["codigo_acceso"]) == 6

    # PIN incorrecto -> 401, y queda auditado como login fallido
    fallo = client.post(
        "/api/usuarios/login-pin", json={"codigo": estudiante["codigo_acceso"], "pin": "9999"}
    )
    assert fallo.status_code == 401

    login = client.post(
        "/api/usuarios/login-pin", json={"codigo": estudiante["codigo_acceso"].lower(), "pin": "4826"}
    )
    assert login.status_code == 200
    token_estudiante = login.json()["token"]

    # RF03: el docente crea una actividad de vocabulario
    actividad = client.post(
        "/api/actividades",
        json={
            "nombre": "Animales", "descripcion": "Empareja la imagen con la palabra",
            "nivel": 1, "tipo": "vocabulario", "puntaje_maximo": 100,
            "pregunta": "What animal is this?", "opciones": ["Dog", "Cat", "Bird", "Fish"],
            "respuesta_correcta": "Dog", "icono": "🐶",
        },
        headers=auth(token_docente),
    )
    assert actividad.status_code == 201, actividad.text

    # Un estudiante no puede reportar resultados de OTRO estudiante
    suplantacion = client.post(
        "/api/actividades/completar/otro-estudiante",
        json={"id_actividad": "x", "tiempo_empleado": 5, "intentos": 1, "puntaje_obtenido": 100},
        headers=auth(token_estudiante),
    )
    assert suplantacion.status_code == 403

    # RF03/RF05: completa la actividad y cruza el umbral de recompensa (100)
    resultado1 = client.post(
        f"/api/actividades/completar/{estudiante['id_usuario']}",
        json={"id_actividad": actividad.json()["id_actividad"], "tiempo_empleado": 20, "intentos": 1, "puntaje_obtenido": 100},
        headers=auth(token_estudiante),
    )
    assert resultado1.status_code == 200
    cuerpo1 = resultado1.json()
    assert cuerpo1["recompensa_generada"] is not None
    assert cuerpo1["nivel_logrado"] == 1  # aún no llega a 150

    # RF04: una segunda actividad hace que cruce a nivel 2 (umbral 150)
    resultado2 = client.post(
        f"/api/actividades/completar/{estudiante['id_usuario']}",
        json={"id_actividad": actividad.json()["id_actividad"], "tiempo_empleado": 15, "intentos": 1, "puntaje_obtenido": 50},
        headers=auth(token_estudiante),
    )
    assert resultado2.json()["nivel_logrado"] == 2
    assert resultado2.json()["subio_de_nivel"] is True

    # RF07/RF11: el coordinador le asigna el niño a su padre
    hijos = client.get(f"/api/usuarios/padre/{padre['id_usuario']}/hijos", headers=auth(token_padre))
    assert hijos.status_code == 200
    assert [h["id_usuario"] for h in hijos.json()] == [estudiante["id_usuario"]]

    # Un padre no puede consultar la lista de "hijos" de otro padre
    _, token_otro_padre = crear_adulto(client, token_coord, "padre", "otro", "Otro")
    ajeno = client.get(f"/api/usuarios/padre/{padre['id_usuario']}/hijos", headers=auth(token_otro_padre))
    assert ajeno.status_code == 403

    # El padre vinculado ya puede ver el progreso y las recompensas del hijo
    progreso = client.get(f"/api/usuarios/{estudiante['id_usuario']}/progreso", headers=auth(token_padre))
    assert progreso.status_code == 200
    assert progreso.json()["puntaje_total"] == 150

    recompensas = client.get(f"/api/recompensas/estudiante/{estudiante['id_usuario']}", headers=auth(token_padre))
    assert recompensas.status_code == 200
    assert len(recompensas.json()) == 1

    # RF06: estadísticas agregadas del docente
    stats = client.get(f"/api/usuarios/docente/{docente['id_usuario']}/estadisticas", headers=auth(token_docente))
    assert stats.status_code == 200
    assert stats.json()["total_estudiantes"] == 1

    # El hash del PIN nunca debe salir de la API por ningún endpoint que liste estudiantes
    lista_estudiantes = client.get(
        f"/api/usuarios/docente/{docente['id_usuario']}/estudiantes", headers=auth(token_docente)
    )
    assert "pin_hash" not in lista_estudiantes.text
    assert "pin_hash" not in hijos.text
    assert "pin_hash" not in stats.text


def test_solo_el_coordinador_puede_exportar_auditoria(client):
    _, token_coord = crear_coordinador()
    _, token_docente = crear_adulto(client, token_coord, "docente", "mgarcia")
    assert client.get("/api/auditoria/exportar.csv", headers=auth(token_docente)).status_code == 403
    permitido = client.get("/api/auditoria/exportar.csv", headers=auth(token_coord))
    assert permitido.status_code == 200
    assert permitido.headers["content-type"].startswith("text/csv")


def test_confirmar_entrega_exige_secreto_de_dispositivo(client):
    assert client.post("/api/recompensas/x/confirmar-entrega").status_code == 401
    incorrecto = client.post("/api/recompensas/x/confirmar-entrega", headers={"X-Device-Secret": "equivocado"})
    assert incorrecto.status_code == 401


def test_login_pin_con_codigo_inexistente(client):
    resp = client.post("/api/usuarios/login-pin", json={"codigo": "ZZZZZZ", "pin": "1234"})
    assert resp.status_code == 401


def test_intentos_fallidos_de_pin_se_guardan_aunque_la_peticion_falle(client):
    """La petición con PIN incorrecto termina en 401, pero el contador de fallos y la
    auditoría sí se guardan (ver app/db.get_db): al quinto fallo el código queda bloqueado."""
    from app.services.auth_service import MAX_FALLOS

    _, token_coord = crear_coordinador()
    nino = crear_nino(client, token_coord)
    for _ in range(MAX_FALLOS):
        assert client.post("/api/usuarios/login-pin", json={"codigo": nino["codigo_acceso"], "pin": "0000"}).status_code == 401
    bloqueado = client.post("/api/usuarios/login-pin", json={"codigo": nino["codigo_acceso"], "pin": "4826"})
    assert bloqueado.status_code == 429


def test_un_error_inesperado_deshace_lo_que_alcanzo_a_escribir(client, db, monkeypatch):
    from sqlalchemy import func, select

    from app.models.tablas import Auditoria, MundoDocente
    from app.routers import mundos

    _, token_coord = crear_coordinador()
    _, token = crear_adulto(client, token_coord, "docente", "mgarcia")

    def _falla(*args, **kwargs):
        raise RuntimeError("se cayó a mitad de camino")

    monkeypatch.setattr(mundos, "registrar_auditoria", _falla)  # falla después de crear el mundo
    r = TestClient(client.app, raise_server_exceptions=False).post(
        "/api/mundos", json={"titulo": "A medias"}, headers=auth(token)
    )
    assert r.status_code == 500
    assert db.scalar(select(func.count()).select_from(MundoDocente)) == 0
    # El error sí queda registrado en la auditoría.
    assert db.scalar(select(func.count()).select_from(Auditoria).where(Auditoria.tipo == "error_sistema")) == 1


def test_textos_mas_largos_que_su_columna_se_rechazan(client):
    _, token_coord = crear_coordinador()
    assert client.post("/api/usuarios/login-pin", json={"codigo": "A" * 50, "pin": "1234"}).status_code == 422
    resp = client.post("/api/coordinador/adultos", headers=auth(token_coord),
                       json={"nombre": "x" * 500, "rol": "padre", "usuario": "largo"})
    assert resp.status_code == 422


def test_los_cambios_se_guardan_antes_de_responder(client, monkeypatch):
    """Si guardar falla, la respuesta tiene que ser un error (no un 201 de algo que no quedó)."""
    from sqlalchemy.orm import Session

    _, token_coord = crear_coordinador()
    _, token = crear_adulto(client, token_coord, "docente", "mgarcia")

    def _commit_que_falla(self):
        raise RuntimeError("la base de datos no respondió")

    monkeypatch.setattr(Session, "commit", _commit_que_falla)
    r = TestClient(client.app, raise_server_exceptions=False).post(
        "/api/mundos", json={"titulo": "No guardado"}, headers=auth(token)
    )
    assert r.status_code == 500
