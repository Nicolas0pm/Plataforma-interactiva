"""Camino guiado de lecciones (app/services/lecciones_service.py)."""
from datetime import datetime, timedelta, timezone

from app.services.lecciones_service import sembrar_temario


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _preparar(client, db):
    sembrar_temario(db)
    docente = client.post("/api/usuarios", json={
        "nombre": "Marta", "edad": 40, "rol": "docente", "acudientes_ids": [], "docente_id": None,
        "email": "marta@escuela.co", "acepta_terminos": True,
    }).json()
    db.collection("usuarios").document(docente["id_usuario"]).update({"email_verificado": True})
    token_docente = client.post("/api/usuarios/login-dev", json={"id_usuario": docente["id_usuario"], "rol": "docente"}).json()["token"]
    nino = client.post("/api/usuarios", headers=_auth(token_docente), json={
        "nombre": "Ana", "edad": 7, "rol": "estudiante", "acudientes_ids": [], "docente_id": None,
        "email": None, "pin_acceso": "1234", "autoriza_datos_menor": True,
    }).json()
    token_nino = client.post("/api/usuarios/login-pin", json={"codigo": nino["codigo_acceso"], "pin": "1234"}).json()["token"]
    return docente, token_docente, nino, token_nino


def _jugar(client, token, errores=0, unidad=None, leccion=None, seccion="vocabulario"):
    params = {"unidad": unidad, "leccion": leccion} if unidad else {"seccion": seccion}
    leccion_datos = client.get("/api/lecciones/jugar", params=params, headers=_auth(token)).json()
    respuestas = []
    for i, p in enumerate(leccion_datos["preguntas"]):
        mala = next(o for o in p["opciones"] if o != p["respuesta_correcta"])
        respuestas.append({"id_actividad": p["id_actividad"], "respuesta": mala if i < errores else p["respuesta_correcta"]})
        if i + 1 == errores and errores >= leccion_datos["vidas"]:
            break  # se quedó sin vidas: la lección termina ahí
    resultado = client.post("/api/lecciones/resultado", headers=_auth(token), json={
        "unidad": leccion_datos["unidad"]["id"], "leccion": leccion_datos["leccion"], "respuestas": respuestas,
    })
    return leccion_datos, resultado


def test_la_plataforma_elige_la_primera_leccion(client, db):
    _, _, _, token = _preparar(client, db)
    leccion = client.get("/api/lecciones/jugar", headers=_auth(token)).json()
    assert (leccion["unidad"]["id"], leccion["leccion"], leccion["modo"]) == ("animals", 1, "nueva")
    assert len(leccion["preguntas"]) == 8
    assert leccion["vidas"] == 5 and leccion["vidas_max"] == 5


def test_aprobar_suma_puntos_y_avanza(client, db):
    _, _, _, token = _preparar(client, db)
    _, r = _jugar(client, token, errores=1)
    datos = r.json()
    assert datos["aprobada"] is True
    assert datos["aciertos"] == 7 and datos["puntos_ganados"] == 70
    assert (datos["siguiente"]["unidad"], datos["siguiente"]["leccion"]) == ("animals", 2)


def test_no_se_puede_saltar_a_una_leccion_bloqueada(client, db):
    _, _, _, token = _preparar(client, db)
    r = client.get("/api/lecciones/jugar", params={"unidad": "simple-past", "leccion": 1}, headers=_auth(token))
    assert r.status_code == 403


def _recargar_vidas(db, id_nino, cantidad=5, hace_minutos=0):
    """Deja al niño con `cantidad` vidas, como si la recarga hubiera empezado hace `hace_minutos`."""
    ref = db.collection("usuarios").document(id_nino).collection("resultados").document("actual")
    desde = datetime.now(timezone.utc) - timedelta(minutes=hace_minutos)
    ref.update({"vidas": {"cantidad": cantidad, "desde": None if cantidad >= 5 else desde}})


def test_perder_todas_las_vidas_repite_la_leccion(client, db):
    _, _, nino, token = _preparar(client, db)
    _, r = _jugar(client, token, errores=5)
    datos = r.json()
    assert datos["aprobada"] is False and datos["puntos_ganados"] == 0
    assert (datos["siguiente"]["unidad"], datos["siguiente"]["leccion"]) == ("animals", 1)
    assert len(datos["errores"]) == 5
    assert datos["vidas"]["actuales"] == 0 and datos["vidas"]["proxima_vida"] is not None


def test_las_vidas_se_guardan_entre_lecciones_y_se_recargan(client, db):
    _, _, nino, token = _preparar(client, db)
    _, r = _jugar(client, token, errores=2)          # aprueba, pero gasta 2 vidas
    assert r.json()["aprobada"] is True and r.json()["vidas"]["actuales"] == 3
    leccion, _ = _jugar(client, token, errores=0)    # la siguiente empieza con 3, no con 5
    assert leccion["vidas"] == 3

    # Sin vidas no puede empezar lecciones nuevas...
    _recargar_vidas(db, nino["id_usuario"], cantidad=0)
    r = client.get("/api/lecciones/jugar", headers=_auth(token))
    assert r.status_code == 409 and "sin vidas" in r.json()["detail"]
    # ...pero sí practicar, que no gasta vidas y al aprobar devuelve una.
    practica, r = _jugar(client, token, unidad="animals", leccion=1, errores=1)
    assert practica["modo"] == "practica" and r.json()["aprobada"] is True
    assert r.json()["vidas"]["actuales"] == 1 and r.json()["vida_recuperada"] is True

    # Cada 30 minutos vuelve una vida (hasta 5).
    _recargar_vidas(db, nino["id_usuario"], cantidad=0, hace_minutos=65)
    resumen = client.get(f"/api/lecciones/resumen/{nino['id_usuario']}", headers=_auth(token)).json()
    assert resumen["vidas"]["actuales"] == 2
    _recargar_vidas(db, nino["id_usuario"], cantidad=0, hace_minutos=600)
    resumen = client.get(f"/api/lecciones/resumen/{nino['id_usuario']}", headers=_auth(token)).json()
    assert resumen["vidas"]["actuales"] == 5 and resumen["vidas"]["proxima_vida"] is None


def test_repetir_una_leccion_aprobada_es_practica_sin_puntos(client, db):
    _, _, _, token = _preparar(client, db)
    _jugar(client, token)
    leccion, r = _jugar(client, token, unidad="animals", leccion=1)
    assert leccion["modo"] == "practica"
    assert r.json()["aprobada"] is True and r.json()["puntos_ganados"] == 0


def test_respuestas_duplicadas_se_rechazan(client, db):
    _, _, _, token = _preparar(client, db)
    leccion = client.get("/api/lecciones/jugar", headers=_auth(token)).json()
    p = leccion["preguntas"][0]
    r = client.post("/api/lecciones/resultado", headers=_auth(token), json={
        "unidad": "animals", "leccion": 1,
        "respuestas": [{"id_actividad": p["id_actividad"], "respuesta": p["respuesta_correcta"]}] * 8,
    })
    assert r.status_code == 400


def test_repaso_automatico_de_la_leccion_mas_debil(client, db):
    _, _, nino, token = _preparar(client, db)
    _jugar(client, token, errores=2)          # animals-1 aprobada con 6/8 (75 %)
    _jugar(client, token)                     # animals-2
    _, r = _jugar(client, token)              # animals-3 → ya van 3 nuevas
    # animals-1 se acaba de jugar: todavía no se repasa (parecería que no se guardó).
    assert r.json()["siguiente"] == {"unidad": "animals", "leccion": 4, "modo": "nueva"}

    # Pasada una hora, sí le toca el repaso de la más débil.
    ref = db.collection("usuarios").document(nino["id_usuario"]).collection("resultados").document("actual")
    progreso = ref.get().to_dict()
    progreso["lecciones"]["animals-1"]["ultima"] = datetime.now(timezone.utc) - timedelta(hours=2)
    ref.set(progreso)
    leccion = client.get("/api/lecciones/jugar", headers=_auth(token)).json()
    assert (leccion["unidad"]["id"], leccion["leccion"], leccion["modo"]) == ("animals", 1, "repaso")


def _completar_mundo(client, token, lecciones=5):
    resultados = [_jugar(client, token)[1].json() for _ in range(lecciones)]
    return resultados


def test_completar_un_mundo_sin_maquina_solo_felicita(client, db):
    _, _, _, token = _preparar(client, db)
    resultados = _completar_mundo(client, token)
    assert all(r["mundo_completado"] is None for r in resultados[:4])
    mundo = resultados[4]["mundo_completado"]
    assert mundo["unidad"] == "animals"
    assert mundo["recompensa"]["device_id"] is None and mundo["recompensa"]["estado"] == "celebrada"
    # Repetir una lección del mundo ya completado no da otro premio
    _, r = _jugar(client, token, unidad="animals", leccion=1)
    assert r.json()["mundo_completado"] is None


def test_completar_un_mundo_con_maquina_encola_un_juguete(client, db, monkeypatch):
    from app.services import recompensas_service
    from app.services.fake_firestore import _realtime_store

    monkeypatch.setattr(recompensas_service._settings, "realtime_db_url", "https://fake-rtdb")
    docente, token_docente, nino, token = _preparar(client, db)
    r = client.put(f"/api/usuarios/docente/{docente['id_usuario']}/dispensador",
                   json={"device_id": "aula-101"}, headers=_auth(token_docente))
    assert r.json() == {"device_id": "aula-101", "estudiantes": 1}

    recompensa = _completar_mundo(client, token)[4]["mundo_completado"]["recompensa"]
    assert recompensa["device_id"] == "aula-101" and recompensa["estado"] == "pendiente"
    # Cada premio es un nodo propio en la cola: no se pisan entre sí
    clave = f"cola_recompensas/aula-101/{recompensa['id_historial']}"
    assert _realtime_store[clave]["comando"] == "dispensar"

    # La máquina confirma la entrega y el pedido sale de la cola
    from app.routers import recompensas as router_recompensas
    monkeypatch.setattr(router_recompensas._settings, "realtime_db_url", "https://fake-rtdb")
    ok = client.post(f"/api/recompensas/{recompensa['id_historial']}/confirmar-entrega",
                     headers={"X-Device-Secret": "test-device-secret"})
    assert ok.status_code == 200 and clave not in _realtime_store


def test_ninos_nuevos_heredan_la_maquina_del_salon(client, db):
    docente, token_docente, _, _ = _preparar(client, db)
    client.put(f"/api/usuarios/docente/{docente['id_usuario']}/dispensador", json={"device_id": "aula-7"}, headers=_auth(token_docente))
    nuevo = client.post("/api/usuarios", headers=_auth(token_docente), json={
        "nombre": "Leo", "edad": 7, "rol": "estudiante", "acudientes_ids": [], "docente_id": None,
        "email": None, "pin_acceso": "4321", "autoriza_datos_menor": True,
    }).json()
    assert nuevo["device_id"] == "aula-7"


def test_tienda_gasta_puntos_sin_bajar_el_nivel(client, db):
    _, _, _, token = _preparar(client, db)
    _jugar(client, token)
    _jugar(client, token)                                   # 160 puntos
    tienda = client.get("/api/tienda", headers=_auth(token)).json()
    assert tienda["perfil"]["saldo"] == 160 and tienda["perfil"]["avatar_emoji"] == "🦊"
    compra = client.post("/api/tienda/comprar", json={"item_id": "marco-arcoiris"}, headers=_auth(token))
    assert compra.status_code == 200 and compra.json()["saldo"] == 60 and compra.json()["marco"] == "marco-arcoiris"
    caro = client.post("/api/tienda/comprar", json={"item_id": "avatar-dragon"}, headers=_auth(token))
    assert caro.status_code == 400
    repetido = client.post("/api/tienda/comprar", json={"item_id": "marco-arcoiris"}, headers=_auth(token))
    assert repetido.status_code == 400
    sin_comprar = client.post("/api/tienda/equipar", json={"item_id": "avatar-dragon", "tipo": "avatar"}, headers=_auth(token))
    assert sin_comprar.status_code == 400
    resumen = client.get("/api/lecciones/jugar", headers=_auth(token))  # sigue jugando normal
    assert resumen.status_code == 200


def test_mundos_del_profe_solo_seleccion_multiple(client, db):
    docente, token_docente, nino, token = _preparar(client, db)
    mundo = client.post("/api/mundos", json={"titulo": "Mi salón", "emoji": "🏫"}, headers=_auth(token_docente)).json()
    base = f"/api/mundos/{mundo['id_mundo']}/preguntas"
    malas = [
        {"pregunta": "¿Abierta?", "opciones": ["solo una"], "respuesta_correcta": "solo una"},
        {"pregunta": "Repetidas", "opciones": ["a", "A"], "respuesta_correcta": "a"},
        {"pregunta": "Sin la correcta", "opciones": ["a", "b"], "respuesta_correcta": "c"},
        {"pregunta": "Muchas", "opciones": ["a", "b", "c", "d", "e"], "respuesta_correcta": "a"},
    ]
    for mala in malas:
        assert client.post(base, json=mala, headers=_auth(token_docente)).status_code == 422
    for i in range(10):
        r = client.post(base, json={"pregunta": f"How do you say {i}?", "opciones": [f"ok{i}", "no", "maybe"],
                                     "respuesta_correcta": f"ok{i}", "icono": "🔢"}, headers=_auth(token_docente))
        assert r.status_code == 201
    assert client.get("/api/mundos", headers=_auth(token_docente)).json()[0]["lecciones"] == 2  # 10 → 8 + 2

    # El niño lo ve en su apartado "profesor" y lo juega como cualquier otro
    leccion, r = _jugar(client, token, seccion="profesor")
    assert leccion["unidad"]["titulo"]["es"] == "Mi salón" and len(leccion["preguntas"]) == 8
    assert r.json()["aprobada"] is True
    leccion2, r2 = _jugar(client, token, seccion="profesor")
    assert len(leccion2["preguntas"]) == 2 and r2.json()["mundo_completado"]["unidad"] == leccion["unidad"]["id"]

    # Otro docente no puede tocar ese mundo
    otro = client.post("/api/usuarios", json={"nombre": "Otro", "edad": 30, "rol": "docente", "acudientes_ids": [],
                                              "docente_id": None, "email": "o@e.co", "acepta_terminos": True}).json()
    db.collection("usuarios").document(otro["id_usuario"]).update({"email_verificado": True})
    token_otro = client.post("/api/usuarios/login-dev", json={"id_usuario": otro["id_usuario"], "rol": "docente"}).json()["token"]
    assert client.post(base, json={"pregunta": "x", "opciones": ["a", "b"], "respuesta_correcta": "a"},
                       headers=_auth(token_otro)).status_code == 403


def test_preguntas_del_profe_pueden_llevar_imagen(client, db):
    docente, token_docente, nino, token = _preparar(client, db)
    mundo = client.post("/api/mundos", json={"titulo": "Fotos"}, headers=_auth(token_docente)).json()
    base = f"/api/mundos/{mundo['id_mundo']}/preguntas"
    imagen = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    pregunta = {"pregunta": "What is this?", "opciones": ["dog", "cat"], "respuesta_correcta": "dog"}
    assert client.post(base, json={**pregunta, "imagen": imagen}, headers=_auth(token_docente)).status_code == 201
    for mala in ("https://example.com/x.jpg", "data:text/html;base64,PGgxPg==", "data:image/png;base64," + "A" * 300_000):
        assert client.post(base, json={**pregunta, "imagen": mala}, headers=_auth(token_docente)).status_code == 422
    assert client.get(base, headers=_auth(token_docente)).json()[0]["imagen"] == imagen
    leccion = client.get("/api/lecciones/jugar?seccion=profesor", headers=_auth(token)).json()
    assert leccion["preguntas"][0]["imagen"] == imagen


def test_docente_ve_quien_necesita_ayuda_y_por_que(client, db):
    docente, token_docente, nino, token = _preparar(client, db)
    _jugar(client, token, errores=5)
    _recargar_vidas(db, nino["id_usuario"])
    _jugar(client, token, errores=5)
    resumen = client.get(f"/api/lecciones/docente/{docente['id_usuario']}", headers=_auth(token_docente)).json()
    fila = resumen["estudiantes"][0]
    assert fila["nombre"] == "Ana" and fila["necesita_ayuda"] is True
    assert any("Perdió 2 veces" in m for m in fila["motivos"])
    assert resumen["necesitan_ayuda"] == 1 and resumen["activos_hoy"] == 1
    detalle = client.get(f"/api/lecciones/resumen/{nino['id_usuario']}", headers=_auth(token_docente)).json()
    assert detalle["errores_frecuentes"] and detalle["recientes"][0]["aprobada"] is False


def test_gramatica_es_un_camino_aparte_que_el_nino_puede_elegir(client, db):
    _, _, nino, token = _preparar(client, db)
    leccion, r = _jugar(client, token, seccion="gramatica")
    assert (leccion["unidad"]["id"], leccion["leccion"]) == ("to-be", 1)
    assert leccion["unidad"]["explicacion"]  # trae la tarjeta "Cómo se usa"
    assert (r.json()["siguiente"]["unidad"], r.json()["siguiente"]["leccion"]) == ("to-be", 2)
    # Vocabulario sigue en su propio inicio: avanzar en gramática no lo mueve.
    resumen = client.get(f"/api/lecciones/resumen/{nino['id_usuario']}", headers=_auth(token)).json()
    assert (resumen["siguiente"]["vocabulario"]["unidad"], resumen["siguiente"]["vocabulario"]["leccion"]) == ("animals", 1)
    assert resumen["por_seccion"]["gramatica"]["aprobadas"] == 1
    assert resumen["por_seccion"]["vocabulario"]["total"] == 55


def test_docente_ve_a_que_horas_estuvo_activo(client, db):
    docente, token_docente, _, token = _preparar(client, db)
    _jugar(client, token)
    _jugar(client, token, seccion="gramatica")
    fila = client.get(f"/api/lecciones/docente/{docente['id_usuario']}", headers=_auth(token_docente)).json()["estudiantes"][0]
    assert len(fila["horas_hoy"]) == 2
    assert fila["ultima_actividad"] is not None


def test_lecciones_de_vocabulario_variadas_y_bien_armadas():
    from app.curriculo import VOCABULARIO, _preguntas_vocabulario

    for unidad in VOCABULARIO:
        lecciones = _preguntas_vocabulario(unidad)
        assert [len(l) for l in lecciones] == [8] * 5
        for leccion in lecciones:
            for p in leccion:
                assert p["respuesta_correcta"] in p["opciones"]
                assert len({o.lower() for o in p["opciones"]}) == len(p["opciones"])
        # Cada lección tiene su propia mezcla de tipos de pregunta (el texto sin la palabra).
        firmas = [frozenset(p["pregunta"].split("“")[0].split("«")[0].split("?")[0][:12] for p in l) for l in lecciones]
        assert len(set(firmas)) == 5, unidad
