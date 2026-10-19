"""Login de docentes, padres y coordinadores: usuario + contraseña (app/services/auth_service.py)."""
from app.services.auth_service import MAX_FALLOS, hash_password, verificar_password
from utilidades import PASSWORD, auth, crear_adulto, crear_coordinador


def _login(client, usuario="mgarcia", password=PASSWORD):
    return client.post("/api/usuarios/login", json={"usuario": usuario, "password": password})


def test_la_contrasena_se_guarda_como_hash():
    guardado = hash_password("clave-segura-1")
    assert "clave-segura-1" not in guardado and guardado.startswith("scrypt$")
    assert verificar_password("clave-segura-1", guardado)
    assert not verificar_password("otra-clave-123", guardado)
    assert hash_password("clave-segura-1") != guardado  # cada hash lleva su propia sal


def test_primer_ingreso_obliga_a_cambiar_la_contrasena_y_aceptar_terminos(client):
    _, token_coord = crear_coordinador()
    creado = client.post("/api/coordinador/adultos", headers=auth(token_coord),
                         json={"nombre": "Marta", "rol": "docente", "usuario": "mgarcia", "email": "Marta@Escuela.co"}).json()
    temporal = creado["password_temporal"]
    assert len(temporal) == 12 and "password_hash" not in creado

    sesion = _login(client, password=temporal).json()
    assert sesion["rol"] == "docente" and sesion["debe_cambiar_password"] is True
    token = sesion["token"]
    sin_terminos = {"actual": temporal, "nueva": PASSWORD}
    assert client.post("/api/usuarios/cambiar-password", headers=auth(token), json=sin_terminos).status_code == 400
    igual = {"actual": temporal, "nueva": temporal, "acepta_terminos": True}
    assert client.post("/api/usuarios/cambiar-password", headers=auth(token), json=igual).status_code == 400
    ok = client.post("/api/usuarios/cambiar-password", headers=auth(token), json={**sin_terminos, "acepta_terminos": True})
    assert ok.status_code == 200

    assert _login(client, password=temporal).status_code == 401
    sesion = _login(client, usuario="  MGarcia ").json()  # sin importar mayúsculas ni espacios
    assert sesion["debe_cambiar_password"] is False
    assert _login(client, usuario="marta@escuela.co").status_code == 200  # también con el correo
    yo = client.get("/api/usuarios/sesion", headers=auth(sesion["token"])).json()
    assert yo["usuario"] == "mgarcia" and yo["email"] == "marta@escuela.co"


def test_credenciales_incorrectas_dan_el_mismo_error(client):
    _, token_coord = crear_coordinador()
    crear_adulto(client, token_coord, "docente", "mgarcia")
    mala = _login(client, password="otra-clave-123")
    inexistente = _login(client, usuario="nadie")
    assert mala.status_code == inexistente.status_code == 401
    assert mala.json() == inexistente.json()


def test_el_usuario_se_bloquea_tras_varios_fallos(client):
    _, token_coord = crear_coordinador()
    crear_adulto(client, token_coord, "docente", "mgarcia")
    for _ in range(MAX_FALLOS):
        assert _login(client, password="otra-clave-123").status_code == 401
    assert _login(client).status_code == 429  # ni la contraseña correcta, por un rato


def test_cambiar_contrasena_despues(client):
    _, token_coord = crear_coordinador()
    _, token = crear_adulto(client, token_coord, "padre", "mgarcia")
    cambio = {"actual": "equivocada-1", "nueva": "nueva-clave-2"}
    assert client.post("/api/usuarios/cambiar-password", json=cambio, headers=auth(token)).status_code == 400
    cambio["actual"] = PASSWORD
    assert client.post("/api/usuarios/cambiar-password", json=cambio, headers=auth(token)).status_code == 200
    assert _login(client).status_code == 401
    assert _login(client, password="nueva-clave-2").status_code == 200


def test_un_token_de_otro_rol_no_sirve(client):
    """Si alguien cambia el rol dentro del token, la firma ya no coincide; y un token viejo
    con un rol que la cuenta ya no tiene, tampoco entra."""
    from app.services.auth_service import crear_token_sesion

    _, token_coord = crear_coordinador()
    padre, _ = crear_adulto(client, token_coord, "padre", "cperez")
    falso = crear_token_sesion(padre["id_usuario"], "admin")
    assert client.get("/api/coordinador/usuarios", headers=auth(falso)).status_code == 401
