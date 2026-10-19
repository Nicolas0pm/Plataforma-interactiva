import os
from functools import lru_cache

from dotenv import load_dotenv

# La DATABASE_URL que viene de la terminal (no del archivo .env): en modo de prueba solo se
# usa esta, para que USE_FAKE_DB=true nunca termine conectado a la base real del .env.
_DATABASE_URL_EXPLICITA = os.environ.get("DATABASE_URL", "")

load_dotenv()


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    cors_origins: list[str] = [
        origen.strip() for origen in os.getenv("CORS_ORIGINS", "*").split(",") if origen.strip()
    ]
    # No es válido (ni lo aceptan los navegadores) combinar credenciales con "*":
    # solo se permiten cookies/credenciales cuando la lista de orígenes es explícita.
    cors_allow_credentials: bool = cors_origins != ["*"]

    # Versión vigente de frontend/terminos.html. Si cambia el texto, se sube la versión
    # para saber qué versión aceptó cada adulto (Ley 1581 / Decreto 1377).
    terminos_version: str = "1.1"

    # Horas respecto a UTC para decidir qué es "hoy" (Colombia: -5, sin horario de verano).
    zona_horaria_utc: int = int(os.getenv("ZONA_HORARIA_UTC", "-5"))

    reward_threshold: int = int(os.getenv("REWARD_THRESHOLD", "100"))

    # RF04: umbrales de puntaje acumulado para desbloquear cada nivel. Agregar un
    # nivel nuevo es agregar una entrada aquí + su mundo correspondiente en
    # frontend/js/pages/kid-dashboard.js (deben quedar sincronizados).
    nivel_umbrales: dict[int, int] = {1: 0, 2: 150, 3: 400, 4: 700, 5: 1100, 6: 1550}

    # Autenticación
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-cambiar-en-produccion")
    jwt_pin_exp_minutos: int = int(os.getenv("JWT_PIN_EXP_MINUTOS", "30"))  # RNF-SEG-04
    # Docentes y padres: una jornada (el panel del docente se deja abierto en clase).
    jwt_adulto_exp_minutos: int = int(os.getenv("JWT_ADULTO_EXP_MINUTOS", "480"))
    pin_pepper: str = os.getenv("PIN_PEPPER", "dev-pepper-cambiar-en-produccion")

    # Secreto compartido simple para que el ESP32 confirme entregas sin necesitar
    # una cuenta de usuario completa (fase futura, ver esp32/README.md).
    device_shared_secret: str = os.getenv("DEVICE_SHARED_SECRET", "")

    # Modo de desarrollo: base de datos SQLite en memoria y login de desarrollo sin
    # contraseña, para poder correr y probar la API sin credenciales (ver app/db.py).
    # NUNCA activar en producción.
    use_fake_db: bool = _parse_bool(os.getenv("USE_FAKE_DB", "false"))

    # Base de datos relacional (PostgreSQL en Neon). Formato:
    #   postgresql://usuario:clave@host/base?sslmode=require
    # En modo de prueba se usa SQLite en memoria (se borra al apagar), salvo que la terminal
    # pase otra DATABASE_URL a propósito (p. ej. las pruebas con TEST_DATABASE_URL).
    database_url: str = (_DATABASE_URL_EXPLICITA or "sqlite://") if use_fake_db else os.getenv("DATABASE_URL", "")
    if database_url.startswith(("postgres://", "postgresql://")):
        # Neon entrega "postgresql://..."; SQLAlchemy necesita saber que el driver es psycopg 3.
        database_url = "postgresql+psycopg://" + database_url.split("://", 1)[1]


@lru_cache
def get_settings() -> Settings:
    return Settings()
