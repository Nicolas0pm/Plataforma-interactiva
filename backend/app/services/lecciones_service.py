"""
Camino de aprendizaje guiado (estilo Duolingo).

- El niño NO elige lecciones nuevas: `siguiente_leccion()` decide cuál sigue. Normalmente es
  la primera del temario que aún no aprueba; pero cada `REPASO_CADA` lecciones nuevas, si
  hay alguna aprobada con menos del 80 % de aciertos, le toca un **repaso** de la más débil.
- Sí puede **repetir** lecciones que ya aprobó (modo "practica"): cuenta para su precisión
  y su mejor resultado, pero no da puntos (para que no se acumulen premios repitiendo).
- Cada lección tiene `VIDAS_POR_LECCION` vidas: cada error quita una. Si se equivoca
  3 veces la lección se pierde y se repite; si termina con al menos una vida, la aprueba.
- El servidor califica comparando las respuestas con las correctas guardadas en Firestore.

Progreso guardado en `usuarios/{id}/resultados/actual`:
  lecciones: { "animals-1": {aprobada, mejor, total, intentos, fallos, ultima} }
  unidades:  { "animals": {respuestas, correctas} }      # precisión por tema
  respuestas_totales, respuestas_correctas, aprobadas_desde_repaso
Cada intento queda además en la colección `intentos_leccion` (con sus errores), que es lo
que ve el docente como "en qué va bien y en qué va mal".
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.curriculo import (
    PUNTOS_POR_ACIERTO,
    SECCIONES,
    VIDAS_POR_LECCION,
    clave_leccion,
    info_unidad,
    lecciones_en_orden,
    ORDEN_UNIDADES,
)
from app.services.progreso_service import calcular_nivel, puntos_para_siguiente_nivel
from app.services.recompensas_service import evaluar_recompensa

REPASO_CADA = 3
UMBRAL_REPASO = 0.8


def _ref_progreso(db, id_usuario: str):
    return db.collection("usuarios").document(id_usuario).collection("resultados").document("actual")


def leer_progreso(db, id_usuario: str) -> dict:
    datos = _ref_progreso(db, id_usuario).get().to_dict() or {}
    datos.setdefault("puntaje_total", 0)
    datos.setdefault("actividades_completadas", 0)
    datos.setdefault("lecciones", {})
    datos.setdefault("unidades", {})
    datos.setdefault("respuestas_totales", 0)
    datos.setdefault("respuestas_correctas", 0)
    datos.setdefault("aprobadas_desde_repaso", 0)
    return datos


def _proporcion(estado: dict) -> float:
    return estado.get("mejor", 0) / estado["total"] if estado.get("total") else 0.0


def siguiente_leccion(progreso: dict) -> dict | None:
    """La lección que le toca al niño: {unidad, leccion, modo: "nueva" | "repaso"}."""
    lecciones = progreso["lecciones"]
    pendiente = next(
        ((u, n) for u, n in lecciones_en_orden() if not lecciones.get(clave_leccion(u, n), {}).get("aprobada")),
        None,
    )
    debiles = sorted(
        (
            (_proporcion(estado), clave)
            for clave, estado in lecciones.items()
            if estado.get("aprobada") and _proporcion(estado) < UMBRAL_REPASO
        ),
    )
    toca_repaso = progreso["aprobadas_desde_repaso"] >= REPASO_CADA or pendiente is None
    if toca_repaso and debiles:
        unidad, _, numero = debiles[0][1].rpartition("-")
        return {"unidad": unidad, "leccion": int(numero), "modo": "repaso"}
    if pendiente:
        return {"unidad": pendiente[0], "leccion": pendiente[1], "modo": "nueva"}
    return None  # terminó todo el temario y no tiene nada débil


def modo_para(progreso: dict, unidad: str, leccion: int) -> str:
    """Decide si el niño puede jugar esa lección y en qué modo, o lanza 403."""
    siguiente = siguiente_leccion(progreso)
    if siguiente and siguiente["unidad"] == unidad and siguiente["leccion"] == leccion:
        return siguiente["modo"]
    if progreso["lecciones"].get(clave_leccion(unidad, leccion), {}).get("aprobada"):
        return "practica"
    raise HTTPException(403, "Esa lección todavía no está desbloqueada")


def preguntas_de(db, unidad: str, leccion: int) -> list[dict]:
    query = (
        db.collection("actividades")
        .where("unidad", "==", unidad)
        .where("leccion", "==", leccion)
        .where("activo", "==", True)
    )
    preguntas = [{**doc.to_dict(), "id_actividad": doc.id} for doc in query.stream()]
    if not preguntas:
        raise HTTPException(404, "Esta lección no tiene preguntas cargadas")
    return sorted(preguntas, key=lambda p: p.get("orden") or 0)


def armar_leccion(db, id_usuario: str, unidad: str | None, leccion: int | None) -> dict:
    progreso = leer_progreso(db, id_usuario)
    if unidad is None or leccion is None:
        siguiente = siguiente_leccion(progreso)
        if siguiente is None:
            raise HTTPException(404, "¡Terminaste todo el temario!")
        unidad, leccion = siguiente["unidad"], siguiente["leccion"]
    if unidad not in ORDEN_UNIDADES:
        raise HTTPException(404, "No existe esa unidad")
    modo = modo_para(progreso, unidad, leccion)
    preguntas = preguntas_de(db, unidad, leccion)
    return {
        "unidad": info_unidad(unidad),
        "leccion": leccion,
        "modo": modo,
        "vidas": VIDAS_POR_LECCION,
        "preguntas": [
            {
                "id_actividad": p["id_actividad"],
                "pregunta": p.get("pregunta"),
                "opciones": p.get("opciones", []),
                # Se envía para dar el feedback inmediato; la nota final la calcula el servidor.
                "respuesta_correcta": p.get("respuesta_correcta"),
                "icono": p.get("icono"),
                "formato_opciones": p.get("formato_opciones", "texto"),
            }
            for p in preguntas
        ],
    }


def registrar_resultado(db, id_usuario: str, unidad: str, leccion: int, respuestas: list[dict]) -> dict:
    progreso = leer_progreso(db, id_usuario)
    if unidad not in ORDEN_UNIDADES:
        raise HTTPException(404, "No existe esa unidad")
    modo = modo_para(progreso, unidad, leccion)
    preguntas = {p["id_actividad"]: p for p in preguntas_de(db, unidad, leccion)}

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
    aprobada = len(errores) < VIDAS_POR_LECCION and aciertos + len(errores) >= total
    ahora = datetime.now(timezone.utc)

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

    # --- Puntos: solo lecciones nuevas y repasos aprobados (la práctica no suma) ---
    puntos = aciertos * PUNTOS_POR_ACIERTO if aprobada and modo != "practica" else 0
    anterior = progreso["puntaje_total"]
    nivel_anterior = calcular_nivel(anterior)
    progreso["puntaje_total"] = anterior + puntos
    progreso["actividades_completadas"] += respondidas
    if aprobada and modo == "nueva":
        progreso["aprobadas_desde_repaso"] += 1
    elif aprobada and modo == "repaso":
        progreso["aprobadas_desde_repaso"] = 0

    nuevo_nivel = calcular_nivel(progreso["puntaje_total"])
    progreso["nivel_logrado"] = nuevo_nivel
    progreso["actualizado_en"] = ahora
    _ref_progreso(db, id_usuario).set(progreso)

    db.collection("intentos_leccion").document().set({
        "id_usuario": id_usuario,
        "unidad": unidad,
        "leccion": leccion,
        "modo": modo,
        "aciertos": aciertos,
        "total": total,
        "errores": errores,
        "aprobada": aprobada,
        "puntos": puntos,
        "fecha": ahora,
    })

    recompensa = evaluar_recompensa(id_usuario, progreso["puntaje_total"], anterior) if puntos else None
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
        "recompensa_generada": recompensa,
        "siguiente": siguiente_leccion(progreso),
    }


def intentos_recientes(db, id_usuario: str, limite: int = 20) -> list[dict]:
    # Solo filtro por igualdad (no necesita índice compuesto); se ordena aquí.
    docs = [d.to_dict() for d in db.collection("intentos_leccion").where("id_usuario", "==", id_usuario).stream()]
    docs.sort(key=lambda d: d["fecha"], reverse=True)
    return docs[:limite]


def resumen_aprendizaje(db, id_usuario: str) -> dict:
    """Camino completo con estados + estadísticas. Lo usan el niño, su docente y sus padres."""
    progreso = leer_progreso(db, id_usuario)
    siguiente = siguiente_leccion(progreso)
    lecciones = progreso["lecciones"]

    unidades = []
    for unidad in ORDEN_UNIDADES:
        info = info_unidad(unidad)
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
            "lecciones": estados,
            "aprobadas": sum(1 for e in estados if e["aprobada"]),
            "precision": round(por_unidad["correctas"] / por_unidad["respuestas"], 2)
            if por_unidad.get("respuestas") else None,
        })

    recientes = intentos_recientes(db, id_usuario)
    conteo_errores: dict[str, dict] = {}
    for intento in recientes:
        for error in intento.get("errores", []):
            item = conteo_errores.setdefault(error["id_actividad"], {**error, "veces": 0, "unidad": intento["unidad"]})
            item["veces"] += 1

    total_lecciones = len(lecciones_en_orden())
    aprobadas = sum(1 for e in lecciones.values() if e.get("aprobada"))
    return {
        "secciones": SECCIONES,
        "unidades": unidades,
        "siguiente": {**siguiente, "info": info_unidad(siguiente["unidad"])} if siguiente else None,
        "lecciones_aprobadas": aprobadas,
        "total_lecciones": total_lecciones,
        "precision": round(progreso["respuestas_correctas"] / progreso["respuestas_totales"], 2)
        if progreso["respuestas_totales"] else None,
        "puntaje_total": progreso["puntaje_total"],
        "nivel_logrado": calcular_nivel(progreso["puntaje_total"]),
        "puntos_para_siguiente_nivel": puntos_para_siguiente_nivel(progreso["puntaje_total"]),
        # Última lección jugada (no la fecha de registro): define "activo hoy" y "sin practicar".
        "ultima_actividad": recientes[0]["fecha"] if recientes else None,
        "recientes": [
            {k: i[k] for k in ("unidad", "leccion", "modo", "aciertos", "total", "aprobada", "puntos", "fecha")}
            | {"errores": len(i.get("errores", [])), "titulo": info_unidad(i["unidad"])["titulo"]}
            for i in recientes[:8]
        ],
        "errores_frecuentes": sorted(conteo_errores.values(), key=lambda e: -e["veces"])[:8],
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


def sembrar_temario(db) -> dict:
    """Carga el temario de `app/curriculo.py` en Firestore. Es idempotente: cada pregunta
    usa un ID fijo ("animals-1-1"), así que volver a correrlo actualiza en vez de duplicar.
    Las actividades antiguas sin unidad (catálogo anterior) quedan desactivadas."""
    from app.curriculo import generar_actividades

    desactivadas = 0
    for doc in db.collection("actividades").where("activo", "==", True).stream():
        if not doc.to_dict().get("unidad"):
            doc.reference.update({"activo": False})
            desactivadas += 1
    actividades = generar_actividades()
    for actividad in actividades:
        db.collection("actividades").document(actividad["nombre"]).set(actividad)
    return {"creadas_o_actualizadas": len(actividades), "antiguas_desactivadas": desactivadas}
