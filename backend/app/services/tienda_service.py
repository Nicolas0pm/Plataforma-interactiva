"""
Tienda del perfil: los puntos que gana el niño se gastan en cosas para su perfil
(avatares y marcos). El premio físico de la máquina NO se compra: llega al completar un
mundo (ver `recompensas_service.recompensa_por_mundo`).

- `puntaje_total` es todo lo ganado (define el nivel y nunca baja).
- `perfil.puntos_gastados` es lo que ha gastado; el saldo disponible es la diferencia.

El perfil se guarda junto al progreso, en `usuarios/{id}/resultados/actual.perfil`.
"""
from fastapi import HTTPException

ITEMS = [
    # Avatares (emoji grande en el panel del niño)
    {"id": "avatar-zorro", "tipo": "avatar", "emoji": "🦊", "precio": 0, "nombre": {"es": "Zorrito", "en": "Fox"}},
    {"id": "avatar-gato", "tipo": "avatar", "emoji": "🐱", "precio": 100, "nombre": {"es": "Gatito", "en": "Kitty"}},
    {"id": "avatar-panda", "tipo": "avatar", "emoji": "🐼", "precio": 100, "nombre": {"es": "Panda", "en": "Panda"}},
    {"id": "avatar-rana", "tipo": "avatar", "emoji": "🐸", "precio": 100, "nombre": {"es": "Rana", "en": "Frog"}},
    {"id": "avatar-tigre", "tipo": "avatar", "emoji": "🐯", "precio": 150, "nombre": {"es": "Tigre", "en": "Tiger"}},
    {"id": "avatar-pinguino", "tipo": "avatar", "emoji": "🐧", "precio": 150, "nombre": {"es": "Pingüino", "en": "Penguin"}},
    {"id": "avatar-leon", "tipo": "avatar", "emoji": "🦁", "precio": 200, "nombre": {"es": "León", "en": "Lion"}},
    {"id": "avatar-robot", "tipo": "avatar", "emoji": "🤖", "precio": 250, "nombre": {"es": "Robot", "en": "Robot"}},
    {"id": "avatar-unicornio", "tipo": "avatar", "emoji": "🦄", "precio": 300, "nombre": {"es": "Unicornio", "en": "Unicorn"}},
    {"id": "avatar-dragon", "tipo": "avatar", "emoji": "🐲", "precio": 400, "nombre": {"es": "Dragón", "en": "Dragon"}},
    # Marcos para el avatar (se dibujan con CSS: .marco-<id>)
    {"id": "marco-arcoiris", "tipo": "marco", "emoji": "🌈", "precio": 100, "nombre": {"es": "Arcoíris", "en": "Rainbow"}},
    {"id": "marco-estrellas", "tipo": "marco", "emoji": "⭐", "precio": 100, "nombre": {"es": "Estrellas", "en": "Stars"}},
    {"id": "marco-hielo", "tipo": "marco", "emoji": "❄️", "precio": 150, "nombre": {"es": "Hielo", "en": "Ice"}},
    {"id": "marco-fuego", "tipo": "marco", "emoji": "🔥", "precio": 150, "nombre": {"es": "Fuego", "en": "Fire"}},
    {"id": "marco-oro", "tipo": "marco", "emoji": "👑", "precio": 250, "nombre": {"es": "Oro", "en": "Gold"}},
    {"id": "marco-galaxia", "tipo": "marco", "emoji": "🌌", "precio": 350, "nombre": {"es": "Galaxia", "en": "Galaxy"}},
]
POR_ID = {item["id"]: item for item in ITEMS}
AVATAR_INICIAL = "avatar-zorro"


def perfil_de(progreso: dict) -> dict:
    perfil = dict(progreso.get("perfil") or {})
    perfil.setdefault("avatar", AVATAR_INICIAL)
    perfil.setdefault("marco", None)
    perfil.setdefault("comprados", [AVATAR_INICIAL])
    perfil.setdefault("puntos_gastados", 0)
    perfil["saldo"] = progreso.get("puntaje_total", 0) - perfil["puntos_gastados"]
    perfil["avatar_emoji"] = POR_ID.get(perfil["avatar"], POR_ID[AVATAR_INICIAL])["emoji"]
    return perfil


def _guardar_perfil(progreso: dict, perfil: dict) -> None:
    progreso["perfil"] = {k: perfil[k] for k in ("avatar", "marco", "comprados", "puntos_gastados")}


def comprar(progreso: dict, item_id: str) -> dict:
    item = POR_ID.get(item_id)
    if item is None:
        raise HTTPException(404, "Ese artículo no existe")
    perfil = perfil_de(progreso)
    if item_id in perfil["comprados"]:
        raise HTTPException(400, "Ya tienes ese artículo")
    if perfil["saldo"] < item["precio"]:
        raise HTTPException(400, "No te alcanzan los puntos todavía")
    perfil["comprados"].append(item_id)
    perfil["puntos_gastados"] += item["precio"]
    perfil[item["tipo"]] = item_id  # se equipa al comprarlo
    _guardar_perfil(progreso, perfil)
    return perfil_de(progreso)


def equipar(progreso: dict, item_id: str | None, tipo: str) -> dict:
    perfil = perfil_de(progreso)
    if item_id is None:
        if tipo != "marco":
            raise HTTPException(400, "Siempre necesitas un avatar")
        perfil["marco"] = None
    else:
        item = POR_ID.get(item_id)
        if item is None or item_id not in perfil["comprados"]:
            raise HTTPException(400, "Primero tienes que comprar ese artículo")
        perfil[item["tipo"]] = item_id
    _guardar_perfil(progreso, perfil)
    return perfil_de(progreso)
