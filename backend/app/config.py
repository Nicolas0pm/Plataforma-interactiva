import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    firebase_credentials_path: str = os.getenv(
        "FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json"
    )
    # En un servidor (Render, Cloud Run...) no hay archivo serviceAccountKey.json: se pasa
    # su contenido completo en esta variable (JSON tal cual, o codificado en base64).
    # Si está definida, tiene prioridad sobre FIREBASE_CREDENTIALS_PATH.
    firebase_credentials_json: str = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
    firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")
    realtime_db_url: str = os.getenv("FIREBASE_REALTIME_DB_URL", "")

    cors_origins: list[str] = [
        origen.strip() for origen in os.getenv("CORS_ORIGINS", "*").split(",") if origen.strip()
    ]
    # No es válido (ni lo aceptan los navegadores) combinar credenciales con "*":
    # solo se permiten cookies/credenciales cuando la lista de orígenes es explícita.
    cors_allow_credentials: bool = cors_origins != ["*"]

    # Versión vigente de frontend/terminos.html. Si cambia el texto, se sube la versión
    # para saber qué versión aceptó cada adulto (Ley 1581 / Decreto 1377).
    terminos_version: str = "1.0"

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
    pin_pepper: str = os.getenv("PIN_PEPPER", "dev-pepper-cambiar-en-produccion")

    # Secreto compartido simple para que el ESP32 confirme entregas sin necesitar
    # una cuenta de usuario completa (fase futura, ver esp32/README.md).
    device_shared_secret: str = os.getenv("DEVICE_SHARED_SECRET", "")

    # Correo (código para confirmar el correo de docentes y padres, ver correo_service.py).
    # Con BREVO_API_KEY se usa Brevo; si no, con SMTP_HOST se usa SMTP; si no hay ninguno,
    # el correo solo se escribe en el log del servidor.
    email_remitente: str = os.getenv("EMAIL_REMITENTE", "")
    email_remitente_nombre: str = os.getenv("EMAIL_REMITENTE_NOMBRE", "¡Aprendamos inglés!")
    brevo_api_key: str = os.getenv("BREVO_API_KEY", "")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_usuario: str = os.getenv("SMTP_USUARIO", "")
    smtp_clave: str = os.getenv("SMTP_CLAVE", "")

    # Modo de desarrollo: usa una base de datos en memoria en vez de Firestore real,
    # para poder correr y probar la API sin credenciales de Firebase (ver
    # app/services/fake_firestore.py). NUNCA activar en producción.
    use_fake_db: bool = _parse_bool(os.getenv("USE_FAKE_DB", "false"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
