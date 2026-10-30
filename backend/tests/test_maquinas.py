"""La máquina de premios se registra sola con su MAC y el docente la configura desde la página."""
from tests.utilidades import auth, crear_adulto, crear_coordinador, crear_nino

MAC = "24:6F:28:7F:3A:2C"
CLAVE = "clave-inventada-por-la-esp32"


def _registrar(client, mac=MAC, clave=CLAVE):
    r = client.post("/api/maquinas/registro", json={"mac": mac, "clave": clave})
    assert r.status_code == 200, r.text
    return {"X-Device-Id": r.json()["device_id"], "X-Device-Token": clave}


def _docente(client, usuario="mgarcia", con_nino=True):
    _, token_coord = crear_coordinador(f"coord-{usuario}")
    docente, token = crear_adulto(client, token_coord, "docente", usuario)
    nino = crear_nino(client, token_coord, docente_id=docente["id_usuario"]) if con_nino else None
    return token, nino


def test_la_maquina_se_registra_con_su_mac(client):
    maquina = _registrar(client)
    assert maquina["X-Device-Id"] == "MAQ-7F3A2C"
    yo = client.get("/api/maquinas/yo", headers=maquina).json()
    assert yo == {"device_id": "MAQ-7F3A2C", "vinculada": False, "wifi": None}
    # Volver a registrarse con la misma clave no crea otra máquina
    assert _registrar(client)["X-Device-Id"] == "MAQ-7F3A2C"


def test_mac_o_clave_no_validas(client):
    assert client.post("/api/maquinas/registro", json={"mac": "no-es-mac", "clave": CLAVE}).status_code == 422
    assert client.post("/api/maquinas/registro", json={"mac": MAC, "clave": "corta"}).status_code == 422


def test_el_docente_elige_su_maquina_de_la_lista(client):
    maquina = _registrar(client)
    token, nino = _docente(client)
    libres = client.get("/api/maquinas/disponibles", headers=auth(token)).json()
    assert [m["device_id"] for m in libres] == ["MAQ-7F3A2C"] and libres[0]["en_linea"] is True
    estado = client.post("/api/maquinas/vincular", headers=auth(token), json={"device_id": "MAQ-7F3A2C"}).json()
    assert estado["vinculada"] is True and estado["en_linea"] is True
    assert client.get("/api/maquinas/disponibles", headers=auth(token)).json() == []
    assert client.get("/api/maquinas/yo", headers=maquina).json()["vinculada"] is True
    perfil = client.get(f"/api/usuarios/{nino['id_usuario']}", headers=auth(token)).json()
    assert perfil["device_id"] == "MAQ-7F3A2C"


def test_no_se_puede_tomar_la_maquina_de_otro_salon(client):
    _registrar(client)
    token_a, _ = _docente(client, "docentea", con_nino=False)
    token_b, _ = _docente(client, "docenteb", con_nino=False)
    assert client.post("/api/maquinas/vincular", headers=auth(token_a), json={"device_id": "MAQ-7F3A2C"}).status_code == 200
    assert client.post("/api/maquinas/vincular", headers=auth(token_b), json={"device_id": "MAQ-7F3A2C"}).status_code == 409
    assert client.post("/api/maquinas/vincular", headers=auth(token_b), json={"device_id": "MAQ-000000"}).status_code == 404


def test_otra_clave_no_sirve_si_la_maquina_ya_tiene_salon(client):
    _registrar(client)
    token, _ = _docente(client, con_nino=False)
    client.post("/api/maquinas/vincular", headers=auth(token), json={"device_id": "MAQ-7F3A2C"})
    intruso = client.post("/api/maquinas/registro", json={"mac": MAC, "clave": "otra-clave-de-un-intruso"})
    assert intruso.status_code == 409
    assert client.get("/api/maquinas/yo", headers={"X-Device-Id": "MAQ-7F3A2C",
                                                    "X-Device-Token": "otra-clave-de-un-intruso"}).status_code == 401


def test_cambiar_wifi_desde_el_panel(client):
    maquina = _registrar(client)
    token, _ = _docente(client, con_nino=False)
    client.post("/api/maquinas/vincular", headers=auth(token), json={"device_id": "MAQ-7F3A2C"})
    pedido = client.post("/api/maquinas/wifi", headers=auth(token), json={"ssid": "Colegio_Nuevo", "password": "secreta123"})
    assert pedido.json()["wifi_pendiente"] == {"ssid": "Colegio_Nuevo"}  # la contraseña no vuelve al navegador
    yo = client.get("/api/maquinas/yo", headers=maquina).json()
    assert yo["wifi"] == {"ssid": "Colegio_Nuevo", "password": "secreta123"}
    client.post("/api/maquinas/yo/wifi", headers=maquina, json={"ok": True, "red": "Colegio_Nuevo"})
    estado = client.get("/api/maquinas/estado", headers=auth(token)).json()
    assert estado["red_actual"] == "Colegio_Nuevo" and estado["wifi_pendiente"] is False
    assert client.get("/api/maquinas/yo", headers=maquina).json()["wifi"] is None


def test_si_el_wifi_nuevo_falla_el_panel_lo_muestra(client):
    maquina = _registrar(client)
    token, _ = _docente(client, con_nino=False)
    client.post("/api/maquinas/vincular", headers=auth(token), json={"device_id": "MAQ-7F3A2C"})
    client.post("/api/maquinas/wifi", headers=auth(token), json={"ssid": "Mal_Escrita", "password": "x"})
    client.post("/api/maquinas/yo/wifi", headers=maquina, json={"ok": False, "red": "Mal_Escrita",
                                                               "detalle": "Contraseña incorrecta"})
    assert client.get("/api/maquinas/estado", headers=auth(token)).json()["wifi_estado"] == "Contraseña incorrecta"


def test_probar_pone_un_premio_que_la_maquina_suelta_y_confirma(client):
    maquina = _registrar(client)
    token, _ = _docente(client, con_nino=False)
    client.post("/api/maquinas/vincular", headers=auth(token), json={"device_id": "MAQ-7F3A2C"})
    prueba = client.post("/api/maquinas/probar", headers=auth(token)).json()
    cola = client.get("/api/recompensas/cola/MAQ-7F3A2C", headers=maquina).json()
    assert [p["id_historial"] for p in cola] == [prueba["id_historial"]]
    assert client.post(f"/api/recompensas/{prueba['id_historial']}/confirmar-entrega", headers=maquina).status_code == 200
    assert client.get("/api/recompensas/cola/MAQ-7F3A2C", headers=maquina).json() == []


def test_una_maquina_no_confirma_premios_de_otra(client):
    maquina_a = _registrar(client, "24:6F:28:00:00:0A")
    _registrar(client, "24:6F:28:00:00:0B", "otra-clave-de-la-maquina-b")
    token, _ = _docente(client, con_nino=False)
    client.post("/api/maquinas/vincular", headers=auth(token), json={"device_id": "MAQ-00000B"})
    premio = client.post("/api/maquinas/probar", headers=auth(token)).json()
    assert client.post(f"/api/recompensas/{premio['id_historial']}/confirmar-entrega", headers=maquina_a).status_code == 404


def test_desvincular_deja_la_maquina_libre(client):
    maquina = _registrar(client)
    token, nino = _docente(client)
    client.post("/api/maquinas/vincular", headers=auth(token), json={"device_id": "MAQ-7F3A2C"})
    assert client.delete("/api/maquinas", headers=auth(token)).status_code == 200
    assert client.get("/api/maquinas/estado", headers=auth(token)).json()["vinculada"] is False
    assert client.get("/api/maquinas/yo", headers=maquina).json()["vinculada"] is False
    assert [m["device_id"] for m in client.get("/api/maquinas/disponibles", headers=auth(token)).json()] == ["MAQ-7F3A2C"]
    assert client.post("/api/maquinas/probar", headers=auth(token)).status_code == 400


def test_solo_un_docente_usa_estas_opciones(client):
    _, token_coord = crear_coordinador()
    _, token_padre = crear_adulto(client, token_coord, "padre", "padre1")
    assert client.get("/api/maquinas/disponibles", headers=auth(token_padre)).status_code == 403
    assert client.get("/api/maquinas/disponibles").status_code == 401
    assert client.get("/api/maquinas/yo").status_code == 401


def test_el_secreto_compartido_sigue_funcionando(client):
    r = client.get("/api/recompensas/cola/aula-101", headers={"X-Device-Secret": "test-device-secret"})
    assert r.status_code == 200
