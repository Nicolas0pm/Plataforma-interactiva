"""La máquina de premios se vincula desde el panel del docente y se autentica con su token."""
from tests.utilidades import auth, crear_adulto, crear_coordinador, crear_nino


def _docente_con_nino(client):
    _, token_coord = crear_coordinador()
    docente, token_docente = crear_adulto(client, token_coord, "docente", "mgarcia")
    nino = crear_nino(client, token_coord, docente_id=docente["id_usuario"])
    return docente, token_docente, nino


def test_vincular_crea_la_maquina_y_la_asigna_al_salon(client):
    docente, token, nino = _docente_con_nino(client)
    r = client.post("/api/maquinas/vincular", headers=auth(token))
    assert r.status_code == 201
    datos = r.json()
    assert datos["device_id"].startswith("maq-") and len(datos["token"]) > 30
    estado = client.get("/api/maquinas/estado", headers=auth(token)).json()
    assert estado["device_id"] == datos["device_id"] and estado["vinculada"] is True and estado["en_linea"] is False
    perfil = client.get(f"/api/usuarios/{nino['id_usuario']}", headers=auth(token)).json()
    assert perfil["device_id"] == datos["device_id"]


def test_la_maquina_consulta_su_cola_con_su_token_y_queda_en_linea(client):
    _, token, _ = _docente_con_nino(client)
    maquina = client.post("/api/maquinas/vincular", headers=auth(token)).json()
    cabeceras = {"X-Device-Token": maquina["token"]}
    cola = client.get(f"/api/recompensas/cola/{maquina['device_id']}", headers=cabeceras)
    assert cola.status_code == 200 and cola.json() == []
    assert client.get("/api/maquinas/estado", headers=auth(token)).json()["en_linea"] is True


def test_token_equivocado_o_de_otra_maquina_no_sirve(client):
    _, token, _ = _docente_con_nino(client)
    maquina = client.post("/api/maquinas/vincular", headers=auth(token)).json()
    assert client.get(f"/api/recompensas/cola/{maquina['device_id']}",
                      headers={"X-Device-Token": "equivocado"}).status_code == 401
    assert client.get("/api/recompensas/cola/maq-otra", headers={"X-Device-Token": maquina["token"]}).status_code == 401


def test_volver_a_vincular_anula_el_token_anterior(client):
    _, token, _ = _docente_con_nino(client)
    vieja = client.post("/api/maquinas/vincular", headers=auth(token)).json()
    nueva = client.post("/api/maquinas/vincular", headers=auth(token)).json()
    assert nueva["device_id"] != vieja["device_id"]
    assert client.get(f"/api/recompensas/cola/{vieja['device_id']}",
                      headers={"X-Device-Token": vieja["token"]}).status_code == 401


def test_probar_pone_un_premio_que_la_maquina_suelta_y_confirma(client):
    _, token, _ = _docente_con_nino(client)
    maquina = client.post("/api/maquinas/vincular", headers=auth(token)).json()
    prueba = client.post("/api/maquinas/probar", headers=auth(token))
    assert prueba.status_code == 200
    cabeceras = {"X-Device-Id": maquina["device_id"], "X-Device-Token": maquina["token"]}
    cola = client.get(f"/api/recompensas/cola/{maquina['device_id']}", headers=cabeceras).json()
    assert [p["id_historial"] for p in cola] == [prueba.json()["id_historial"]]
    confirmada = client.post(f"/api/recompensas/{cola[0]['id_historial']}/confirmar-entrega", headers=cabeceras)
    assert confirmada.status_code == 200
    assert client.get(f"/api/recompensas/cola/{maquina['device_id']}", headers=cabeceras).json() == []


def test_una_maquina_no_confirma_premios_de_otra(client):
    _, token_coord = crear_coordinador()
    _, token_a = crear_adulto(client, token_coord, "docente", "docentea")
    _, token_b = crear_adulto(client, token_coord, "docente", "docenteb")
    maquina_a = client.post("/api/maquinas/vincular", headers=auth(token_a)).json()
    maquina_b = client.post("/api/maquinas/vincular", headers=auth(token_b)).json()
    premio_b = client.post("/api/maquinas/probar", headers=auth(token_b)).json()
    intento = client.post(f"/api/recompensas/{premio_b['id_historial']}/confirmar-entrega",
                          headers={"X-Device-Id": maquina_a["device_id"], "X-Device-Token": maquina_a["token"]})
    assert intento.status_code == 404
    cola_b = client.get(f"/api/recompensas/cola/{maquina_b['device_id']}", headers={"X-Device-Token": maquina_b["token"]})
    assert len(cola_b.json()) == 1


def test_desvincular_quita_la_maquina_del_salon(client):
    _, token, nino = _docente_con_nino(client)
    maquina = client.post("/api/maquinas/vincular", headers=auth(token)).json()
    assert client.delete("/api/maquinas", headers=auth(token)).status_code == 200
    assert client.get("/api/maquinas/estado", headers=auth(token)).json()["device_id"] is None
    assert client.get(f"/api/recompensas/cola/{maquina['device_id']}",
                      headers={"X-Device-Token": maquina["token"]}).status_code == 401
    assert client.post("/api/maquinas/probar", headers=auth(token)).status_code == 400


def test_solo_un_docente_vincula_maquinas(client):
    _, token_coord = crear_coordinador()
    _, token_padre = crear_adulto(client, token_coord, "padre", "padre1")
    assert client.post("/api/maquinas/vincular", headers=auth(token_padre)).status_code == 403
    assert client.post("/api/maquinas/vincular").status_code == 401


def test_el_secreto_compartido_sigue_funcionando(client):
    _, token, _ = _docente_con_nino(client)
    maquina = client.post("/api/maquinas/vincular", headers=auth(token)).json()
    r = client.get(f"/api/recompensas/cola/{maquina['device_id']}", headers={"X-Device-Secret": "test-device-secret"})
    assert r.status_code == 200
