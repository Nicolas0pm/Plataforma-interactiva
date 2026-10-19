"""
Lee y guarda el progreso de un estudiante repartido en tablas relacionales.

La lógica del camino (`lecciones_service.py`) y de la tienda (`tienda_service.py`) trabaja
con un diccionario de progreso; este módulo lo arma desde las tablas y lo vuelve a guardar:

  progreso            → puntaje, contadores, vidas y perfil de la tienda (una fila)
  progreso_lecciones  → lecciones: { "animals-1": {aprobada, mejor, total, intentos, fallos, ultima} }
  progreso_unidades   → unidades: { "animals": {respuestas, correctas} } y mundos_completados
  progreso_secciones  → aprobadas_desde_repaso: { "vocabulario": n, ... }
  items_comprados     → perfil.comprados
  intentos_leccion    → recientes (los últimos `MAX_RECIENTES`, con sus errores)
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.curriculo import clave_leccion
from app.models.tablas import (
    ErrorIntento,
    IntentoLeccion,
    ItemComprado,
    Progreso,
    ProgresoLeccion,
    ProgresoSeccion,
    ProgresoUnidad,
)

MAX_RECIENTES = 20
_CAMPOS_LECCION = ("aprobada", "mejor", "total", "intentos", "fallos", "ultima")
_CONTADORES = ("puntaje_total", "nivel_logrado", "actividades_completadas", "respuestas_totales", "respuestas_correctas")


def _separar_clave(clave: str) -> tuple[str, int]:
    """ "simple-past-3" → ("simple-past", 3): el número de lección siempre va al final."""
    unidad, numero = clave.rsplit("-", 1)
    return unidad, int(numero)


def _por_usuario(db: Session, modelo, ids: list[str]) -> dict[str, list]:
    filas: dict[str, list] = {i: [] for i in ids}
    for fila in db.scalars(select(modelo).where(modelo.id_usuario.in_(ids))):
        filas[fila.id_usuario].append(fila)
    return filas


def recientes_de(db: Session, ids: list[str], limite: int = MAX_RECIENTES) -> dict[str, list[dict]]:
    """Últimos intentos de cada estudiante (más nuevo primero), en una sola consulta."""
    numerados = (
        select(
            IntentoLeccion.id,
            func.row_number().over(
                partition_by=IntentoLeccion.id_usuario,
                order_by=(IntentoLeccion.fecha.desc(), IntentoLeccion.id.desc()),
            ).label("n"),
        )
        .where(IntentoLeccion.id_usuario.in_(ids))
        .subquery()
    )
    consulta = (
        select(IntentoLeccion)
        .join(numerados, numerados.c.id == IntentoLeccion.id)
        .where(numerados.c.n <= limite)
        .order_by(IntentoLeccion.fecha.desc(), IntentoLeccion.id.desc())
    )
    por_id: dict[str, list[dict]] = {i: [] for i in ids}
    for intento in db.scalars(consulta):
        por_id[intento.id_usuario].append(intento.a_dict())
    return por_id


def leer_progresos_crudos(db: Session, ids: list[str]) -> dict[str, dict]:
    """{id_usuario: progreso} de varios estudiantes con una consulta por tabla (no por niño)."""
    if not ids:
        return {}
    filas = {p.id_usuario: p for p in db.scalars(select(Progreso).where(Progreso.id_usuario.in_(ids)))}
    lecciones = _por_usuario(db, ProgresoLeccion, ids)
    unidades = _por_usuario(db, ProgresoUnidad, ids)
    secciones = _por_usuario(db, ProgresoSeccion, ids)
    items = _por_usuario(db, ItemComprado, ids)
    recientes = recientes_de(db, ids)

    resultado = {}
    for i in ids:
        fila = filas.get(i)
        datos: dict = {c: getattr(fila, c) for c in _CONTADORES} if fila else {}
        if fila:
            datos["actualizado_en"] = fila.actualizado_en
            if fila.vidas_cantidad is not None:
                datos["vidas"] = {"cantidad": fila.vidas_cantidad, "desde": fila.vidas_desde}
            perfil = {"marco": fila.marco, "puntos_gastados": fila.puntos_gastados}
            if fila.avatar:
                perfil["avatar"] = fila.avatar
            if items[i]:
                perfil["comprados"] = [it.item_id for it in sorted(items[i], key=lambda it: it.comprado_en)]
            datos["perfil"] = perfil
        datos["lecciones"] = {
            clave_leccion(l.unidad, l.leccion): {c: getattr(l, c) for c in _CAMPOS_LECCION} for l in lecciones[i]
        }
        datos["unidades"] = {u.unidad: {"respuestas": u.respuestas, "correctas": u.correctas} for u in unidades[i]}
        datos["mundos_completados"] = {u.unidad: u.completado_en for u in unidades[i] if u.completado_en}
        datos["aprobadas_desde_repaso"] = {s.seccion: s.aprobadas_desde_repaso for s in secciones[i]}
        datos["recientes"] = recientes[i]
        resultado[i] = datos
    return resultado


def guardar_progreso_crudo(db: Session, id_usuario: str, progreso: dict) -> None:
    """Escribe el diccionario de progreso en sus tablas (solo inserta o actualiza filas)."""
    fila = db.get(Progreso, id_usuario)
    if fila is None:
        fila = Progreso(id_usuario=id_usuario)
        db.add(fila)
    for campo in _CONTADORES:
        if campo in progreso:
            setattr(fila, campo, progreso[campo])
    if "actualizado_en" in progreso:
        fila.actualizado_en = progreso["actualizado_en"]
    vidas = progreso.get("vidas")
    fila.vidas_cantidad, fila.vidas_desde = (vidas["cantidad"], vidas["desde"]) if vidas else (None, None)

    perfil = progreso.get("perfil") or {}
    fila.avatar = perfil.get("avatar")
    fila.marco = perfil.get("marco")
    fila.puntos_gastados = perfil.get("puntos_gastados", 0)
    tiene = {it.item_id for it in db.scalars(select(ItemComprado).where(ItemComprado.id_usuario == id_usuario))}
    for item_id in perfil.get("comprados", []):
        if item_id not in tiene:
            db.add(ItemComprado(id_usuario=id_usuario, item_id=item_id))
            tiene.add(item_id)

    actuales = {(l.unidad, l.leccion): l for l in db.scalars(select(ProgresoLeccion).where(ProgresoLeccion.id_usuario == id_usuario))}
    for clave, estado in progreso.get("lecciones", {}).items():
        unidad, numero = _separar_clave(clave)
        leccion = actuales.get((unidad, numero))
        if leccion is None:
            leccion = ProgresoLeccion(id_usuario=id_usuario, unidad=unidad, leccion=numero)
            db.add(leccion)
        for campo in _CAMPOS_LECCION:
            if campo in estado:
                setattr(leccion, campo, estado[campo])

    temas = {u.unidad: u for u in db.scalars(select(ProgresoUnidad).where(ProgresoUnidad.id_usuario == id_usuario))}
    completados = progreso.get("mundos_completados", {})
    for unidad in {*progreso.get("unidades", {}), *completados}:
        tema = temas.get(unidad)
        if tema is None:
            tema = ProgresoUnidad(id_usuario=id_usuario, unidad=unidad, respuestas=0, correctas=0)
            db.add(tema)
        conteo = progreso.get("unidades", {}).get(unidad, {})
        tema.respuestas = conteo.get("respuestas", tema.respuestas)
        tema.correctas = conteo.get("correctas", tema.correctas)
        tema.completado_en = completados.get(unidad)

    secciones = {s.seccion: s for s in db.scalars(select(ProgresoSeccion).where(ProgresoSeccion.id_usuario == id_usuario))}
    for seccion, n in progreso.get("aprobadas_desde_repaso", {}).items():
        fila_seccion = secciones.get(seccion)
        if fila_seccion is None:
            db.add(ProgresoSeccion(id_usuario=id_usuario, seccion=seccion, aprobadas_desde_repaso=n))
        else:
            fila_seccion.aprobadas_desde_repaso = n
    db.flush()


def registrar_intento(db: Session, id_usuario: str, intento: dict) -> None:
    """Historial completo de lecciones jugadas, con cada pregunta que respondió mal."""
    db.add(IntentoLeccion(
        id_usuario=id_usuario, unidad=intento["unidad"], seccion=intento["seccion"],
        titulo_es=intento["titulo"]["es"], titulo_en=intento["titulo"]["en"], emoji=intento["emoji"],
        leccion=intento["leccion"], modo=intento["modo"], aciertos=intento["aciertos"], total=intento["total"],
        aprobada=intento["aprobada"], puntos=intento["puntos"], fecha=intento["fecha"],
        errores=[ErrorIntento(**error) for error in intento["errores"]],
    ))
    db.flush()
