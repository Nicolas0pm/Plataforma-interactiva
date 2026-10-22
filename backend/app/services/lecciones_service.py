"""
Camino de aprendizaje guiado (estilo Duolingo).

- Hay tres apartados: **vocabulario**, **gramática** y **del profe** (mundos que crea el
  docente del estudiante, ver `catalogo_service.py`). El niño elige el apartado; dentro de
  él NO elige lecciones nuevas: `siguiente_leccion()` decide. Normalmente es la primera que
  aún no aprueba; pero cada `REPASO_CADA` lecciones nuevas de ese apartado, si hay alguna
  aprobada con menos del 80 % de aciertos, le toca un **repaso** de la más débil. Solo se
  repasa una lección si pasó al menos `ESPERA_REPASO` desde su último intento (repasar
  justo la que acaba de hacer parecería que no se guardó).
- Sí puede **repetir** lecciones que ya aprobó (modo "practica"): cuenta para su precisión
  y su mejor resultado, pero no da puntos.
- **Vidas** (`VIDAS_MAX`): se guardan entre lecciones y cada error gasta una. Si se
  queda sin vidas a mitad de una lección, la pierde; si la termina con al menos una vida,
  la aprueba. Se recupera una vida cada `MINUTOS_POR_VIDA` minutos. Con 0 vidas no puede
  empezar lecciones nuevas ni repasos, pero sí **practicar** (repetir una ya aprobada):
  practicar no gasta vidas y, si la aprueba, le devuelve una.
- El servidor califica comparando las respuestas con las correctas guardadas en la base de datos.
- **Premios**: los puntos se gastan en la tienda del perfil (`tienda_service.py`). Completar
  un mundo (todas sus lecciones) deja el logro y, cada N mundos de un apartado, arma un
  **examen** de esos mundos (`examenes_service.py`). El premio físico llega al aprobar el
  examen de los mundos del profe.

El progreso se maneja como un diccionario que `progreso_db.py` arma desde sus tablas:
  lecciones: { "animals-1": {aprobada, mejor, total, intentos, fallos, ultima} }
  unidades:  { "animals": {respuestas, correctas} }      # precisión por tema
  respuestas_totales, respuestas_correctas
  aprobadas_desde_repaso: { "vocabulario": n, "gramatica": n, "profesor": n }
  mundos_completados: { "animals": fecha }
  vidas: { cantidad, desde }   # vidas en el instante `desde` (None si están llenas)
  recientes: [ últimos intentos ]
Cada intento queda en la tabla `intentos_leccion` (y sus errores en `errores_intento`), que
es lo que ve el docente como "en qué va bien y en qué va mal".
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.curriculo import MINUTOS_POR_VIDA, PUNTOS_POR_ACIERTO, SECCIONES, VIDAS_MAX, clave_leccion
from app.services.catalogo_service import (
    SECCION_PROFESOR,
    SECCIONES_TODAS,
    buscar_unidad,
    catalogo,
    lecciones_de,
    preguntas_de_leccion,
)
from app.models.tablas import Actividad, Usuario
from app.services.progreso_db import MAX_RECIENTES, guardar_progreso_crudo, leer_progresos_crudos, registrar_intento
from app.services.progreso_service import calcular_nivel, puntos_para_siguiente_nivel
from app.services.examenes_service import examenes_de, nuevo_examen_si_toca
from app.services.recompensas_service import logro_de_mundo

REPASO_CADA = 3
ESPERA_REPASO = timedelta(hours=1)
UMBRAL_REPASO = 0.8


RECARGA = timedelta(minutes=MINUTOS_POR_VIDA)


def _como_utc(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _vidas_ahora(progreso: dict, ahora: datetime) -> tuple[int, datetime | None]:
    """(vidas que tiene ahora, desde cuándo corre la recarga de la siguiente)."""
    guardadas = progreso.get("vidas") or {}
    cantidad = guardadas.get("cantidad", VIDAS_MAX)
    desde = guardadas.get("desde")
    if cantidad >= VIDAS_MAX or desde is None:
        return VIDAS_MAX, None
    desde = _como_utc(desde)
    recargadas = int((ahora - desde) / RECARGA)
    cantidad = min(VIDAS_MAX, cantidad + recargadas)
    if cantidad >= VIDAS_MAX:
        return VIDAS_MAX, None
    return cantidad, desde + recargadas * RECARGA


def estado_vidas(progreso: dict, ahora: datetime | None = None) -> dict:
    """Lo que ven el niño y el frontend: cuántas tiene y cuándo llega la próxima."""
    actuales, desde = _vidas_ahora(progreso, ahora or datetime.now(timezone.utc))
    return {
        "actuales": actuales,
        "maximo": VIDAS_MAX,
        "minutos_por_vida": MINUTOS_POR_VIDA,
        "proxima_vida": desde + RECARGA if desde else None,
    }


def _sin_vidas(progreso: dict, ahora: datetime) -> HTTPException:
    proxima = estado_vidas(progreso, ahora)["proxima_vida"]
    minutos = max(1, -(-int((proxima - ahora).total_seconds()) // 60))
    return HTTPException(409, f"Te quedaste sin vidas ❤️. La próxima llega en {minutos} min. "
                              "Mientras tanto puedes practicar una lección que ya aprobaste.")


def leer_progreso(db: Session, id_usuario: str) -> dict:
    return leer_progresos(db, [id_usuario])[id_usuario]


def guardar_progreso(db: Session, id_usuario: str, progreso: dict) -> None:
    guardar_progreso_crudo(db, id_usuario, progreso)


def _completar_progreso(datos: dict | None) -> dict:
    datos = dict(datos or {})
    datos.setdefault("puntaje_total", 0)
    datos.setdefault("actividades_completadas", 0)
    datos.setdefault("lecciones", {})
    datos.setdefault("unidades", {})
    datos.setdefault("respuestas_totales", 0)
    datos.setdefault("respuestas_correctas", 0)
    datos.setdefault("mundos_completados", {})
    contador = datos.get("aprobadas_desde_repaso", {})
    if not isinstance(contador, dict):  # progreso guardado antes de separar los apartados
        contador = {"vocabulario": contador}
    datos["aprobadas_desde_repaso"] = {s: contador.get(s, 0) for s in SECCIONES_TODAS}
    datos.setdefault("recientes", [])
    return datos


def leer_progresos(db: Session, ids: list[str]) -> dict[str, dict]:
    """Progreso de varios estudiantes con una consulta por tabla (panel del docente)."""
    return {i: _completar_progreso(datos) for i, datos in leer_progresos_crudos(db, ids).items()}


def _proporcion(estado: dict) -> float:
    return estado.get("mejor", 0) / estado["total"] if estado.get("total") else 0.0


def _jugada_despues(estado: dict, fecha: datetime) -> bool:
    ultima = estado.get("ultima")
    return ultima is not None and _como_utc(ultima) > fecha


def siguiente_leccion(progreso: dict, cat: dict, seccion: str) -> dict | None:
    """La lección que le toca en ese apartado: {unidad, leccion, modo: "nueva" | "repaso"}."""
    lecciones = progreso["lecciones"]
    orden = lecciones_de(cat, seccion)
    pendiente = next(
        ((u, n) for u, n in orden if not lecciones.get(clave_leccion(u, n), {}).get("aprobada")), None
    )
    hace_poco = datetime.now(timezone.utc) - ESPERA_REPASO
    debiles = sorted(
        (_proporcion(lecciones[clave_leccion(u, n)]), u, n)
        for u, n in orden
        if lecciones.get(clave_leccion(u, n), {}).get("aprobada")
        and _proporcion(lecciones[clave_leccion(u, n)]) < UMBRAL_REPASO
        and not _jugada_despues(lecciones[clave_leccion(u, n)], hace_poco)
    )
    toca_repaso = progreso["aprobadas_desde_repaso"][seccion] >= REPASO_CADA or pendiente is None
    if toca_repaso and debiles:
        _, unidad, numero = debiles[0]
        return {"unidad": unidad, "leccion": numero, "modo": "repaso"}
    if pendiente:
        return {"unidad": pendiente[0], "leccion": pendiente[1], "modo": "nueva"}
    return None  # terminó ese apartado y no tiene nada débil


def modo_para(progreso: dict, cat: dict, unidad: str, leccion: int) -> str:
    """Decide si el niño puede jugar esa lección y en qué modo, o lanza 403/404."""
    info = buscar_unidad(cat, unidad)
    if info is None or not 1 <= leccion <= info["lecciones"]:
        raise HTTPException(404, "No existe esa lección")
    siguiente = siguiente_leccion(progreso, cat, info["seccion"])
    if siguiente and siguiente["unidad"] == unidad and siguiente["leccion"] == leccion:
        return siguiente["modo"]
    if progreso["lecciones"].get(clave_leccion(unidad, leccion), {}).get("aprobada"):
        return "practica"
    raise HTTPException(403, "Esa lección todavía no está desbloqueada")


def _docente_id(db: Session, id_usuario: str) -> str | None:
    return db.scalar(select(Usuario.docente_id).where(Usuario.id_usuario == id_usuario))


def _preguntas(db: Session, unidad: str, leccion: int, id_docente: str | None) -> list[dict]:
    preguntas = preguntas_de_leccion(db, unidad, leccion, id_docente)
    if not preguntas:
        raise HTTPException(404, "Esta lección no tiene preguntas cargadas")
    return preguntas


def armar_leccion(
    db: Session, id_usuario: str, unidad: str | None, leccion: int | None, seccion: str = "vocabulario"
) -> dict:
    progreso = leer_progreso(db, id_usuario)
    cat = catalogo(db, id_usuario)
    if unidad is None or leccion is None:
        if seccion not in cat:
            raise HTTPException(404, "No existe ese apartado")
        siguiente = siguiente_leccion(progreso, cat, seccion)
        if siguiente is None:
            raise HTTPException(404, "¡Terminaste todo este apartado!")
        unidad, leccion = siguiente["unidad"], siguiente["leccion"]
    modo = modo_para(progreso, cat, unidad, leccion)
    ahora = datetime.now(timezone.utc)
    vidas, _ = _vidas_ahora(progreso, ahora)
    if modo != "practica" and vidas == 0:
        raise _sin_vidas(progreso, ahora)
    return {
        "unidad": buscar_unidad(cat, unidad),
        "leccion": leccion,
        "modo": modo,
        # Practicar no gasta vidas: se juega con todas.
        "vidas": VIDAS_MAX if modo == "practica" else vidas,
        "vidas_max": VIDAS_MAX,
        "preguntas": [
            {
                "id_actividad": p["id_actividad"],
                "pregunta": p.get("pregunta"),
                "opciones": p.get("opciones", []),
                # Se envía para dar el feedback inmediato; la nota final la calcula el servidor.
                "respuesta_correcta": p.get("respuesta_correcta"),
                "icono": p.get("icono"),
                "imagen": p.get("imagen"),  # solo las preguntas de los mundos del profe
                "formato_opciones": p.get("formato_opciones", "texto"),
            }
            for p in _preguntas(db, unidad, leccion, _docente_id(db, id_usuario))
        ],
    }


def registrar_resultado(db: Session, id_usuario: str, unidad: str, leccion: int, respuestas: list[dict]) -> dict:
    progreso = leer_progreso(db, id_usuario)
    cat = catalogo(db, id_usuario)
    modo = modo_para(progreso, cat, unidad, leccion)
    info = buscar_unidad(cat, unidad)
    seccion = info["seccion"]
    ahora = datetime.now(timezone.utc)
    vidas, recarga_desde = _vidas_ahora(progreso, ahora)
    if modo != "practica" and vidas == 0:
        raise _sin_vidas(progreso, ahora)
    vidas_al_empezar = VIDAS_MAX if modo == "practica" else vidas
    preguntas = {p["id_actividad"]: p for p in _preguntas(db, unidad, leccion, _docente_id(db, id_usuario))}

    ids = [r["id_actividad"] for r in respuestas]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Cada pregunta se responde una sola vez")

    aciertos = 0
    errores = []
    for r in respuestas:
        pregunta = preguntas.get(r["id_actividad"])
        if pregunta is None:
            raise HTTPException(400, "Una de las respuestas no pertenece a esta lección")
        if r["respuesta"] == pregunta.get("respuesta_correcta"):
            aciertos += 1
        else:
            errores.append({
                "id_actividad": r["id_actividad"],
                "pregunta": pregunta.get("pregunta"),
                "icono": pregunta.get("icono"),
                "respuesta_dada": r["respuesta"],
                "respuesta_correcta": pregunta.get("respuesta_correcta"),
            })

    total = len(preguntas)
    aprobada = len(errores) < vidas_al_empezar and aciertos + len(errores) >= total

    # --- Vidas: cada error gasta una; practicar no gasta y, si aprueba, devuelve una ---
    if modo == "practica":
        nuevas = min(VIDAS_MAX, vidas + (1 if aprobada else 0))
    else:
        nuevas = max(0, vidas - len(errores))
    # La recarga corre desde que dejó de tener todas (si ya corría, sigue igual).
    progreso["vidas"] = {"cantidad": nuevas, "desde": None if nuevas >= VIDAS_MAX else (recarga_desde or ahora)}

    # --- Progreso por lección ---
    clave = clave_leccion(unidad, leccion)
    estado = dict(progreso["lecciones"].get(clave, {}))
    estado["total"] = total
    estado["intentos"] = estado.get("intentos", 0) + 1
    estado["ultima"] = ahora
    if aprobada:
        estado["aprobada"] = True
        estado["mejor"] = max(estado.get("mejor", 0), aciertos)
        estado["fallos"] = 0
    else:
        estado.setdefault("aprobada", False)
        estado.setdefault("mejor", 0)
        estado["fallos"] = estado.get("fallos", 0) + 1
    progreso["lecciones"][clave] = estado

    # --- Precisión general y por tema ---
    respondidas = aciertos + len(errores)
    progreso["respuestas_totales"] += respondidas
    progreso["respuestas_correctas"] += aciertos
    por_unidad = dict(progreso["unidades"].get(unidad, {}))
    por_unidad["respuestas"] = por_unidad.get("respuestas", 0) + respondidas
    por_unidad["correctas"] = por_unidad.get("correctas", 0) + aciertos
    progreso["unidades"][unidad] = por_unidad

    # --- Puntos (para la tienda): solo lecciones nuevas y repasos aprobados ---
    puntos = aciertos * PUNTOS_POR_ACIERTO if aprobada and modo != "practica" else 0
    anterior = progreso["puntaje_total"]
    nivel_anterior = calcular_nivel(anterior)
    progreso["puntaje_total"] = anterior + puntos
    progreso["actividades_completadas"] += respondidas
    if aprobada and modo == "nueva":
        progreso["aprobadas_desde_repaso"][seccion] += 1
    elif aprobada and modo == "repaso":
        progreso["aprobadas_desde_repaso"][seccion] = 0

    # --- ¿Completó el mundo? (primera vez que aprueba todas sus lecciones) ---
    mundo_completado = None
    todas = all(
        progreso["lecciones"].get(clave_leccion(unidad, n), {}).get("aprobada")
        for n in range(1, info["lecciones"] + 1)
    )
    if aprobada and todas and unidad not in progreso["mundos_completados"]:
        progreso["mundos_completados"][unidad] = ahora
        mundo_completado = {
            "unidad": unidad,
            "titulo": info["titulo"],
            "emoji": info["emoji"],
            "recompensa": logro_de_mundo(db, id_usuario, info),
            # Cada N mundos del apartado: examen de esos mundos (o cuántos faltan).
            **nuevo_examen_si_toca(db, id_usuario, seccion, progreso, cat),
        }

    nuevo_nivel = calcular_nivel(progreso["puntaje_total"])
    progreso["nivel_logrado"] = nuevo_nivel
    progreso["actualizado_en"] = ahora
    intento = {
        "unidad": unidad,
        "seccion": seccion,
        "titulo": info["titulo"],
        "emoji": info["emoji"],
        "leccion": leccion,
        "modo": modo,
        "aciertos": aciertos,
        "total": total,
        "errores": errores,
        "aprobada": aprobada,
        "puntos": puntos,
        "fecha": ahora,
    }
    # Los últimos intentos viajan dentro del progreso: el resumen no necesita otra consulta.
    progreso["recientes"] = [intento, *progreso.get("recientes", [])][:MAX_RECIENTES]
    guardar_progreso(db, id_usuario, progreso)

    # Historial completo (auditoría / análisis de la prueba piloto).
    registrar_intento(db, id_usuario, intento)

    return {
        "aprobada": aprobada,
        "modo": modo,
        "aciertos": aciertos,
        "total": total,
        "errores": errores,
        "puntos_ganados": puntos,
        "puntaje_total": progreso["puntaje_total"],
        "nivel_logrado": nuevo_nivel,
        "subio_de_nivel": nuevo_nivel > nivel_anterior,
        "mundo_completado": mundo_completado,
        "siguiente": siguiente_leccion(progreso, cat, seccion),
        "vidas": estado_vidas(progreso, ahora),
        "vida_recuperada": modo == "practica" and nuevas > vidas,
    }


def resumen_aprendizaje(db: Session, id_usuario: str, progreso: dict | None = None, cat: dict | None = None,
                        con_examenes: bool = True) -> dict:
    """Caminos con estados + estadísticas. Lo usan el niño, su docente y sus padres.
    El panel del docente pasa `progreso` y `cat` ya consultados para no repetir lecturas."""
    from app.services.tienda_service import perfil_de

    if progreso is None:
        progreso = leer_progreso(db, id_usuario)
    if cat is None:
        cat = catalogo(db, id_usuario)
    siguientes = {sec: siguiente_leccion(progreso, cat, sec) for sec in cat}
    lecciones = progreso["lecciones"]

    unidades = []
    for seccion, lista in cat.items():
        siguiente = siguientes[seccion]
        for info in lista:
            unidad = info["id"]
            estados = []
            for numero in range(1, info["lecciones"] + 1):
                estado = lecciones.get(clave_leccion(unidad, numero), {})
                if siguiente and (siguiente["unidad"], siguiente["leccion"]) == (unidad, numero):
                    situacion = "actual"
                elif estado.get("aprobada"):
                    situacion = "aprobada"
                else:
                    situacion = "bloqueada"
                estados.append({
                    "numero": numero,
                    "estado": situacion,
                    "aprobada": bool(estado.get("aprobada")),
                    "mejor": estado.get("mejor", 0),
                    "total": estado.get("total", 0),
                    "intentos": estado.get("intentos", 0),
                    "fallos": estado.get("fallos", 0),
                })
            por_unidad = progreso["unidades"].get(unidad, {})
            unidades.append({
                **{k: info[k] for k in ("id", "seccion", "titulo", "emoji")},
                "descripcion": info.get("descripcion", ""),
                "lecciones": estados,
                "aprobadas": sum(1 for e in estados if e["aprobada"]),
                "completado": unidad in progreso["mundos_completados"],
                "precision": round(por_unidad["correctas"] / por_unidad["respuestas"], 2)
                if por_unidad.get("respuestas") else None,
            })

    recientes = progreso["recientes"]
    conteo_errores: dict[str, dict] = {}
    for intento in recientes:
        for error in intento.get("errores", []):
            item = conteo_errores.setdefault(error["id_actividad"], {**error, "veces": 0, "unidad": intento["unidad"]})
            item["veces"] += 1

    def _titulo_intento(intento):
        info = buscar_unidad(cat, intento["unidad"])
        return (
            (info or {}).get("titulo") or intento.get("titulo") or {"es": intento["unidad"], "en": intento["unidad"]},
            (info or {}).get("emoji") or intento.get("emoji") or "🌟",
        )

    por_seccion = {
        sec: {
            "aprobadas": sum(1 for u, n in lecciones_de(cat, sec) if lecciones.get(clave_leccion(u, n), {}).get("aprobada")),
            "total": len(lecciones_de(cat, sec)),
        }
        for sec in cat
    }
    total_lecciones = len(lecciones_de(cat))
    return {
        "secciones": [*SECCIONES, {"id": SECCION_PROFESOR, "titulo": {"es": "Del profe", "en": "From my teacher"}, "emoji": "👩‍🏫"}],
        "unidades": unidades,
        # La próxima lección de cada apartado (el niño elige el apartado; la lección, no).
        "siguiente": {
            sec: {**sig, "info": buscar_unidad(cat, sig["unidad"])} if sig else None
            for sec, sig in siguientes.items()
        },
        "por_seccion": por_seccion,
        "lecciones_aprobadas": sum(s["aprobadas"] for s in por_seccion.values()),
        "total_lecciones": total_lecciones,
        "mundos_completados": len(progreso["mundos_completados"]),
        "precision": round(progreso["respuestas_correctas"] / progreso["respuestas_totales"], 2)
        if progreso["respuestas_totales"] else None,
        "puntaje_total": progreso["puntaje_total"],
        "vidas": estado_vidas(progreso),
        "perfil": perfil_de(progreso),
        "nivel_logrado": calcular_nivel(progreso["puntaje_total"]),
        "puntos_para_siguiente_nivel": puntos_para_siguiente_nivel(progreso["puntaje_total"]),
        # Última lección jugada (no la fecha de registro): define "activo hoy" y "sin practicar".
        "ultima_actividad": recientes[0]["fecha"] if recientes else None,
        # Hora de cada intento reciente: el docente ve a qué horas estuvo activo.
        "actividad": [i["fecha"] for i in recientes],
        "recientes": [
            {k: i[k] for k in ("unidad", "leccion", "modo", "aciertos", "total", "aprobada", "puntos", "fecha")}
            | {"errores": len(i.get("errores", [])), "titulo": _titulo_intento(i)[0], "emoji": _titulo_intento(i)[1]}
            for i in recientes[:8]
        ],
        "errores_frecuentes": sorted(conteo_errores.values(), key=lambda e: -e["veces"])[:8],
        # El panel de todo el salón no los necesita (y se ahorra una consulta por niño).
        "examenes": examenes_de(db, id_usuario, cat) if con_examenes else [],
    }


def motivos_de_ayuda(resumen: dict, ahora: datetime) -> list[str]:
    """Por qué un estudiante necesita ayuda (se muestra al docente)."""
    motivos = []
    if resumen["precision"] is not None and resumen["precision"] < 0.6:
        motivos.append(f"Precisión baja: {round(resumen['precision'] * 100)} %")
    for unidad in resumen["unidades"]:
        for leccion in unidad["lecciones"]:
            if leccion["fallos"] >= 2 and leccion["estado"] != "aprobada":
                motivos.append(f"Perdió {leccion['fallos']} veces seguidas: {unidad['titulo']['es']} · lección {leccion['numero']}")
        if unidad["precision"] is not None and unidad["precision"] < 0.5:
            motivos.append(f"Le cuesta {unidad['titulo']['es']} ({round(unidad['precision'] * 100)} % de aciertos)")
    ultima = resumen.get("ultima_actividad")
    if ultima is not None:
        if ultima.tzinfo is None:
            ultima = ultima.replace(tzinfo=timezone.utc)
        if (ahora - ultima).days >= 7:
            motivos.append(f"Sin practicar hace {(ahora - ultima).days} días")
    return motivos


def sembrar_temario(db: Session) -> dict:
    """Carga el temario de `app/curriculo.py` en la tabla `actividades`. Es idempotente: cada
    pregunta usa un ID fijo ("animals-1-1"), así que volver a correrlo actualiza en vez de
    duplicar. Las actividades antiguas sin unidad (catálogo anterior) quedan desactivadas."""
    from app.curriculo import generar_actividades

    desactivadas = 0
    for actividad in db.scalars(select(Actividad).where(Actividad.activo, Actividad.unidad.is_(None))):
        actividad.activo = False
        desactivadas += 1
    actividades = generar_actividades()
    existentes = {a.id_actividad: a for a in db.scalars(select(Actividad).where(Actividad.id_mundo.is_(None)))}
    for datos in actividades:
        fila = existentes.get(datos["nombre"])
        if fila is None:
            fila = Actividad(id_actividad=datos["nombre"])
            db.add(fila)
        for campo, valor in datos.items():
            setattr(fila, campo, valor)
    db.flush()
    return {"creadas_o_actualizadas": len(actividades), "antiguas_desactivadas": desactivadas}


def temario_cargado(db: Session) -> bool:
    return db.scalar(select(Actividad.id_actividad).where(Actividad.seccion == "vocabulario").limit(1)) is not None
