import pytest
from fastapi import HTTPException

from app.models.tablas import Usuario
from app.services.auth_service import hash_pin
from app.services.auth_service import MAX_FALLOS
from app.services.vinculacion_service import vincular_con_pin


def _crear_estudiante(db, id_usuario="est1", codigo="ABC234", pin="1234"):
    db.add_all([
        Usuario(id_usuario="doc1", nombre="Marta", edad=40, rol="docente"),
        Usuario(id_usuario="padre1", nombre="Carlos", edad=40, rol="padre"),
        Usuario(id_usuario="padre2", nombre="Lucía", edad=40, rol="padre"),
        Usuario(id_usuario=id_usuario, nombre="Ana", edad=7, rol="estudiante", activo=True,
                codigo_acceso=codigo, pin_hash=hash_pin(pin)),
    ])
    db.flush()


def _estudiante(db, id_usuario="est1") -> Usuario:
    db.flush()
    return db.get(Usuario, id_usuario)


DOCENTE = {"id_usuario": "doc1", "rol": "docente"}
PADRE = {"id_usuario": "padre1", "rol": "padre"}


def test_vincula_al_padre_con_codigo_y_pin(db):
    _crear_estudiante(db)
    resultado = vincular_con_pin(db, "abc234", "1234", PADRE)

    assert resultado["id_usuario"] == "est1"
    assert "pin_hash" not in resultado
    assert _estudiante(db).acudientes_ids == ["padre1"]


def test_vincula_al_docente_con_codigo_y_pin(db):
    _crear_estudiante(db)
    vincular_con_pin(db, "ABC234", "1234", DOCENTE)

    assert _estudiante(db).docente_id == "doc1"


def test_un_estudiante_puede_tener_varios_padres(db):
    _crear_estudiante(db)
    vincular_con_pin(db, "ABC234", "1234", PADRE)
    vincular_con_pin(db, "ABC234", "1234", {"id_usuario": "padre2", "rol": "padre"})
    vincular_con_pin(db, "ABC234", "1234", PADRE)  # repetir no duplica

    assert _estudiante(db).acudientes_ids == ["padre1", "padre2"]


def test_pin_incorrecto_no_vincula(db):
    _crear_estudiante(db)
    with pytest.raises(HTTPException) as exc:
        vincular_con_pin(db, "ABC234", "9999", PADRE)
    assert exc.value.status_code == 401
    assert _estudiante(db).acudientes_ids == []


def test_codigo_se_bloquea_tras_varios_fallos(db):
    _crear_estudiante(db)
    for _ in range(MAX_FALLOS):
        with pytest.raises(HTTPException):
            vincular_con_pin(db, "ABC234", "0000", PADRE)

    # Bloqueado: ni siquiera el PIN correcto funciona hasta que pase el tiempo
    with pytest.raises(HTTPException) as exc:
        vincular_con_pin(db, "ABC234", "1234", PADRE)
    assert exc.value.status_code == 429
