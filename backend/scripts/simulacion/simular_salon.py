"""
Simulación de un salón (DATOS SINTÉTICOS, no son niños reales).

Una docente y 12 estudiantes ficticios usan la plataforma desde el 24 de agosto hasta el
22 de octubre de 2026 a través de la API real (la misma lógica que en producción), con el
reloj controlado por freezegun para que cada acción quede con su fecha simulada. Todo se
guarda en una base SQLite aparte: nunca toca la base de producción.

- La docente sigue un plan de 8 semanas y publica 16 mundos «Del profe», 2 cada lunes (ver
  `mundos_profe.py`), registra la máquina del
  salón, elige «examen cada 4 mundos», cambia y oculta preguntas del temario y cada viernes
  revisa su panel y deja comentarios a quien necesita ayuda.
- Hay clase de inglés martes y jueves de 9:00 a 10:00: ahí los niños juegan los mundos del
  profe y presentan sus exámenes. En casa juegan vocabulario y gramática, cada uno con su
  perfil (horario, constancia, aciertos y cuánto mejora).
- La máquina de premios (ESP32) consulta su cola todo el tiempo y entrega en cuanto aparece
  un premio; la simulación anota a qué hora se entregaría cada uno.
- Los padres revisan el panel de sus hijos algunos domingos.

Uso (desde la carpeta backend, en un entorno con freezegun):
    python scripts/simulacion/simular_salon.py <salida.db> <registro.json>
"""
import json
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

SALIDA_DB, SALIDA_JSON = sys.argv[1], sys.argv[2]
if os.path.exists(SALIDA_DB):
    os.remove(SALIDA_DB)
os.environ.update({
    "USE_FAKE_DB": "true",
    "DATABASE_URL": f"sqlite:///{os.path.abspath(SALIDA_DB)}",
    "DEVICE_SHARED_SECRET": "secreto-simulacion",
    "LIMITE_LOGIN_POR_MINUTO": "1000000",
    "LIMITE_API_POR_MINUTO": "1000000",
    "CORS_ORIGINS": "*",
})
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

from freezegun import freeze_time  # noqa: E402

from mundos_profe import MUNDOS  # noqa: E402

ZONA = timezone(timedelta(hours=-5))
INICIO = date(2026, 8, 24)  # lunes: la coordinación crea las cuentas
FIN = datetime(2026, 10, 22, 10, 30, tzinfo=ZONA)  # hoy, después de la clase del jueves
DIAS_DE_CLASE = (1, 3)  # martes y jueves
azar = random.Random(20260824)


def local(dia: date, hora: int, minuto: int = 0) -> datetime:
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=ZONA)


@dataclass
class Perfil:
    nombre: str
    tipo: str
    base: float  # probabilidad de acertar al empezar
    mejora: float  # cuánto sube esa probabilidad hasta el final
    casa_por_semana: float  # sesiones en casa por semana (promedio)
    horas_casa: tuple[int, int]  # rango de hora local de las sesiones en casa
    lecciones: tuple[int, int]  # lecciones por sesión
    asistencia: float = 0.95
    gramatica: float = 0.3  # parte de las sesiones de casa dedicadas a gramática
    solo_fin_de_semana: bool = False
    deja_casa_semana: int | None = None  # deja de jugar en casa desde esa semana
    olvida_pin: float = 0.02
    examen_profe_en_casa: float = 0.15  # si tiene un examen del profe pendiente en casa
    segundos: tuple[int, int] = (5, 12)  # por pregunta
    acudiente: bool = True
    # estado de la simulación
    id: str = ""
    codigo: str = ""
    token: str = ""
    sesiones: list = field(default_factory=list)


PERFILES = [
    Perfil("Sofía Martínez", "Sobresaliente", 0.88, 0.06, 4, (17, 19), (3, 4)),
    Perfil("Mateo Rojas", "Constante", 0.78, 0.10, 3, (18, 20), (2, 3)),
    Perfil("Valentina Cruz", "Rápida pero descuidada", 0.70, 0.10, 5, (16, 18), (4, 5), segundos=(3, 7)),
    Perfil("Samuel Torres", "Con dificultades", 0.56, 0.14, 2, (18, 19), (1, 2), segundos=(8, 16)),
    Perfil("Isabella Gómez", "Juega de noche", 0.80, 0.07, 4, (20, 22), (2, 3), examen_profe_en_casa=0.6),
    Perfil("Santiago Díaz", "Irregular", 0.70, 0.08, 1.2, (17, 20), (2, 3), asistencia=0.7),
    Perfil("Mariana López", "Deja de practicar en casa", 0.75, 0.05, 3, (17, 19), (2, 3), asistencia=0.85,
           deja_casa_semana=4),
    Perfil("Emiliano Ruiz", "Solo en clase", 0.68, 0.12, 0, (0, 0), (2, 3), acudiente=False),
    Perfil("Luciana Herrera", "Fines de semana", 0.82, 0.06, 2, (10, 12), (4, 6), solo_fin_de_semana=True),
    Perfil("Tomás Castro", "Olvida el PIN", 0.74, 0.08, 2, (18, 20), (2, 3), olvida_pin=0.35, acudiente=False),
    Perfil("Gabriela Vargas", "Promedio", 0.76, 0.09, 3, (17, 19), (2, 3), acudiente=False),
    Perfil("Daniel Moreno", "Con dificultades que mejora", 0.52, 0.26, 3, (18, 20), (2, 3), segundos=(7, 14),
           acudiente=False),
]

registro: dict = {"eventos": [], "semanas": [], "entregas": [], "sin_vidas": [], "bloqueos": [],
                  "pin_errado": [], "examenes": [], "comentarios": [], "padres": [], "mundos_profe": []}


def anotar(lista: str, **datos):
    registro[lista].append({k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in datos.items()})


with freeze_time(local(INICIO, 6).astimezone(timezone.utc)) as reloj:
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from app.db import SesionLocal
    from app.main import app
    from app.models.tablas import Actividad
    from app.services.catalogo_service import aplicar_cambios_salon

    cliente = TestClient(app)
    ahora_sim = local(INICIO, 6)

    def ir_a(momento: datetime):
        global ahora_sim
        if momento > ahora_sim:
            ahora_sim = momento
            reloj.move_to(momento.astimezone(timezone.utc))

    def avanzar(segundos: float):
        ir_a(ahora_sim + timedelta(seconds=segundos))

    def api(metodo, ruta, token=None, cuerpo=None, cabeceras=None, esperado=(200, 201)):
        h = dict(cabeceras or {})
        if token:
            h["Authorization"] = f"Bearer {token}"
        r = cliente.request(metodo, ruta, json=cuerpo, headers=h)
        if esperado and r.status_code not in esperado:
            raise RuntimeError(f"{metodo} {ruta} → {r.status_code} {r.text[:300]}")
        return r

    # ------------------------------------------------------------- cuentas (coordinación)
    coord = api("POST", "/api/usuarios/login", cuerpo={"usuario": "coordinador", "password": "coordinador123"}).json()
    CLAVE = "clave-simulacion-1"

    def adulto(rol, usuario, nombre):
        creado = api("POST", "/api/coordinador/adultos", coord["token"],
                     {"nombre": nombre, "rol": rol, "usuario": usuario}).json()
        s = api("POST", "/api/usuarios/login", cuerpo={"usuario": usuario, "password": creado["password_temporal"]}).json()
        api("POST", "/api/usuarios/cambiar-password", s["token"],
            {"actual": creado["password_temporal"], "nueva": CLAVE, "acepta_terminos": True})
        return creado

    docente = adulto("docente", "lmendez", "Laura Méndez")

    def sesion_docente():
        return api("POST", "/api/usuarios/login", cuerpo={"usuario": "lmendez", "password": CLAVE}).json()["token"]

    padres = {}
    pines = ["4826", "5830", "7149", "3958", "6207", "8415", "2693", "9071", "1538", "4762", "3184", "6529"]
    for i, p in enumerate(PERFILES):
        acudientes = []
        if p.acudiente:
            usuario = f"acudiente{i + 1:02d}"
            padres[p.nombre] = adulto("padre", usuario, f"Acudiente de {p.nombre.split()[0]}")
            padres[p.nombre]["usuario"] = usuario
            acudientes = [padres[p.nombre]["id_usuario"]]
        nino = api("POST", "/api/coordinador/estudiantes", coord["token"], {
            "nombre": p.nombre, "edad": azar.choice([6, 7, 7, 8]), "pin": pines[i], "docente_id": docente["id_usuario"],
            "acudientes_ids": acudientes, "autoriza_datos_menor": True,
        }).json()
        p.id, p.codigo, p.pin = nino["id_usuario"], nino["codigo_acceso"], pines[i]

    # ------------------------------------------------------------- la docente prepara su salón
    ir_a(local(INICIO, 15))
    token_docente = sesion_docente()
    api("PUT", f"/api/usuarios/docente/{docente['id_usuario']}/dispensador", token_docente, {"device_id": "aula-2b"})
    api("PUT", f"/api/usuarios/docente/{docente['id_usuario']}/premio", token_docente, {"cada_mundos": 4})
    # Cambia el enunciado de una pregunta del temario y oculta otra, solo para su salón.
    animals = api("GET", "/api/temario/salon/animals/preguntas", token_docente).json()
    primera = animals["lecciones"][0]["preguntas"][0]
    api("PUT", f"/api/temario/salon/preguntas/{primera['id_actividad']}", token_docente,
        {"pregunta": "Look at the picture. What animal is it?", "opciones": primera["opciones"],
         "respuesta_correcta": primera["respuesta_correcta"]})
    api("PATCH", f"/api/temario/salon/preguntas/{animals['lecciones'][1]['preguntas'][7]['id_actividad']}",
        token_docente, {"activo": False})
    anotar("eventos", fecha=ahora_sim, quien="docente", que="configura máquina, examen cada 4 mundos y edita el temario")

    def crear_mundo(m):
        token = sesion_docente()
        mundo = api("POST", "/api/mundos", token, {"titulo": m["titulo"], "emoji": m["emoji"],
                                                    "descripcion": m["descripcion"]}).json()
        for emoji, pregunta, correcta, distractores in m["preguntas"]:
            api("POST", f"/api/mundos/{mundo['id_mundo']}/preguntas", token, {
                "pregunta": pregunta, "opciones": [correcta, *distractores], "respuesta_correcta": correcta,
                "icono": emoji})
        anotar("mundos_profe", fecha=ahora_sim, titulo=m["titulo"], preguntas=len(m["preguntas"]))

    # ------------------------------------------------------------- acciones de los niños
    def respuestas_correctas(ids):
        with SesionLocal() as db:
            filas = [a.a_dict() for a in db.scalars(select(Actividad).where(Actividad.id_actividad.in_(ids)))]
            vistas = aplicar_cambios_salon(db, docente["id_usuario"], filas)
        return {p["id_actividad"]: p["respuesta_correcta"] for p in vistas}

    def probabilidad(p: Perfil, extra=0.0):
        avance = (ahora_sim - local(INICIO, 0)).days / (FIN - local(INICIO, 0)).days
        return max(0.25, min(0.97, p.base + p.mejora * avance + extra + azar.uniform(-0.04, 0.04)))

    def entrar(p: Perfil) -> bool:
        intentos = 0
        while azar.random() < p.olvida_pin and intentos < 3:
            intentos += 1
            r = api("POST", "/api/usuarios/login-pin", cuerpo={"codigo": p.codigo, "pin": "0000"}, esperado=None)
            anotar("pin_errado", fecha=ahora_sim, nino=p.nombre, codigo=r.status_code)
            avanzar(azar.randint(5, 20))
        r = api("POST", "/api/usuarios/login-pin", cuerpo={"codigo": p.codigo, "pin": p.pin}, esperado=None)
        if r.status_code == 429:
            anotar("bloqueos", fecha=ahora_sim, nino=p.nombre)
            return False
        p.token = r.json()["token"]
        return True

    def jugar_leccion(p: Perfil, seccion: str, en_clase: bool):
        r = api("GET", f"/api/lecciones/jugar?seccion={seccion}", p.token, esperado=None)
        if r.status_code == 409:
            anotar("sin_vidas", fecha=ahora_sim, nino=p.nombre, seccion=seccion)
            return "sin_vidas"
        if r.status_code == 404:
            return "terminado"
        leccion = r.json()
        extra = (0.03 if en_clase else 0.0) - (0.06 if seccion == "gramatica" else 0.0)
        prob = probabilidad(p, extra)
        respuestas, vidas = [], leccion["vidas"]
        for pregunta in leccion["preguntas"]:
            avanzar(azar.randint(*p.segundos) + 1.5)
            bien = azar.random() < prob
            mala = next(o for o in pregunta["opciones"] if o != pregunta["respuesta_correcta"])
            respuestas.append({"id_actividad": pregunta["id_actividad"],
                               "respuesta": pregunta["respuesta_correcta"] if bien else mala})
            if not bien:
                vidas -= 1
                if vidas <= 0:
                    break
        resultado = api("POST", "/api/lecciones/resultado", p.token,
                        {"unidad": leccion["unidad"]["id"], "leccion": leccion["leccion"], "respuestas": respuestas}).json()
        avanzar(8)
        return resultado

    def presentar_examen(p: Perfil, examen: dict, en_clase: bool):
        datos = api("GET", f"/api/examenes/{examen['id_examen']}", p.token).json()
        correctas = respuestas_correctas([q["id_actividad"] for q in datos["preguntas"]])
        prob = probabilidad(p, 0.04 if en_clase else 0.0)
        respuestas = []
        for q in datos["preguntas"]:
            avanzar(azar.randint(*p.segundos) + 1)
            bien = azar.random() < prob
            mala = next(o for o in q["opciones"] if o != correctas[q["id_actividad"]])
            respuestas.append({"id_actividad": q["id_actividad"], "respuesta": correctas[q["id_actividad"]] if bien else mala})
        r = api("POST", f"/api/examenes/{examen['id_examen']}/resultado", p.token, {"respuestas": respuestas}).json()
        anotar("examenes", fecha=ahora_sim, nino=p.nombre, id_examen=examen["id_examen"], seccion=examen["seccion"],
               aciertos=r["aciertos"],
               total=r["total"], aprobado=r["aprobado"], primera_vez=r["primera_vez"], en_clase=en_clase,
               con_premio=bool(r["recompensa"] and r["recompensa"]["device_id"]))
        if r["recompensa"] and r["recompensa"]["device_id"]:
            maquina_revisa(en_clase)
        avanzar(10)
        return r

    def maquina_revisa(en_clase: bool):
        """La máquina consulta su cola cada 5 segundos y entrega en cuanto hay un premio."""
        avanzar(5)
        secreto = {"X-Device-Secret": "secreto-simulacion"}
        for premio in api("GET", "/api/recompensas/cola/aula-2b", cabeceras=secreto).json():
            api("POST", f"/api/recompensas/{premio['id_historial']}/confirmar-entrega", cabeceras=secreto)
            anotar("entregas", fecha=ahora_sim, en_clase=en_clase, hora_local=ahora_sim.hour,
                   id_historial=premio["id_historial"])

    def examenes_pendientes(p: Perfil):
        return [e for e in api("GET", "/api/examenes", p.token).json() if e["estado"] == "pendiente"]

    def sesion(p: Perfil, inicio: datetime, en_clase: bool):
        ir_a(inicio)
        if not entrar(p):
            return
        lecciones = 0
        objetivo = azar.randint(*p.lecciones)
        # Primero los exámenes pendientes: en clase la docente pide presentarlos.
        for examen in examenes_pendientes(p):
            if examen["seccion"] == "profesor" and not en_clase and azar.random() >= p.examen_profe_en_casa:
                continue
            if not en_clase and azar.random() < 0.4:
                continue
            r = presentar_examen(p, examen, en_clase)
            if not r["aprobado"] and azar.random() < 0.5:
                presentar_examen(p, examen, en_clase)
        if en_clase:
            secciones = ["profesor", "vocabulario"]
        else:
            secciones = ["gramatica", "vocabulario"] if azar.random() < p.gramatica else ["vocabulario", "gramatica"]
            if azar.random() < p.examen_profe_en_casa:
                secciones.insert(0, "profesor")
        while lecciones < objetivo and secciones:
            resultado = jugar_leccion(p, secciones[0], en_clase)
            if resultado == "terminado":
                secciones.pop(0)
                continue
            if resultado == "sin_vidas":
                break
            lecciones += 1
            mundo = resultado.get("mundo_completado")
            if mundo and mundo.get("examen"):
                examen = mundo["examen"]
                if examen["seccion"] != "profesor" or en_clase or azar.random() < p.examen_profe_en_casa:
                    r = presentar_examen(p, examen, en_clase)
                    if not r["aprobado"] and azar.random() < 0.5:
                        presentar_examen(p, examen, en_clase)
        # De vez en cuando gasta puntos en la tienda.
        if azar.random() < 0.15:
            tienda = api("GET", "/api/tienda", p.token).json()
            saldo = tienda["perfil"]["saldo"]
            ya = set(tienda["perfil"].get("comprados", []))
            comprables = [i for i in tienda["items"] if i["precio"] and i["precio"] <= saldo and i["id"] not in ya]
            if comprables:
                item = azar.choice(comprables)
                if api("POST", "/api/tienda/comprar", p.token, {"item_id": item["id"]}, esperado=None).status_code == 200:
                    api("POST", "/api/tienda/equipar", p.token, {"item_id": item["id"], "tipo": item["tipo"]}, esperado=None)
        p.sesiones.append({"inicio": inicio.isoformat(), "en_clase": en_clase, "lecciones": lecciones})

    # ------------------------------------------------------------- calendario
    def semana_de(dia: date) -> int:
        return (dia - INICIO).days // 7 + 1

    dia = INICIO
    while local(dia, 0) <= FIN:
        semana = semana_de(dia)
        acciones = []  # (momento, función)
        if dia.weekday() == 0:  # lunes: la docente publica los mundos de la semana
            for m in MUNDOS:
                if m["semana"] == semana:
                    acciones.append((local(dia, 14, 0), lambda m=m: crear_mundo(m)))
        if dia.weekday() in DIAS_DE_CLASE:
            for p in PERFILES:
                if azar.random() < p.asistencia:
                    inicio = local(dia, 9, azar.randint(2, 15))
                    acciones.append((inicio, lambda p=p, inicio=inicio: sesion(p, inicio, True)))
        for p in PERFILES:
            if p.casa_por_semana == 0 or (p.deja_casa_semana and semana >= p.deja_casa_semana):
                continue
            fin_de_semana = dia.weekday() >= 5
            if p.solo_fin_de_semana and not fin_de_semana:
                continue
            dias_posibles = 2 if p.solo_fin_de_semana else 7
            if azar.random() < p.casa_por_semana / dias_posibles:
                inicio = local(dia, azar.randint(*p.horas_casa), azar.randint(0, 50))
                acciones.append((inicio, lambda p=p, inicio=inicio: sesion(p, inicio, False)))
        if dia.weekday() == 4:  # viernes: la docente revisa el panel y deja comentarios
            def revisar(dia=dia, semana=semana):
                ir_a(local(dia, 15))
                token = sesion_docente()
                panel = api("GET", f"/api/lecciones/docente/{docente['id_usuario']}", token).json()
                anotar("semanas", semana=semana, fecha=ahora_sim, necesitan_ayuda=panel["necesitan_ayuda"],
                       activos_hoy=panel["activos_hoy"], progreso_promedio=panel["progreso_promedio"],
                       quienes=[(e["nombre"], e["motivos"]) for e in panel["estudiantes"] if e["necesita_ayuda"]])
                for e in [e for e in panel["estudiantes"] if e["necesita_ayuda"]][:3]:
                    comentario = (f"{e['nombre'].split()[0]} necesita refuerzo: {e['motivos'][0].lower()}. "
                                  "Les sugiero practicar 10 minutos diarios en casa.")
                    api("POST", "/api/feedback", token, {"id_estudiante": e["id_usuario"], "comentario": comentario})
                    anotar("comentarios", fecha=ahora_sim, nino=e["nombre"], comentario=comentario)
            acciones.append((local(dia, 15), revisar))
        if dia.weekday() == 6:  # domingo: algunos padres revisan el panel
            for p in PERFILES:
                if p.nombre in padres and azar.random() < 0.5:
                    def ver(p=p, dia=dia):
                        ir_a(local(dia, 19, azar.randint(0, 59)))
                        s = api("POST", "/api/usuarios/login", cuerpo={"usuario": padres[p.nombre]["usuario"],
                                                                         "password": CLAVE}).json()
                        hijos = api("GET", f"/api/usuarios/padre/{s['id_usuario']}/hijos", s["token"]).json()
                        for h in hijos:
                            api("GET", f"/api/lecciones/resumen/{h['id_usuario']}", s["token"])
                            api("GET", f"/api/feedback/estudiante/{h['id_usuario']}", s["token"])
                        anotar("padres", fecha=ahora_sim, nino=p.nombre)
                    acciones.append((local(dia, 19), ver))
        for momento, accion in sorted(acciones, key=lambda a: a[0]):
            if momento > FIN:
                continue
            accion()
        dia += timedelta(days=1)

    registro["estudiantes"] = [
        {"nombre": p.nombre, "perfil": p.tipo, "id": p.id, "codigo": p.codigo, "sesiones": p.sesiones,
         "acudiente": p.acudiente}
        for p in PERFILES
    ]
    registro["docente"] = {"id": docente["id_usuario"], "nombre": "Laura Méndez", "usuario": "lmendez", "clave": CLAVE}
    registro["periodo"] = {"inicio": local(INICIO, 6).isoformat(), "fin": FIN.isoformat()}

with open(SALIDA_JSON, "w", encoding="utf-8") as f:
    json.dump(registro, f, ensure_ascii=False, indent=1)
print("listo:", SALIDA_DB, SALIDA_JSON)
