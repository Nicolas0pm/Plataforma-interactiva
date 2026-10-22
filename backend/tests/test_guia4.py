"""Requisitos de la Guía 4: frecuencia de exámenes y premios (RF06, ver también
test_examenes.py), temario por salón (RF07), edición de cuentas por el coordinador (RF01) y
temario institucional (RF08)."""
from test_lecciones import _preparar
from utilidades import auth, crear_coordinador, crear_nino


def test_frecuencia_de_premio_valida_rango_y_dueno(client, db):
    docente, token_docente, _, token_nino = _preparar(client, db)
    url = f"/api/usuarios/docente/{docente['id_usuario']}/premio"
    assert client.put(url, json={"cada_mundos": 6}, headers=auth(token_docente)).status_code == 422
    assert client.put(url, json={"cada_mundos": 0}, headers=auth(token_docente)).status_code == 422
    assert client.put(url, json={"cada_mundos": 2}, headers=auth(token_nino)).status_code == 403


def test_docente_apaga_y_ordena_mundos_de_su_salon(client, db):
    _, token_docente, nino, token = _preparar(client, db)
    temario = client.get("/api/temario/salon", headers=auth(token_docente)).json()
    vocab = [t["id"] for t in temario["vocabulario"]]
    assert vocab[0] == "animals" and all(t["activo"] for t in temario["vocabulario"])
    # «colors» primero y «animals» apagado
    nuevo = ["colors", *[u for u in vocab if u not in ("colors", "animals")], "animals"]
    r = client.put("/api/temario/salon/vocabulario", headers=auth(token_docente),
                   json={"unidades": [{"id": u, "activo": u != "animals"} for u in nuevo]})
    assert r.status_code == 200, r.text
    assert [t["id"] for t in r.json()["vocabulario"]] == nuevo
    leccion = client.get("/api/lecciones/jugar", headers=auth(token)).json()
    assert leccion["unidad"]["id"] == "colors"
    resumen = client.get(f"/api/lecciones/resumen/{nino['id_usuario']}", headers=auth(token)).json()
    vocab_nino = [u["id"] for u in resumen["unidades"] if u["seccion"] == "vocabulario"]
    assert vocab_nino == nuevo[:-1]


def test_temario_del_salon_exige_lista_completa_y_un_activo(client, db):
    _, token_docente, _, token_nino = _preparar(client, db)
    vocab = [t["id"] for t in client.get("/api/temario/salon", headers=auth(token_docente)).json()["vocabulario"]]
    url = "/api/temario/salon/vocabulario"
    incompleto = {"unidades": [{"id": u, "activo": True} for u in vocab[1:]]}
    assert client.put(url, json=incompleto, headers=auth(token_docente)).status_code == 400
    ninguno = {"unidades": [{"id": u, "activo": False} for u in vocab]}
    assert client.put(url, json=ninguno, headers=auth(token_docente)).status_code == 400
    assert client.put("/api/temario/salon/historia", json=incompleto, headers=auth(token_docente)).status_code == 404
    assert client.get("/api/temario/salon", headers=auth(token_nino)).status_code == 403


def test_coordinador_apaga_un_mundo_para_todos(client, db):
    _, token_docente, _, token = _preparar(client, db)
    _, token_coord = crear_coordinador("coord2")
    r = client.patch("/api/coordinador/temario/animals", json={"activo": False}, headers=auth(token_coord))
    assert r.status_code == 200, r.text
    assert client.get("/api/lecciones/jugar", headers=auth(token)).json()["unidad"]["id"] == "colors"
    salon = client.get("/api/temario/salon", headers=auth(token_docente)).json()["vocabulario"]
    assert next(t for t in salon if t["id"] == "animals")["global_activo"] is False
    temario = client.get("/api/coordinador/temario", headers=auth(token_coord)).json()
    assert next(t for t in temario["vocabulario"] if t["id"] == "animals")["activo"] is False
    assert client.patch("/api/coordinador/temario/no-existe", json={"activo": False},
                        headers=auth(token_coord)).status_code == 404
    assert client.patch("/api/coordinador/temario/animals", json={"activo": True},
                        headers=auth(token_docente)).status_code == 403


def test_coordinador_no_deja_un_apartado_vacio(client, db):
    _, token_coord = crear_coordinador()
    temario = client.get("/api/coordinador/temario", headers=auth(token_coord)).json()
    gramatica = [t["id"] for t in temario["gramatica"]]
    for u in gramatica[:-1]:
        assert client.patch(f"/api/coordinador/temario/{u}", json={"activo": False}, headers=auth(token_coord)).status_code == 200
    assert client.patch(f"/api/coordinador/temario/{gramatica[-1]}", json={"activo": False},
                        headers=auth(token_coord)).status_code == 400


def test_coordinador_edita_datos_de_las_cuentas(client, db):
    docente, token_docente, nino, _ = _preparar(client, db)
    _, token_coord = crear_coordinador("coord2")
    r = client.patch(f"/api/coordinador/usuarios/{nino['id_usuario']}", headers=auth(token_coord),
                     json={"nombre": "Ana María", "edad": 8})
    assert r.status_code == 200 and (r.json()["nombre"], r.json()["edad"]) == ("Ana María", 8)
    assert r.json()["activo"] is True
    r = client.patch(f"/api/coordinador/usuarios/{docente['id_usuario']}", headers=auth(token_coord),
                     json={"nombre": "Marta G.", "email": "Marta@Colegio.edu.co"})
    assert r.status_code == 200 and r.json()["email"] == "marta@colegio.edu.co"
    # Edad solo para niños; correo solo para adultos
    assert client.patch(f"/api/coordinador/usuarios/{docente['id_usuario']}", headers=auth(token_coord),
                        json={"edad": 9}).status_code == 400
    assert client.patch(f"/api/coordinador/usuarios/{nino['id_usuario']}", headers=auth(token_coord),
                        json={"email": "x@y.co"}).status_code == 400
    # El correo no se repite; "" lo quita
    otro = crear_nino(client, token_coord, nombre="Leo")
    assert otro["email"] is None
    r = client.patch(f"/api/coordinador/usuarios/{docente['id_usuario']}", headers=auth(token_coord), json={"email": ""})
    assert r.json()["email"] is None
    # El docente no puede editar cuentas
    assert client.patch(f"/api/coordinador/usuarios/{nino['id_usuario']}", headers=auth(token_docente),
                        json={"nombre": "X"}).status_code == 403
    # Desactivar sigue funcionando igual
    r = client.patch(f"/api/coordinador/usuarios/{nino['id_usuario']}", headers=auth(token_coord), json={"activo": False})
    assert r.json()["activo"] is False
