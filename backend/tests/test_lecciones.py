"""Camino guiado de lecciones (app/services/lecciones_service.py)."""
from app.services.lecciones_service import sembrar_temario


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _preparar(client, db):
    sembrar_temario(db)
    docente = client.post("/api/usuarios", json={
        "nombre": "Marta", "edad": 40, "rol": "docente", "acudientes_ids": [], "docente_id": None,
        "email": "marta@escuela.co", "acepta_terminos": True,
    }).json()
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
    assert leccion["vidas"] == 3


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


def test_perder_las_tres_vidas_repite_la_leccion(client, db):
    _, _, nino, token = _preparar(client, db)
    _, r = _jugar(client, token, errores=3)
    datos = r.json()
    assert datos["aprobada"] is False and datos["puntos_ganados"] == 0
    assert (datos["siguiente"]["unidad"], datos["siguiente"]["leccion"]) == ("animals", 1)
    assert len(datos["errores"]) == 3


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
    _, _, _, token = _preparar(client, db)
    _jugar(client, token, errores=2)          # animals-1 aprobada con 6/8 (75 %)
    _jugar(client, token)                     # animals-2
    _, r = _jugar(client, token)              # animals-3 → ya van 3 nuevas
    siguiente = r.json()["siguiente"]
    assert siguiente == {"unidad": "animals", "leccion": 1, "modo": "repaso"}


def test_recompensa_al_cruzar_cien_puntos(client, db):
    _, _, _, token = _preparar(client, db)
    _, r1 = _jugar(client, token, errores=1)  # 70 puntos
    assert r1.json()["recompensa_generada"] is None
    _, r2 = _jugar(client, token)             # 150 → cruza 100
    assert r2.json()["recompensa_generada"] is not None


def test_docente_ve_quien_necesita_ayuda_y_por_que(client, db):
    docente, token_docente, nino, token = _preparar(client, db)
    _jugar(client, token, errores=3)
    _jugar(client, token, errores=3)
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
