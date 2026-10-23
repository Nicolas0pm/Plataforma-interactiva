"""
Resultados de la simulación del salón (DATOS SINTÉTICOS): tablas en JSON/CSV y gráficos.

Uso: python scripts/simulacion/analizar.py <simulacion.db> <registro.json> <carpeta-salida>
"""
import csv
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DB, REGISTRO, SALIDA = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(SALIDA, exist_ok=True)
ZONA = timezone(timedelta(hours=-5))
AZUL, NARANJA, GRIS, TINTA = "#2a78d6", "#eb6834", "#9aa5b1", "#1f2933"

db = sqlite3.connect(DB)
reg = json.load(open(REGISTRO, encoding="utf-8"))
inicio = datetime.fromisoformat(reg["periodo"]["inicio"])


def local(texto):
    fecha = datetime.fromisoformat(texto.replace(" ", "T"))
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(ZONA)


def semana(fecha):
    return (fecha.date() - inicio.date()).days // 7 + 1


nombres = {r[0]: r[1] for r in db.execute("select id_usuario, nombre from usuarios where rol='estudiante'")}
perfiles = {e["id"]: e for e in reg["estudiantes"]}
intentos = [
    {"id": r[0], "fecha": local(r[1]), "seccion": r[2], "modo": r[3], "aciertos": r[4], "total": r[5], "aprobada": r[6]}
    for r in db.execute("select id_usuario, fecha, seccion, modo, aciertos, total, aprobada from intentos_leccion")
]
examenes = reg["examenes"]
semanas = sorted({semana(i["fecha"]) for i in intentos})
ultima = max(semanas)


def precision(lista):
    total = sum(i["total"] for i in lista)
    return round(sum(i["aciertos"] for i in lista) / total, 3) if total else None


# ------------------------------------------------------------- por estudiante
por_estudiante = []
for id_, perfil in perfiles.items():
    suyos = [i for i in intentos if i["id"] == id_]
    sesiones = perfil["sesiones"]
    exs = [e for e in examenes if e["nino"] == perfil["nombre"]]
    mundos = db.execute("select count(*) from progreso_unidades where id_usuario=? and completado_en is not null",
                        (id_,)).fetchone()[0]
    por_estudiante.append({
        "estudiante": perfil["nombre"],
        "perfil": perfil["perfil"],
        "sesiones_clase": sum(1 for s in sesiones if s["en_clase"]),
        "sesiones_casa": sum(1 for s in sesiones if not s["en_clase"]),
        "lecciones_jugadas": len(suyos),
        "lecciones_aprobadas": sum(i["aprobada"] for i in suyos),
        "precision": precision(suyos),
        "precision_semanas_1_2": precision([i for i in suyos if semana(i["fecha"]) <= 2]),
        "precision_ultimas_2": precision([i for i in suyos if semana(i["fecha"]) >= ultima - 1]),
        "mundos_completados": mundos,
        "examenes_aprobados": sum(1 for e in exs if e["aprobado"] and e["primera_vez"]),
        "examenes_presentados": len(exs),
        "examenes_distintos": len({e["id_examen"] for e in exs}),
        "aprobados_al_primer_intento": None,
        "premios": sum(1 for e in exs if e["con_premio"]),
        "veces_sin_vidas": sum(1 for s in reg["sin_vidas"] if s["nino"] == perfil["nombre"]),
        "pin_errado": sum(1 for s in reg["pin_errado"] if s["nino"] == perfil["nombre"]),
    })

# Aprobado al primer intento: el primer registro de cada examen
primer_intento = {}
for e in examenes:
    primer_intento.setdefault(e["id_examen"], e)
for fila in por_estudiante:
    fila["aprobados_al_primer_intento"] = sum(
        1 for e in primer_intento.values() if e["nino"] == fila["estudiante"] and e["aprobado"])

# ------------------------------------------------------------- por semana
por_semana = []
for s in semanas:
    deesta = [i for i in intentos if semana(i["fecha"]) == s]
    viernes = next((x for x in reg["semanas"] if x["semana"] == s), None)
    por_semana.append({
        "semana": s,
        "estudiantes_activos": len({i["id"] for i in deesta}),
        "lecciones": len(deesta),
        "lecciones_aprobadas": sum(i["aprobada"] for i in deesta),
        "precision": precision(deesta),
        "examenes": sum(1 for e in examenes if semana(local(e["fecha"])) == s),
        "necesitan_ayuda_viernes": viernes["necesitan_ayuda"] if viernes else None,
        "progreso_promedio_viernes": viernes["progreso_promedio"] if viernes else None,
    })

# ------------------------------------------------------------- general
horas = Counter(i["fecha"].hour for i in intentos)
en_casa = [i for i in intentos if not (i["fecha"].weekday() in (1, 3) and 9 <= i["fecha"].hour < 10)]
tienda = db.execute("select count(*) from auditoria where tipo='tienda_compra'").fetchone()[0]
logins = db.execute("select count(*) from auditoria where tipo='login_exitoso'").fetchone()[0]
general = {
    "periodo": {"inicio": reg["periodo"]["inicio"], "fin": reg["periodo"]["fin"], "semanas": ultima},
    "estudiantes": len(perfiles),
    "acudientes": sum(1 for e in reg["estudiantes"] if e["acudiente"]),
    "mundos_del_profe": len(reg["mundos_profe"]),
    "lecciones_jugadas": len(intentos),
    "lecciones_aprobadas": sum(i["aprobada"] for i in intentos),
    "por_modo": dict(Counter(i["modo"] for i in intentos)),
    "por_seccion": {sec: {"jugadas": len(l), "precision": precision(l)}
                    for sec, l in ((s, [i for i in intentos if i["seccion"] == s]) for s in ("vocabulario", "gramatica", "profesor"))},
    "precision_general": precision(intentos),
    "precision_semanas_1_2": precision([i for i in intentos if semana(i["fecha"]) <= 2]),
    "precision_ultimas_2": precision([i for i in intentos if semana(i["fecha"]) >= ultima - 1]),
    "parte_en_casa": round(len(en_casa) / len(intentos), 3),
    "mundos_completados": db.execute("select count(*) from progreso_unidades where completado_en is not null").fetchone()[0],
    "examenes_presentados": len(examenes),
    "examenes_aprobados_primer_intento": sum(1 for e in primer_intento.values() if e["aprobado"]),
    "examenes_creados": db.execute("select count(*) from examenes").fetchone()[0],
    "examenes_aprobados": db.execute("select count(*) from examenes where estado='aprobado'").fetchone()[0],
    "examenes_por_seccion": dict(Counter(e["seccion"] for e in examenes)),
    "premios_entregados": len(reg["entregas"]),
    "premios_fuera_de_clase": sum(1 for e in reg["entregas"] if not e["en_clase"]),
    "veces_sin_vidas": len(reg["sin_vidas"]),
    "pin_errado": len(reg["pin_errado"]),
    "bloqueos": len(reg["bloqueos"]),
    "comentarios_docente": len(reg["comentarios"]),
    "consultas_de_padres": len(reg["padres"]),
    "compras_tienda": tienda,
    "inicios_de_sesion": logins,
    "horas": dict(sorted(horas.items())),
}

json.dump({"general": general, "por_estudiante": por_estudiante, "por_semana": por_semana},
          open(os.path.join(SALIDA, "resultados_simulacion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for nombre, filas in (("por_estudiante", por_estudiante), ("por_semana", por_semana)):
    with open(os.path.join(SALIDA, f"{nombre}_simulacion.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)

# ------------------------------------------------------------- gráficos
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": GRIS, "axes.labelcolor": TINTA,
                     "xtick.color": TINTA, "ytick.color": TINTA, "axes.spines.top": False, "axes.spines.right": False})


def guardar(fig, nombre):
    fig.text(0.99, 0.01, "Datos simulados", ha="right", va="bottom", fontsize=9, color=GRIS)
    fig.tight_layout()
    fig.savefig(os.path.join(SALIDA, nombre), dpi=200)
    plt.close(fig)


# 1. Lecciones por semana y estudiantes activos (dos paneles, un eje cada uno)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8))
x = [s["semana"] for s in por_semana]
a1.bar(x, [s["lecciones"] for s in por_semana], color=AZUL, width=0.6)
a1.set_title("Lecciones jugadas por semana (simulación)", loc="left", fontsize=12, color=TINTA)
a1.set_xlabel("Semana")
a1.set_xticks(x)
a1.grid(axis="y", color="#e4e7eb")
a1.set_axisbelow(True)
a2.plot(x, [s["estudiantes_activos"] for s in por_semana], color=AZUL, linewidth=2, marker="o", markersize=7)
con_viernes = [s for s in por_semana if s["necesitan_ayuda_viernes"] is not None]
a2.plot([s["semana"] for s in con_viernes], [s["necesitan_ayuda_viernes"] for s in con_viernes],
        color=NARANJA, linewidth=2, marker="o", markersize=7)
a2.set_ylim(0, 13)
a2.set_title("Estudiantes por semana (simulación)", loc="left", fontsize=12, color=TINTA)
a2.set_xlabel("Semana")
a2.set_xticks(x)
a2.grid(axis="y", color="#e4e7eb")
a2.text(x[-1] + 0.15, por_semana[-1]["estudiantes_activos"], "Activos", color=AZUL, va="center")
a2.text(con_viernes[-1]["semana"] + 0.15, con_viernes[-1]["necesitan_ayuda_viernes"], "Necesitan ayuda (viernes)",
        color=NARANJA, va="center")
a2.set_xlim(0.5, x[-1] + 2.3)
guardar(fig, "uso_por_semana.png")

# 2. Precisión: primeras dos semanas frente a las dos últimas, por estudiante
filas = sorted(por_estudiante, key=lambda f: f["precision_ultimas_2"] or 0)
fig, ax = plt.subplots(figsize=(8, 5.2))
for i, f in enumerate(filas):
    a, b = f["precision_semanas_1_2"], f["precision_ultimas_2"]
    if a is not None and b is not None:
        ax.plot([a * 100, b * 100], [i, i], color=GRIS, linewidth=2, zorder=1)
    if a is not None:
        ax.scatter(a * 100, i, color=GRIS, s=60, zorder=2, edgecolor="white", linewidth=1.5)
    if b is not None:
        ax.scatter(b * 100, i, color=AZUL, s=70, zorder=3, edgecolor="white", linewidth=1.5)
ax.set_yticks(range(len(filas)), [f["estudiante"] for f in filas])
ax.set_xlabel("Aciertos (%)")
ax.set_xlim(30, 100)
ax.grid(axis="x", color="#e4e7eb")
ax.set_axisbelow(True)
ax.set_title("Aciertos al inicio y al final (simulación)", loc="left", fontsize=12, color=TINTA)
ax.scatter([], [], color=GRIS, s=60, label="Semanas 1–2")
ax.scatter([], [], color=AZUL, s=70, label="Últimas 2 semanas")
ax.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncol=2, frameon=False)
guardar(fig, "aciertos_inicio_final.png")

# 3. Hora del día en que se jugó
fig, ax = plt.subplots(figsize=(9, 3.6))
todas = range(6, 24)
en_clase = Counter(i["fecha"].hour for i in intentos if i["fecha"].weekday() in (1, 3) and 9 <= i["fecha"].hour < 10)
ax.bar(todas, [horas.get(h, 0) - en_clase.get(h, 0) for h in todas], color=AZUL, width=0.7, label="En casa")
ax.bar(todas, [en_clase.get(h, 0) for h in todas], bottom=[horas.get(h, 0) - en_clase.get(h, 0) for h in todas],
       color=NARANJA, width=0.7, label="En clase")
ax.set_xticks(list(todas), [f"{h}" for h in todas])
ax.set_xlabel("Hora del día")
ax.set_ylabel("Lecciones")
ax.grid(axis="y", color="#e4e7eb")
ax.set_axisbelow(True)
ax.set_title("Lecciones según la hora del día (simulación)", loc="left", fontsize=12, color=TINTA)
ax.legend(frameon=False)
guardar(fig, "hora_del_dia.png")

print(json.dumps(general, ensure_ascii=False, indent=1))
