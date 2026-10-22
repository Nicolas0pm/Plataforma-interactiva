"""Exámenes cada N mundos (premio físico solo en los mundos del profe) y preguntas del
temario cambiadas por el docente solo para su salón."""
from sqlalchemy import select

from app.models.tablas import Actividad
from test_lecciones import _completar_mundo, _jugar, _preparar
from utilidades import auth, crear_adulto, crear_coordinador, crear_nino, login_nino

MAQUINA = {"X-Device-Secret": "test-device-secret"}


def _configurar(client, docente, token_docente, cada=1, maquina=True):
    if maquina:
        client.put(f"/api/usuarios/docente/{docente['id_usuario']}/dispensador",
                   json={"device_id": "aula-101"}, headers=auth(token_docente))
    r = client.put(f"/api/usuarios/docente/{docente['id_usuario']}/premio",
                   json={"cada_mundos": cada}, headers=auth(token_docente))
    assert r.status_code == 200, r.text


def _mundo_del_profe(client, token_docente, titulo, n=8):
    mundo = client.post("/api/mundos", json={"titulo": titulo}, headers=auth(token_docente)).json()
    for i in range(n):
        r = client.post(f"/api/mundos/{mundo['id_mundo']}/preguntas", headers=auth(token_docente), json={
            "pregunta": f"{titulo} {i}?", "opciones": [f"si{i}", "no"], "respuesta_correcta": f"si{i}"})
        assert r.status_code == 201
    return mundo


def _completar_del_profe(client, token):
    while True:
        _, r = _jugar(client, token, seccion="profesor")
        datos = r.json()
        if datos["mundo_completado"]:
            return datos["mundo_completado"]


def _correctas(db, ids):
    db.commit()
    return {a.id_actividad: a.respuesta_correcta for a in db.scalars(select(Actividad).where(Actividad.id_actividad.in_(ids)))}


def _responder(client, db, token, id_examen, errores=0):
    examen = client.get(f"/api/examenes/{id_examen}", headers=auth(token)).json()
    correctas = _correctas(db, [p["id_actividad"] for p in examen["preguntas"]])
    respuestas = []
    for i, p in enumerate(examen["preguntas"]):
        mala = next(o for o in p["opciones"] if o != correctas[p["id_actividad"]])
        respuestas.append({"id_actividad": p["id_actividad"],
                           "respuesta": mala if i < errores else correctas[p["id_actividad"]]})
    return client.post(f"/api/examenes/{id_examen}/resultado", headers=auth(token), json={"respuestas": respuestas})


def test_examen_de_un_mundo_del_temario_no_da_premio(client, db):
    docente, token_docente, _, token = _preparar(client, db)
    _configurar(client, docente, token_docente, cada=1)
    mundo = _completar_mundo(client, token)[4]["mundo_completado"]
    examen = mundo["examen"]
    assert examen["estado"] == "pendiente" and examen["da_premio"] is False
    assert [m["id"] for m in examen["mundos"]] == ["animals"]

    pendientes = client.get("/api/examenes", headers=auth(token)).json()
    assert [e["id_examen"] for e in pendientes] == [examen["id_examen"]]
    jugar = client.get(f"/api/examenes/{examen['id_examen']}", headers=auth(token)).json()
    assert 0 < len(jugar["preguntas"]) <= 10
    assert all("respuesta_correcta" not in p for p in jugar["preguntas"])  # se califica en el servidor
    db.commit()
    unidades = set(db.scalars(select(Actividad.unidad).where(
        Actividad.id_actividad.in_([p["id_actividad"] for p in jugar["preguntas"]]))))
    assert unidades == {"animals"}

    r = _responder(client, db, token, examen["id_examen"]).json()
    assert r["aprobado"] is True and r["recompensa"] is None
    assert client.get("/api/recompensas/cola/aula-101", headers=MAQUINA).json() == []
    assert client.get("/api/examenes", headers=auth(token)).json()[0]["estado"] == "aprobado"


def test_examen_cada_dos_mundos_del_profe_da_premio_al_aprobar(client, db):
    docente, token_docente, _, token = _preparar(client, db)
    _configurar(client, docente, token_docente, cada=2)
    _mundo_del_profe(client, token_docente, "Frutas")
    _mundo_del_profe(client, token_docente, "Colegio")

    primero = _completar_del_profe(client, token)
    assert primero["examen"] is None and primero["faltan_mundos"] == 1
    segundo = _completar_del_profe(client, token)
    examen = segundo["examen"]
    assert examen["da_premio"] is True and len(examen["mundos"]) == 2
    assert {m["titulo"]["es"] for m in examen["mundos"]} == {"Frutas", "Colegio"}

    # Con menos del 70 % no aprueba ni hay premio; puede repetirlo
    r = _responder(client, db, token, examen["id_examen"], errores=4).json()
    assert r["aprobado"] is False and r["necesarios"] == 7 and len(r["errores"]) == 4
    assert client.get("/api/recompensas/cola/aula-101", headers=MAQUINA).json() == []

    r = _responder(client, db, token, examen["id_examen"], errores=3).json()
    assert r["aprobado"] is True and r["primera_vez"] is True
    assert r["recompensa"]["estado"] == "pendiente" and r["recompensa"]["device_id"] == "aula-101"
    cola = client.get("/api/recompensas/cola/aula-101", headers=MAQUINA).json()
    assert [p["id_historial"] for p in cola] == [r["recompensa"]["id_historial"]]

    # Repetirlo después de aprobado no da otro premio
    otra = _responder(client, db, token, examen["id_examen"]).json()
    assert otra["aprobado"] is True and otra["primera_vez"] is False and otra["recompensa"] is None
    assert len(client.get("/api/recompensas/cola/aula-101", headers=MAQUINA).json()) == 1

    resumen = client.get(f"/api/lecciones/docente/{docente['id_usuario']}", headers=auth(token_docente)).json()
    assert resumen["premio_cada_mundos"] == 2


def test_examen_solo_lo_ve_y_responde_su_estudiante(client, db):
    docente, token_docente, _, token = _preparar(client, db)
    examen = _completar_mundo(client, token)[4]["mundo_completado"]["examen"]
    _, token_coord = crear_coordinador("coord2")
    otro = crear_nino(client, token_coord, nombre="Leo", docente_id=docente["id_usuario"])
    token_otro = login_nino(client, otro)
    assert client.get(f"/api/examenes/{examen['id_examen']}", headers=auth(token_otro)).status_code == 404
    assert client.get(f"/api/examenes/{examen['id_examen']}", headers=auth(token_docente)).status_code == 403
    ajena = {"respuestas": [{"id_actividad": "colors-1-1", "respuesta": "x"}]}
    assert client.post(f"/api/examenes/{examen['id_examen']}/resultado", headers=auth(token), json=ajena).status_code == 400


def test_docente_cambia_y_oculta_preguntas_del_temario_solo_en_su_salon(client, db):
    docente, token_docente, _, token = _preparar(client, db)
    animals = client.get("/api/temario/salon/animals/preguntas", headers=auth(token_docente)).json()
    leccion1 = animals["lecciones"][0]["preguntas"]
    assert len(leccion1) == 8 and all(p["visible"] and not p["editada"] for p in leccion1)
    primera = leccion1[0]["id_actividad"]

    nueva = {"pregunta": "¿Cuál es el animal de la clase?", "opciones": ["Perro", "Gato", "Pez"], "respuesta_correcta": "Pez"}
    assert client.put(f"/api/temario/salon/preguntas/{primera}", json=nueva, headers=auth(token_docente)).status_code == 200
    assert client.patch(f"/api/temario/salon/preguntas/{leccion1[1]['id_actividad']}", json={"activo": False},
                        headers=auth(token_docente)).status_code == 200

    # El niño del salón ve la pregunta cambiada y una menos, y se califica con la respuesta nueva
    leccion = client.get("/api/lecciones/jugar", headers=auth(token)).json()
    assert len(leccion["preguntas"]) == 7
    cambiada = next(p for p in leccion["preguntas"] if p["id_actividad"] == primera)
    assert cambiada["pregunta"] == nueva["pregunta"] and cambiada["respuesta_correcta"] == "Pez"
    _, r = _jugar(client, token)
    assert r.json()["aciertos"] == 7

    # Otro salón sigue viendo el temario original
    _, token_coord = crear_coordinador("coord2")
    otro_docente, _ = crear_adulto(client, token_coord, "docente", "jrestrepo")
    otro = crear_nino(client, token_coord, nombre="Leo", docente_id=otro_docente["id_usuario"])
    original = client.get("/api/lecciones/jugar", headers=auth(login_nino(client, otro))).json()
    assert len(original["preguntas"]) == 8
    assert next(p for p in original["preguntas"] if p["id_actividad"] == primera)["pregunta"] != nueva["pregunta"]

    # Cada lección conserva al menos 4 preguntas
    for p in leccion1[2:5]:
        assert client.patch(f"/api/temario/salon/preguntas/{p['id_actividad']}", json={"activo": False},
                            headers=auth(token_docente)).status_code == 200
    assert client.patch(f"/api/temario/salon/preguntas/{leccion1[5]['id_actividad']}", json={"activo": False},
                        headers=auth(token_docente)).status_code == 400

    # Restaurar deja la pregunta original
    assert client.delete(f"/api/temario/salon/preguntas/{primera}", headers=auth(token_docente)).status_code == 200
    vista = client.get("/api/temario/salon/animals/preguntas", headers=auth(token_docente)).json()
    restaurada = vista["lecciones"][0]["preguntas"][0]
    assert restaurada["visible"] and not restaurada["editada"] and restaurada["pregunta"] != nueva["pregunta"]


def test_editar_preguntas_del_temario_valida_y_exige_docente(client, db):
    _, token_docente, _, token = _preparar(client, db)
    url = "/api/temario/salon/preguntas/animals-1-1"
    mala = {"pregunta": "x", "opciones": ["a", "b"], "respuesta_correcta": "c"}
    db.commit()
    id_real = db.scalar(select(Actividad.id_actividad).where(Actividad.unidad == "animals").limit(1))
    url = f"/api/temario/salon/preguntas/{id_real}"
    assert client.put(url, json=mala, headers=auth(token_docente)).status_code == 422
    buena = {"pregunta": "x", "opciones": ["a", "b"], "respuesta_correcta": "a"}
    assert client.put(url, json=buena, headers=auth(token)).status_code == 403
    assert client.put("/api/temario/salon/preguntas/no-existe", json=buena, headers=auth(token_docente)).status_code == 404
    assert client.get("/api/temario/salon/historia/preguntas", headers=auth(token_docente)).status_code == 404
