"""
Autenticación y autorización de la API.

Todos los tokens los emite esta misma API (JWT HS256) y se envían como
`Authorization: Bearer <token>`:

- **Estudiantes**: entran con su código de acceso + PIN de 4 dígitos (RF01 CA3).
  La sesión dura `JWT_PIN_EXP_MINUTOS` minutos (RNF-SEG-04).
- **Docentes, padres y admin**: entran con correo + contraseña. La contraseña se guarda
  como hash scrypt (con sal propia), nunca en texto plano. La sesión dura
  `JWT_ADULTO_EXP_MINUTOS` minutos.
- **Modo de prueba** (`USE_FAKE_DB=true`): además existe un login de desarrollo sin
  contraseña (`crear_token_dev`), deshabilitado en cualquier otro caso.

Tras `MAX_FALLOS` intentos fallidos seguidos, el código (o el correo) queda bloqueado
`BLOQUEO_MINUTOS` minutos, para que nadie pueda probar contraseñas o PIN sin límite.

`current_user()` revisa la firma y el vencimiento del token y que la cuenta siga activa.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import ahora, get_db
from app.models.tablas import Auditoria, IntentoFallido, Usuario

_settings = get_settings()

MAX_FALLOS = 5
BLOQUEO_MINUTOS = 10

# Parámetros de scrypt (los recomendados por OWASP: ~16 MB de memoria por intento).
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_pin(pin: str) -> str:
    return hashlib.sha256((_settings.pin_pepper + pin).encode()).hexdigest()


def _scrypt(password: str, sal: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=sal, n=n, r=r, p=p, maxmem=64 * 1024 * 1024, dklen=32)


def hash_password(password: str) -> str:
    """"scrypt$n$r$p$sal$hash" (sal y hash en base64)."""
    sal = secrets.token_bytes(16)
    clave = _scrypt(password, sal, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(sal)}${b64(clave)}"


def verificar_password(password: str, guardado: str | None) -> bool:
    if not guardado:
        return False
    try:
        _, n, r, p, sal, clave = guardado.split("$")
        calculada = _scrypt(password, base64.b64decode(sal), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculada, base64.b64decode(clave))


# Para que un correo inexistente tarde lo mismo que una contraseña incorrecta
# (si no, el tiempo de respuesta revelaría qué correos tienen cuenta).
_HASH_DE_RELLENO = hash_password(secrets.token_hex(8))


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def crear_token_sesion(id_usuario: str, rol: str) -> str:
    minutos = _settings.jwt_pin_exp_minutos if rol == "estudiante" else _settings.jwt_adulto_exp_minutos
    momento = ahora()
    payload = {"sub": id_usuario, "rol": rol, "iat": momento, "exp": momento + timedelta(minutes=minutos)}
    return jwt.encode(payload, _settings.jwt_secret, algorithm="HS256")


def crear_token_dev(id_usuario: str, rol: str) -> str:
    """Login de desarrollo para docentes/padres/admin sin contraseña.
    Solo funciona con USE_FAKE_DB=true; en cualquier otro caso está deshabilitado."""
    if not _settings.use_fake_db:
        raise HTTPException(403, "El login de desarrollo solo está disponible con USE_FAKE_DB=true")
    return crear_token_sesion(id_usuario, rol)


def revisar_bloqueo(db: Session, clave: str) -> None:
    """429 si `clave` está bloqueada por demasiados intentos fallidos seguidos."""
    intentos = db.get(IntentoFallido, clave)
    if intentos and intentos.bloqueado_hasta and intentos.bloqueado_hasta > ahora():
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos y vuelve a intentar.")


def anotar_intento(db: Session, clave: str, correcto: bool) -> None:
    """Un acierto reinicia el contador; el fallo número `MAX_FALLOS` bloquea la clave."""
    intentos = db.get(IntentoFallido, clave)
    if correcto:
        if intentos:
            intentos.fallos, intentos.bloqueado_hasta = 0, None
        return
    if intentos is None:
        intentos = IntentoFallido(clave=clave, fallos=0)
        db.add(intentos)
    fallos = intentos.fallos + 1
    bloqueo = ahora() + timedelta(minutes=BLOQUEO_MINUTOS) if fallos >= MAX_FALLOS else None
    intentos.fallos, intentos.bloqueado_hasta = (0 if bloqueo else fallos), bloqueo


def verificar_credenciales(db: Session, email: str, password: str) -> Usuario:
    """El adulto dueño de ese correo y contraseña, o 401 (mismo mensaje si el correo no
    existe, para no revelar qué correos están registrados)."""
    email = normalizar_email(email)
    clave = f"correo:{email}"
    revisar_bloqueo(db, clave)
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    guardado = usuario.password_hash if usuario else None
    correcto = verificar_password(password, guardado or _HASH_DE_RELLENO) and guardado is not None
    correcto = correcto and usuario.activo and usuario.rol != "estudiante"
    anotar_intento(db, clave, correcto)
    if not correcto:
        raise HTTPException(401, "Correo o contraseña incorrectos")
    return usuario


def extraer_token_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Falta el encabezado Authorization: Bearer <token>")
    return authorization.split(" ", 1)[1].strip()


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict:
    """Quién llama: token válido y vigente de una cuenta que existe y sigue activa."""
    token = extraer_token_bearer(authorization)
    try:
        payload = jwt.decode(token, _settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido o expirado") from None
    perfil = db.get(Usuario, payload["sub"])
    if perfil is None or not perfil.activo or perfil.rol != payload["rol"]:
        raise HTTPException(401, "Token inválido o expirado")
    return {"id_usuario": perfil.id_usuario, "rol": perfil.rol}


def require_role(*roles: str):
    """Dependencia de FastAPI: exige que el usuario autenticado tenga uno de `roles`."""

    def _verificar(usuario: dict = Depends(current_user)) -> dict:
        if usuario["rol"] not in roles:
            raise HTTPException(403, "No tienes permiso para realizar esta acción")
        return usuario

    return _verificar


def verificar_acceso_estudiante(usuario: dict, id_estudiante: str, db: Session) -> None:
    """Lanza 403/404 si `usuario` no tiene derecho a ver u operar sobre los datos
    de `id_estudiante`: debe ser admin, el propio estudiante, su docente asignado
    o uno de sus padres/acudientes vinculados (RF11)."""
    if usuario["rol"] == "admin":
        return
    if usuario["rol"] == "estudiante":
        if usuario["id_usuario"] == id_estudiante:
            return
        raise HTTPException(403, "Un estudiante solo puede ver su propia información")

    estudiante = db.get(Usuario, id_estudiante)
    if estudiante is None:
        raise HTTPException(404, "Estudiante no encontrado")

    if usuario["rol"] == "docente" and estudiante.docente_id == usuario["id_usuario"]:
        return
    if usuario["rol"] == "padre" and usuario["id_usuario"] in estudiante.acudientes_ids:
        return
    raise HTTPException(403, "No tienes ningún vínculo con este estudiante")


def registrar_auditoria(db: Session, tipo: str, actor: str | None, detalle: dict | None = None) -> None:
    """RNF-AUD-*: registro de auditoría de solo-inserción (tabla `auditoria`)."""
    db.add(Auditoria(tipo=tipo, actor=actor, detalle=detalle or {}, fecha=ahora()))
