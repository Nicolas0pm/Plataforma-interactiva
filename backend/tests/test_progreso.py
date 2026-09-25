from app.services.progreso_service import calcular_nivel, nivel_maximo, puntos_para_siguiente_nivel


def test_calcular_nivel_umbrales():
    assert calcular_nivel(0) == 1
    assert calcular_nivel(149) == 1
    assert calcular_nivel(150) == 2
    assert calcular_nivel(399) == 2
    assert calcular_nivel(400) == 3
    assert calcular_nivel(699) == 3
    assert calcular_nivel(700) == 4
    assert calcular_nivel(1099) == 4
    assert calcular_nivel(1100) == 5
    assert calcular_nivel(1549) == 5
    assert calcular_nivel(1550) == 6
    assert calcular_nivel(10_000) == 6  # se queda en el nivel máximo definido


def test_puntos_para_siguiente_nivel():
    assert puntos_para_siguiente_nivel(0) == 150
    assert puntos_para_siguiente_nivel(100) == 50
    assert puntos_para_siguiente_nivel(400) == 300  # falta para nivel 4 (umbral 700)
    assert puntos_para_siguiente_nivel(1100) == 450  # falta para nivel 6 (umbral 1550)
    assert puntos_para_siguiente_nivel(1550) is None  # ya está en el nivel máximo
    assert puntos_para_siguiente_nivel(10_000) is None


def test_nivel_maximo():
    assert nivel_maximo() == 6
