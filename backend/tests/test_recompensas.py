from sqlalchemy import select

from app.models.tablas import Auditoria, Usuario
from app.services.recompensas_service import evaluar_recompensa


def _crear_estudiante(db, id_usuario="est1", device_id=None):
    db.add(Usuario(id_usuario=id_usuario, nombre="Ana", edad=7, rol="estudiante", activo=True, device_id=device_id))
    db.flush()


def test_no_genera_recompensa_bajo_el_umbral(db):
    _crear_estudiante(db)
    assert evaluar_recompensa(db, "est1", 40) is None


def test_genera_recompensa_justo_al_cruzar_el_umbral(db):
    _crear_estudiante(db)
    recompensa = evaluar_recompensa(db, "est1", 100)
    assert recompensa is not None
    assert recompensa["estado"] == "pendiente"
    assert recompensa["puntos_consumidos"] == 100


def test_no_genera_recompensa_extra_entre_umbrales(db):
    _crear_estudiante(db)
    assert evaluar_recompensa(db, "est1", 150) is None  # no es múltiplo exacto del umbral (100)


def test_genera_segunda_recompensa_en_el_siguiente_multiplo(db):
    _crear_estudiante(db)
    assert evaluar_recompensa(db, "est1", 200) is not None


def test_recompensa_generada_queda_registrada_en_auditoria(db):
    _crear_estudiante(db)
    evaluar_recompensa(db, "est1", 100)
    db.flush()
    registros = list(db.scalars(select(Auditoria).where(Auditoria.tipo == "recompensa_generada")))
    assert len(registros) == 1
    assert registros[0].actor == "est1"


def test_recompensa_sin_dispensador_sincronizado_no_trae_device_id(db):
    """Un estudiante sin dispensador (device_id) asignado igual gana la recompensa,
    pero el frontend usa este campo para no prometerle un premio físico inexistente."""
    _crear_estudiante(db)  # sin device_id
    recompensa = evaluar_recompensa(db, "est1", 100)
    assert recompensa["device_id"] is None


def test_recompensa_con_dispensador_sincronizado_trae_su_device_id(db):
    _crear_estudiante(db, device_id="aula-101")
    recompensa = evaluar_recompensa(db, "est1", 100)
    assert recompensa["device_id"] == "aula-101"
