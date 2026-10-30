"""
Simulación de un salón en la plataforma PUBLICADA (datos sintéticos, no son niños reales).

A diferencia de `simular_salon.py`, no cambia el reloj ni toca la base de datos: todo pasa
por la API pública (Render + Neon), con la hora real. Es una jornada: la coordinación crea las
cuentas, la docente prepara su salón y publica sus 4 mundos, los niños juegan en clase y luego
en casa (cada uno con su perfil), la máquina entrega los premios, la docente revisa su panel y
deja comentarios, y los acudientes consultan el avance.

Todo lo simulado queda marcado: los nombres empiezan por «(Sim)» y los usuarios por «sim_», y
la máquina es «sim-aula-2b». Con `desactivar` se desactivan todas esas cuentas al terminar (no se
borran, así que la simulación se corre una sola vez).

Uso (desde backend/; pide el usuario y la contraseña de un coordinador, que no se guardan):
    python scripts/simulacion/simular_produccion.py simular
    python scripts/simulacion/simular_produccion.py desactivar
Variables opcionales: SIM_API (por defecto la API publicada), SIM_DEVICE_SECRET (secreto de las
máquinas en Render, para confirmar las entregas; sin él los premios quedan en la cola).
"""
import getpass
import json
import os
import random
import secrets
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

sys.path.insert(0, os.path.dirname(__file__))
from mundos_profe import MUNDOS  # noqa: E402

API = os.environ.get("SIM_API", "https://plataforma-ingles-kids-api.onrender.com").rstrip("/")
CARPETA = os.environ.get("SIM_CARPETA") or os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "simulacion", "produccion")
CUENTAS = os.path.join(CARPETA, "cuentas_produccion.json")  # en .gitignore
REGISTRO = os.path.join(CARPETA, "registro_produccion.json")
DISPOSITIVO = "sim-aula-2b"
PAUSA = 0.15  # entre peticiones, para no acercarse al límite por IP
azar = random.Random(20261022)


@dataclass
class Perfil:
    nombre: str
    tipo: str
    acierto: float
    lecciones_casa: tuple[int, int]
    asistencia: float = 0.95
    casa: bool = True
    gramatica: float = 0.3
    olvida_pin: float = 0.02
    acudiente: bool = True
    id: str = ""
    codigo: str = ""
    pin: str = ""
    token: str = ""
    lecciones: list = field(default_factory=list)
    aprobadas: list = field(default_factory=list)  # (unidad, lección) que puede practicar


PERFILES = [
    Perfil("Sofía Martínez", "Sobresaliente", 0.90, (4, 6)),
    Perfil("Mateo Rojas", "Constante", 0.82, (3, 4)),
    Perfil("Valentina Cruz", "Rápida pero descuidada", 0.68, (5, 7)),
    Perfil("Samuel Torres", "Con dificultades", 0.60, (1, 2)),
    Perfil("Isabella Gómez", "Juega de noche", 0.82, (3, 4)),
    Perfil("Santiago Díaz", "Irregular", 0.72, (1, 3), asistencia=0.7),
    Perfil("Mariana López", "Deja de practicar en casa", 0.76, (0, 0), casa=False),
    Perfil("Emiliano Ruiz", "Solo en clase", 0.72, (0, 0), casa=False, acudiente=False),
    Perfil("Luciana Herrera", "Fines de semana", 0.84, (5, 7)),
    Perfil("Tomás Castro", "Olvida el PIN", 0.76, (2, 3), olvida_pin=0.6, acudiente=False),
    Perfil("Gabriela Vargas", "Promedio", 0.78, (2, 4), acudiente=False),
    Perfil("Daniel Moreno", "Con dificultades", 0.58, (2, 3), acudiente=False),
]
PINES = ["4826", "5830", "7149", "3958", "6207", "8415", "2693", "9071", "1538", "4762", "3184", "6529"]

registro: dict = {"api": API, "eventos": [], "lecciones": [], "examenes": [], "entregas": [], "sin_vidas": [],
                  "pin_errado": [], "comentarios": [], "padres": [], "errores": [], "tiempos_ms": []}
cliente = httpx.Client(base_url=API, timeout=90)
correctas: dict[str, str] = {}  # id_actividad -> respuesta, de las lecciones ya jugadas


def ahora():
    return datetime.now(timezone.utc).isoformat()


def anotar(lista, **datos):
    registro[lista].append({"fecha": ahora(), **datos})


def api(metodo, ruta, token=None, cuerpo=None, cabeceras=None, esperado=(200, 201)):
    h = dict(cabeceras or {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    for _ in range(5):
        time.sleep(PAUSA)
        inicio = time.perf_counter()
        r = cliente.request(metodo, ruta, json=cuerpo, headers=h)
        registro["tiempos_ms"].append(round((time.perf_counter() - inicio) * 1000))
        if r.status_code == 429 and "login-pin" not in ruta:
            time.sleep(int(r.headers.get("Retry-After", "10")))
            continue
        break
    if esperado and r.status_code not in esperado:
        anotar("errores", ruta=ruta, codigo=r.status_code, detalle=r.text[:200])
        raise RuntimeError(f"{metodo} {ruta} → {r.status_code} {r.text[:300]}")
    return r


def login(usuario, password):
    return api("POST", "/api/usuarios/login", cuerpo={"usuario": usuario, "password": password}).json()


def coordinador():
    usuario = os.environ.get("SIM_COORD_USUARIO") or input("Usuario del coordinador: ").strip()
    password = os.environ.get("SIM_COORD_PASSWORD") or getpass.getpass("Contraseña del coordinador: ")
    sesion = login(usuario, password)
    if sesion.get("debe_cambiar_password"):
        # Primer ingreso con la contraseña temporal: hay que cambiarla y aceptar los términos.
        nueva = getpass.getpass("Es una contraseña temporal. Escriba la nueva contraseña: ")
        if nueva != getpass.getpass("Repítala: "):
            raise SystemExit("Las contraseñas no coinciden.")
        api("POST", "/api/usuarios/cambiar-password", sesion["token"],
            {"actual": password, "nueva": nueva, "acepta_terminos": True})
        sesion = login(usuario, nueva)
    return sesion


def simular():
    print("Despertando la API (Render puede tardar ~1 minuto)…")
    cliente.get("/", timeout=120)
    coord = coordinador()
    existentes = api("GET", "/api/coordinador/usuarios", coord["token"]).json()
    lista = existentes if isinstance(existentes, list) else [u for v in existentes.values() if isinstance(v, list) for u in v]
    if any(str(u.get("usuario") or "").startswith("sim_") or str(u.get("nombre", "")).startswith("(Sim)") for u in lista):
        # «desactivar» no borra las cuentas: sus usuarios siguen ocupados y no se puede repetir tal cual.
        raise SystemExit("Ya existen cuentas «(Sim)» en la plataforma (activas o desactivadas): la simulación ya se hizo.")
    clave = "Sim-" + secrets.token_urlsafe(9)  # contraseña de todas las cuentas de adulto simuladas
    cuentas = {"aviso": "Cuentas de la simulación en producción (datos sintéticos). No subir al repositorio.",
               "clave_adultos": clave, "adultos": [], "estudiantes": [], "dispositivo": DISPOSITIVO}

    def guardar_cuentas():
        # Después de cada cuenta: si algo falla a mitad, «desactivar» encuentra las ya creadas.
        with open(CUENTAS, "w", encoding="utf-8") as f:
            json.dump(cuentas, f, ensure_ascii=False, indent=1)

    def adulto(rol, usuario, nombre):
        creado = api("POST", "/api/coordinador/adultos", coord["token"], {"nombre": nombre, "rol": rol, "usuario": usuario}).json()
        cuentas["adultos"].append({"rol": rol, "usuario": usuario, "nombre": nombre, "id": creado["id_usuario"]})
        guardar_cuentas()
        s = login(usuario, creado["password_temporal"])
        api("POST", "/api/usuarios/cambiar-password", s["token"],
            {"actual": creado["password_temporal"], "nueva": clave, "acepta_terminos": True})
        return creado

    print("Creando cuentas…")
    docente = adulto("docente", "sim_lmendez", "(Sim) Laura Méndez")
    padres = {}
    for i, p in enumerate(PERFILES):
        acudientes = []
        if p.acudiente:
            usuario = f"sim_acudiente{i + 1:02d}"
            padres[p.nombre] = adulto("padre", usuario, f"(Sim) Acudiente de {p.nombre.split()[0]}")
            padres[p.nombre]["usuario"] = usuario
            acudientes = [padres[p.nombre]["id_usuario"]]
        nino = api("POST", "/api/coordinador/estudiantes", coord["token"], {
            "nombre": f"(Sim) {p.nombre}", "edad": azar.choice([6, 7, 7, 8]), "pin": PINES[i],
            "docente_id": docente["id_usuario"], "acudientes_ids": acudientes, "autoriza_datos_menor": True}).json()
        p.id, p.codigo, p.pin = nino["id_usuario"], nino["codigo_acceso"], PINES[i]
        cuentas["estudiantes"].append({"nombre": nino["nombre"], "perfil": p.tipo, "codigo": p.codigo, "pin": p.pin,
                                       "id": p.id, "acudiente": padres.get(p.nombre, {}).get("usuario")})
        guardar_cuentas()
    anotar("eventos", que="cuentas creadas", docente=1, acudientes=len(padres), estudiantes=len(PERFILES))

    # ------------------------------------------------------------- la docente prepara su salón
    print("La docente prepara su salón…")
    td = login("sim_lmendez", clave)["token"]
    api("PUT", f"/api/usuarios/docente/{docente['id_usuario']}/dispensador", td, {"device_id": DISPOSITIVO})
    api("PUT", f"/api/usuarios/docente/{docente['id_usuario']}/premio", td, {"cada_mundos": 2})
    animals = api("GET", "/api/temario/salon/animals/preguntas", td).json()
    primera = animals["lecciones"][0]["preguntas"][0]
    api("PUT", f"/api/temario/salon/preguntas/{primera['id_actividad']}", td,
        {"pregunta": "Look at the picture. What animal is it?", "opciones": primera["opciones"],
         "respuesta_correcta": primera["respuesta_correcta"]})
    api("PATCH", f"/api/temario/salon/preguntas/{animals['lecciones'][1]['preguntas'][7]['id_actividad']}", td,
        {"activo": False})
    for m in MUNDOS:
        mundo = api("POST", "/api/mundos", td, {"titulo": m["titulo"], "emoji": m["emoji"], "descripcion": m["descripcion"]}).json()
        for emoji, pregunta, correcta, distractores in m["preguntas"]:
            api("POST", f"/api/mundos/{mundo['id_mundo']}/preguntas", td, {
                "pregunta": pregunta, "opciones": [correcta, *distractores], "respuesta_correcta": correcta, "icono": emoji})
    anotar("eventos", que="docente: máquina, examen cada 2 mundos, temario editado y 4 mundos publicados")

    # ------------------------------------------------------------- los niños
    def entrar(p):
        intentos = 0
        while azar.random() < p.olvida_pin and intentos < 2:
            intentos += 1
            r = api("POST", "/api/usuarios/login-pin", cuerpo={"codigo": p.codigo, "pin": "0000"}, esperado=None)
            anotar("pin_errado", nino=p.nombre, codigo=r.status_code)
        r = api("POST", "/api/usuarios/login-pin", cuerpo={"codigo": p.codigo, "pin": p.pin}, esperado=None)
        if r.status_code != 200:
            anotar("errores", ruta="login-pin", codigo=r.status_code, detalle=p.nombre)
            return False
        p.token = r.json()["token"]
        return True

    def jugar(p, seccion, en_clase, practica=None):
        ruta = (f"/api/lecciones/jugar?unidad={practica[0]}&leccion={practica[1]}" if practica
                else f"/api/lecciones/jugar?seccion={seccion}")
        r = api("GET", ruta, p.token, esperado=None)
        if r.status_code == 409:
            anotar("sin_vidas", nino=p.nombre, seccion=seccion)
            return "sin_vidas"
        if r.status_code == 404:
            return "terminado"
        if r.status_code != 200:
            anotar("errores", ruta="lecciones/jugar", codigo=r.status_code, detalle=r.text[:200])
            return "terminado"
        leccion = r.json()
        prob = p.acierto + (0.03 if en_clase else 0) - (0.06 if seccion == "gramatica" else 0) + (0.08 if practica else 0)
        respuestas, vidas = [], leccion["vidas"]
        for q in leccion["preguntas"]:
            correctas[q["id_actividad"]] = q["respuesta_correcta"]
            bien = azar.random() < prob
            mala = next(o for o in q["opciones"] if o != q["respuesta_correcta"])
            respuestas.append({"id_actividad": q["id_actividad"], "respuesta": q["respuesta_correcta"] if bien else mala})
            if not bien:
                vidas -= 1
                if vidas <= 0:
                    break
        res = api("POST", "/api/lecciones/resultado", p.token,
                  {"unidad": leccion["unidad"]["id"], "leccion": leccion["leccion"], "respuestas": respuestas}).json()
        aciertos = sum(1 for x in respuestas if x["respuesta"] == correctas[x["id_actividad"]])
        if res.get("aprobada") and not practica:
            p.aprobadas.append((leccion["unidad"]["id"], leccion["leccion"]))
        anotar("lecciones", nino=p.nombre, seccion=seccion, en_clase=en_clase, aciertos=aciertos, practica=bool(practica),
               preguntas=len(leccion["preguntas"]), aprobada=bool(res.get("aprobada")),
               mundo_completado=bool(res.get("mundo_completado")))
        p.lecciones.append(seccion)
        return res

    def examen(p, ex, en_clase):
        datos = api("GET", f"/api/examenes/{ex['id_examen']}", p.token).json()
        respuestas = []
        for q in datos["preguntas"]:
            buena = correctas.get(q["id_actividad"], q["opciones"][0])
            bien = azar.random() < p.acierto + 0.04
            mala = next(o for o in q["opciones"] if o != buena)
            respuestas.append({"id_actividad": q["id_actividad"], "respuesta": buena if bien else mala})
        r = api("POST", f"/api/examenes/{ex['id_examen']}/resultado", p.token, {"respuestas": respuestas}).json()
        anotar("examenes", nino=p.nombre, seccion=ex["seccion"], aciertos=r["aciertos"], total=r["total"],
               aprobado=r["aprobado"], primera_vez=r["primera_vez"], en_clase=en_clase,
               premio=bool(r.get("recompensa") and r["recompensa"].get("device_id")))
        if r.get("recompensa") and r["recompensa"].get("device_id"):
            maquina(en_clase)
        return r

    def maquina(en_clase):
        secreto = os.environ.get("SIM_DEVICE_SECRET")
        if not secreto:
            return
        h = {"X-Device-Secret": secreto}
        cola = api("GET", f"/api/recompensas/cola/{DISPOSITIVO}", cabeceras=h, esperado=None)
        if cola.status_code != 200:
            # El secreto local no coincide con el de Render: los premios se quedan en la cola.
            anotar("errores", ruta="recompensas/cola", codigo=cola.status_code, detalle="secreto de la máquina")
            os.environ.pop("SIM_DEVICE_SECRET", None)
            return
        for premio in cola.json():
            api("POST", f"/api/recompensas/{premio['id_historial']}/confirmar-entrega", cabeceras=h)
            anotar("entregas", en_clase=en_clase, id_historial=premio["id_historial"])

    def sesion(p, secciones, objetivo, en_clase):
        if not entrar(p):
            return
        for ex in [e for e in api("GET", "/api/examenes", p.token).json() if e["estado"] == "pendiente"]:
            if en_clase or ex["seccion"] != "profesor":
                r = examen(p, ex, en_clase)
                if not r["aprobado"]:
                    examen(p, ex, en_clase)
        hechas = practicas = 0
        while hechas < objetivo and secciones:
            res = jugar(p, secciones[0], en_clase)
            if res == "terminado":
                secciones.pop(0)
                continue
            if res == "sin_vidas":
                # Sin vidas solo puede practicar una lección ya aprobada: no gasta vidas y, si la
                # aprueba, le devuelve una. Lo intenta unas veces y, si no, termina la sesión.
                if p.aprobadas and practicas < 4:
                    practicas += 1
                    jugar(p, secciones[0], en_clase, practica=azar.choice(p.aprobadas))
                    continue
                break
            hechas += 1
            mundo = res.get("mundo_completado")
            if mundo and mundo.get("examen") and (en_clase or mundo["examen"]["seccion"] != "profesor"):
                r = examen(p, mundo["examen"], en_clase)
                if not r["aprobado"]:
                    examen(p, mundo["examen"], en_clase)
        if azar.random() < 0.3:
            tienda = api("GET", "/api/tienda", p.token).json()
            ya = set(tienda["perfil"].get("comprados", []))
            opciones = [i for i in tienda["items"] if i["precio"] and i["precio"] <= tienda["perfil"]["saldo"] and i["id"] not in ya]
            if opciones:
                item = azar.choice(opciones)
                if api("POST", "/api/tienda/comprar", p.token, {"item_id": item["id"]}, esperado=None).status_code == 200:
                    anotar("eventos", que="compra en la tienda", nino=p.nombre)

    print("Clase: los niños juegan los mundos del profe y presentan sus exámenes…")
    for p in PERFILES:
        if azar.random() < p.asistencia:
            sesion(p, ["profesor", "vocabulario"], 10, True)
            print(f"  {p.nombre}: {len(p.lecciones)} lecciones")
    print("Casa: vocabulario y gramática según el perfil…")
    for p in PERFILES:
        if p.casa:
            secciones = ["gramatica", "vocabulario"] if azar.random() < p.gramatica else ["vocabulario", "gramatica"]
            sesion(p, secciones, azar.randint(*p.lecciones_casa), False)

    # ------------------------------------------------------------- docente y acudientes
    print("La docente revisa su panel y los acudientes consultan…")
    td = login("sim_lmendez", clave)["token"]
    panel = api("GET", f"/api/lecciones/docente/{docente['id_usuario']}", td).json()
    registro["panel_docente"] = {"necesitan_ayuda": panel.get("necesitan_ayuda"), "activos_hoy": panel.get("activos_hoy"),
                                 "progreso_promedio": panel.get("progreso_promedio")}
    for e in [e for e in panel["estudiantes"] if e.get("necesita_ayuda")][:3]:
        texto = f"{e['nombre'].replace('(Sim) ', '').split()[0]} necesita refuerzo: {e['motivos'][0].lower()}. Practiquen 10 minutos diarios."
        api("POST", "/api/feedback", td, {"id_estudiante": e["id_usuario"], "comentario": texto})
        anotar("comentarios", nino=e["nombre"])
    for p in PERFILES:
        if p.nombre in padres:
            s = login(padres[p.nombre]["usuario"], clave)
            for h in api("GET", f"/api/usuarios/padre/{s['id_usuario']}/hijos", s["token"]).json():
                api("GET", f"/api/lecciones/resumen/{h['id_usuario']}", s["token"])
                api("GET", f"/api/feedback/estudiante/{h['id_usuario']}", s["token"])
            anotar("padres", nino=p.nombre)
    registro["pendientes_en_cola"] = None if os.environ.get("SIM_DEVICE_SECRET") else "sin secreto: los premios quedaron en la cola"
    registro["fin"] = ahora()


def desactivar():
    coord = coordinador()
    cuentas = json.load(open(CUENTAS, encoding="utf-8"))
    ids = [a["id"] for a in cuentas["adultos"]] + [e["id"] for e in cuentas["estudiantes"]]
    for i in ids:
        api("PATCH", f"/api/coordinador/usuarios/{i}", coord["token"], {"activo": False})
    print(f"{len(ids)} cuentas simuladas desactivadas.")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("simular", "desactivar"):
        raise SystemExit(__doc__)
    if sys.argv[1] == "desactivar":
        desactivar()
    else:
        if os.path.exists(CUENTAS):  # antes del try: así no se sobrescribe el registro anterior
            raise SystemExit(f"Ya hay una simulación en producción ({CUENTAS}). Desactívala o borra ese archivo antes.")
        os.makedirs(CARPETA, exist_ok=True)
        registro["inicio"] = ahora()
        try:
            simular()
        finally:
            if os.path.exists(CUENTAS):  # solo si esta ejecución alcanzó a crear cuentas
                with open(REGISTRO, "w", encoding="utf-8") as f:
                    json.dump(registro, f, ensure_ascii=False, indent=1)
                print("Registro:", os.path.abspath(REGISTRO))
