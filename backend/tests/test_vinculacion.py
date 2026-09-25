import pytest
from fastapi import HTTPException

from app.services.auth_service import hash_pin
from app.services.estudiantes_service import MAX_FALLOS
from app.services.vinculacion_service import vincular_con_pin


def _crear_estudiante(db, id_usuario="est1", codigo="ABC234", pin="1234"):
    db.collection("usuarios").document(id_usuario).set(
        {"nombre": "Ana", "edad": 7, "rol": "estudiante", "acudientes_ids": [], "activo": True,
         "codigo_acceso": codigo, "pin_hash": hash_pin(pin)}
    )


DOCENTE = {"id_usuario": "doc1", "rol": "docente"}
PADRE = {"id_usuario": "padre1", "rol": "padre"}


def test_vincula_al_padre_con_codigo_y_pin(db):
    _crear_estudiante(db)
    resultado = vincular_con_pin("abc234", "1234", PADRE)

    assert resultado["id_usuario"] == "est1"
    assert "pin_hash" not in resultado
    estudiante = db.collection("usuarios").document("est1").get().to_dict()
    assert estudiante["acudientes_ids"] == ["padre1"]


def test_vincula_al_docente_con_codigo_y_pin(db):
    _crear_estudiante(db)
    vincular_con_pin("ABC234", "1234", DOCENTE)

    estudiante = db.collection("usuarios").document("est1").get().to_dict()
    assert estudiante["docente_id"] == "doc1"


def test_un_estudiante_puede_tener_varios_padres(db):
    _crear_estudiante(db)
    vincular_con_pin("ABC234", "1234", PADRE)
    vincular_con_pin("ABC234", "1234", {"id_usuario": "padre2", "rol": "padre"})
    vincular_con_pin("ABC234", "1234", PADRE)  # repetir no duplica

    estudiante = db.collection("usuarios").document("est1").get().to_dict()
    assert estudiante["acudientes_ids"] == ["padre1", "padre2"]


def test_pin_incorrecto_no_vincula(db):
    _crear_estudiante(db)
    with pytest.raises(HTTPException) as exc:
        vincular_con_pin("ABC234", "9999", PADRE)
    assert exc.value.status_code == 401
    assert db.collection("usuarios").document("est1").get().to_dict()["acudientes_ids"] == []


def test_codigo_se_bloquea_tras_varios_fallos(db):
    _crear_estudiante(db)
    for _ in range(MAX_FALLOS):
        with pytest.raises(HTTPException):
            vincular_con_pin("ABC234", "0000", PADRE)

    # Bloqueado: ni siquiera el PIN correcto funciona hasta que pase el tiempo
    with pytest.raises(HTTPException) as exc:
        vincular_con_pin("ABC234", "1234", PADRE)
    assert exc.value.status_code == 429
