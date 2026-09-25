"""RF04: la progresión por niveles.

El nivel alcanzado se deriva del puntaje total acumulado (no se guarda una
decisión manual), comparándolo contra los umbrales definidos en
`Settings.nivel_umbrales`. Así, subir de nivel es una consecuencia automática
de jugar actividades y nunca puede "atascarse" desincronizado del puntaje.
"""
from app.config import get_settings

_settings = get_settings()


def calcular_nivel(puntaje_total: int) -> int:
    nivel_alcanzado = 1
    for nivel, umbral in sorted(_settings.nivel_umbrales.items()):
        if puntaje_total >= umbral:
            nivel_alcanzado = nivel
    return nivel_alcanzado


def nivel_maximo() -> int:
    return max(_settings.nivel_umbrales)


def puntos_para_siguiente_nivel(puntaje_total: int) -> int | None:
    """Cuántos puntos faltan para el próximo nivel, o None si ya está en el máximo."""
    nivel_actual = calcular_nivel(puntaje_total)
    siguiente = nivel_actual + 1
    umbral_siguiente = _settings.nivel_umbrales.get(siguiente)
    if umbral_siguiente is None:
        return None
    return max(0, umbral_siguiente - puntaje_total)
