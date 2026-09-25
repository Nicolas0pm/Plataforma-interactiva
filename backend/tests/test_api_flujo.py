"""
Pruebas de integración de punta a punta sobre la API (con USE_FAKE_DB=true,
ver conftest.py), cubriendo el flujo real: registro, autenticación por rol,
RF11 (vinculación), RF03/RF04/RF05 (actividad -> progreso -> recompensa) y los
huecos de seguridad que se cerraron (guardas de rol, bug de `hijos_de_padre`).
"""


def _crear_usuario(client, **kwargs):
    headers = kwargs.pop("headers", {})
    payload = {
        "nombre": kwargs.pop("nombre", "Sin nombre"),
        "edad": kwargs.pop("edad", 30),
        "rol": kwargs.pop("rol"),
        "acudientes_ids": [],
        "docente_id": None,
        "email": kwargs.pop("email", None),
    }
    if payload["rol"] == "estudiante":
        payload["autoriza_datos_menor"] = True
    else:
        payload["acepta_terminos"] = True
    payload.update(kwargs)  # lo que quede (p. ej. pin_acceso) se agrega tal cual
    resp = client.post("/api/usuarios", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _login_dev(client, id_usuario, rol):
    resp = client.post("/api/usuarios/login-dev", json={"id_usuario": id_usuario, "rol": rol})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_endpoints_protegidos_exigen_token(client):
    assert client.get("/api/actividades").status_code == 401


def test_no_se_puede_crear_estudiante_sin_ser_docente_padre_o_admin(client):
    resp = client.post(
        "/api/usuarios",
        json={
            "nombre": "Ana", "edad": 7, "rol": "estudiante", "acudientes_ids": [],
            "docente_id": None, "email": None, "pin_acceso": "1234",
        },
    )
    assert resp.status_code == 401  # nadie autenticado en la petición


def test_flujo_completo_docente_estudiante_padre(client):
    docente = _crear_usuario(client, nombre="Marta", rol="docente", email="marta@escuela.co")
    token_docente = _login_dev(client, docente["id_usuario"], "docente")

    estudiante = _crear_usuario(
        client, nombre="Ana", edad=7, rol="estudiante", pin_acceso="1234",
        headers=_auth(token_docente),
    )
    assert estudiante["docente_id"] == docente["id_usuario"]
    assert len(estudiante["codigo_acceso"]) == 6

    # PIN incorrecto -> 401, y queda auditado como login fallido
    fallo = client.post(
        "/api/usuarios/login-pin", json={"codigo": estudiante["codigo_acceso"], "pin": "9999"}
    )
    assert fallo.status_code == 401

    login = client.post(
        "/api/usuarios/login-pin", json={"codigo": estudiante["codigo_acceso"].lower(), "pin": "1234"}
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
        headers=_auth(token_docente),
    )
    assert actividad.status_code == 201, actividad.text

    # Un estudiante no puede reportar resultados de OTRO estudiante
    suplantacion = client.post(
        "/api/actividades/completar/otro-estudiante",
        json={"id_actividad": "x", "tiempo_empleado": 5, "intentos": 1, "puntaje_obtenido": 100},
        headers=_auth(token_estudiante),
    )
    assert suplantacion.status_code == 403

    # RF03/RF05: completa la actividad y cruza el umbral de recompensa (100)
    resultado1 = client.post(
        f"/api/actividades/completar/{estudiante['id_usuario']}",
        json={"id_actividad": actividad.json()["id_actividad"], "tiempo_empleado": 20, "intentos": 1, "puntaje_obtenido": 100},
        headers=_auth(token_estudiante),
    )
    assert resultado1.status_code == 200
    cuerpo1 = resultado1.json()
    assert cuerpo1["recompensa_generada"] is not None
    assert cuerpo1["nivel_logrado"] == 1  # aún no llega a 150

    # RF04: una segunda actividad hace que cruce a nivel 2 (umbral 150)
    resultado2 = client.post(
        f"/api/actividades/completar/{estudiante['id_usuario']}",
        json={"id_actividad": actividad.json()["id_actividad"], "tiempo_empleado": 15, "intentos": 1, "puntaje_obtenido": 50},
        headers=_auth(token_estudiante),
    )
    assert resultado2.json()["nivel_logrado"] == 2
    assert resultado2.json()["subio_de_nivel"] is True

    # RF07/RF11: un padre se vincula escribiendo el código y el PIN del niño
    padre = _crear_usuario(client, nombre="Carlos", rol="padre", email="carlos@mail.com")
    token_padre = _login_dev(client, padre["id_usuario"], "padre")

    vincular = client.post(
        "/api/vinculacion", json={"codigo": estudiante["codigo_acceso"], "pin": "1234"}, headers=_auth(token_padre)
    )
    assert vincular.status_code == 200
    assert vincular.json()["codigo_acceso"] == estudiante["codigo_acceso"]
    assert "pin_hash" not in vincular.json()

    # Bug corregido: el panel de padres ahora SÍ encuentra a su hijo vinculado
    hijos = client.get(f"/api/usuarios/padre/{padre['id_usuario']}/hijos", headers=_auth(token_padre))
    assert hijos.status_code == 200
    assert [h["id_usuario"] for h in hijos.json()] == [estudiante["id_usuario"]]

    # Un padre no puede consultar la lista de "hijos" de otro padre
    otro_padre = _crear_usuario(client, nombre="Otro", rol="padre", email="otro@mail.com")
    token_otro_padre = _login_dev(client, otro_padre["id_usuario"], "padre")
    ajeno = client.get(f"/api/usuarios/padre/{padre['id_usuario']}/hijos", headers=_auth(token_otro_padre))
    assert ajeno.status_code == 403

    # El padre vinculado ya puede ver el progreso y las recompensas del hijo
    progreso = client.get(f"/api/usuarios/{estudiante['id_usuario']}/progreso", headers=_auth(token_padre))
    assert progreso.status_code == 200
    assert progreso.json()["puntaje_total"] == 150

    recompensas = client.get(f"/api/recompensas/estudiante/{estudiante['id_usuario']}", headers=_auth(token_padre))
    assert recompensas.status_code == 200
    assert len(recompensas.json()) == 1

    # RF06: estadísticas agregadas del docente
    stats = client.get(f"/api/usuarios/docente/{docente['id_usuario']}/estadisticas", headers=_auth(token_docente))
    assert stats.status_code == 200
    assert stats.json()["total_estudiantes"] == 1

    # El hash del PIN nunca debe salir de la API por ningún endpoint que liste estudiantes
    lista_estudiantes = client.get(
        f"/api/usuarios/docente/{docente['id_usuario']}/estudiantes", headers=_auth(token_docente)
    )
    assert "pin_hash" not in lista_estudiantes.text
    assert "pin_hash" not in hijos.text
    assert "pin_hash" not in stats.text


def test_solo_admin_puede_exportar_auditoria(client):
    admin = _crear_usuario(client, nombre="Admin", rol="admin", email="admin@escuela.co")
    docente = _crear_usuario(client, nombre="Marta", rol="docente", email="marta2@escuela.co")

    token_docente = _login_dev(client, docente["id_usuario"], "docente")
    negado = client.get("/api/auditoria/exportar.csv", headers=_auth(token_docente))
    assert negado.status_code == 403

    token_admin = _login_dev(client, admin["id_usuario"], "admin")
    permitido = client.get("/api/auditoria/exportar.csv", headers=_auth(token_admin))
    assert permitido.status_code == 200
    assert permitido.headers["content-type"].startswith("text/csv")


def test_confirmar_entrega_exige_secreto_de_dispositivo(client):
    sin_secreto = client.post("/api/recompensas/x/confirmar-entrega")
    assert sin_secreto.status_code == 401

    incorrecto = client.post(
        "/api/recompensas/x/confirmar-entrega", headers={"X-Device-Secret": "equivocado"}
    )
    assert incorrecto.status_code == 401


def test_pin_de_estudiante_debe_ser_de_4_digitos(client):
    docente = _crear_usuario(client, nombre="Marta", rol="docente", email="marta2@escuela.co")
    token_docente = _login_dev(client, docente["id_usuario"], "docente")
    for pin_invalido in ("12345", "12a4", "123"):
        resp = client.post(
            "/api/usuarios",
            json={"nombre": "Leo", "edad": 7, "rol": "estudiante", "acudientes_ids": [],
                  "docente_id": None, "email": None, "pin_acceso": pin_invalido,
                  "autoriza_datos_menor": True},
            headers=_auth(token_docente),
        )
        assert resp.status_code == 422, pin_invalido


def test_login_pin_con_codigo_inexistente(client):
    resp = client.post("/api/usuarios/login-pin", json={"codigo": "ZZZZZZ", "pin": "1234"})
    assert resp.status_code == 401


def test_adulto_debe_aceptar_terminos(client):
    resp = client.post(
        "/api/usuarios",
        json={"nombre": "Sin aceptar", "edad": 30, "rol": "padre", "acudientes_ids": [],
              "docente_id": None, "email": "x@mail.com"},
    )
    assert resp.status_code == 400


def test_registrar_nino_exige_autorizacion_de_datos(client, db):
    docente = _crear_usuario(client, nombre="Marta", rol="docente", email="marta3@escuela.co")
    token_docente = _login_dev(client, docente["id_usuario"], "docente")

    sin_autorizacion = client.post(
        "/api/usuarios",
        json={"nombre": "Leo", "edad": 7, "rol": "estudiante", "acudientes_ids": [],
              "docente_id": None, "email": None, "pin_acceso": "1234"},
        headers=_auth(token_docente),
    )
    assert sin_autorizacion.status_code == 400

    creado = _crear_usuario(
        client, nombre="Leo", edad=7, rol="estudiante", pin_acceso="1234", headers=_auth(token_docente)
    )
    guardado = db.collection("usuarios").document(creado["id_usuario"]).get().to_dict()
    assert guardado["autorizacion_datos"]["otorgada_por"] == docente["id_usuario"]
    assert guardado["autorizacion_datos"]["version_terminos"] == "1.0"
    docente_guardado = db.collection("usuarios").document(docente["id_usuario"]).get().to_dict()
    assert docente_guardado["terminos_aceptados"]["version"] == "1.0"
