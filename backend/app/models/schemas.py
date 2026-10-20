from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

Rol = Literal["estudiante", "docente", "padre", "admin"]
# Los largos máximos coinciden con las columnas de app/models/tablas.py: PostgreSQL rechaza
# un texto más largo que su columna, y así se responde 422 en vez de un error 500.
IdUsuario = Annotated[str, Field(max_length=40)]
Email = Annotated[str, Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
# Contraseña de adultos: mínimo 8 caracteres; el máximo evita gastar CPU en el hash.
Password = Annotated[str, Field(min_length=8, max_length=128)]
# Usuario de login de los adultos: corto, en minúsculas, sin espacios (p. ej. "mgarcia").
NombreUsuario = Annotated[str, Field(min_length=3, max_length=40, pattern=r"^[a-z0-9._-]+$")]
Pin = Annotated[str, Field(pattern=r"^\d{4}$", description="Exactamente 4 dígitos")]


class UsuarioBase(BaseModel):
    nombre: str = Field(max_length=120)
    edad: int
    rol: Rol
    acudientes_ids: list[IdUsuario] = Field(
        default_factory=list, description="Uno o más padres/acudientes vinculados (RF11)"
    )
    docente_id: Optional[IdUsuario] = None
    email: Optional[Email] = None
    device_id: Optional[str] = Field(
        default=None,
        max_length=60,
        description="Solo estudiantes: dispensador ESP32 asignado (fase futura del hardware). "
        "Si es None, el estudiante no tiene un dispensador sincronizado y el frontend no le "
        "muestra el aviso de 'recompensa física' al ganar una recompensa.",
    )


class CrearAdulto(BaseModel):
    """El coordinador crea la cuenta de un docente, un padre u otro coordinador."""
    nombre: str = Field(min_length=1, max_length=120)
    rol: Literal["docente", "padre", "admin"]
    usuario: NombreUsuario
    email: Optional[Email] = None


class CrearEstudiante(BaseModel):
    """El coordinador registra a un niño (RF01) y le asigna su docente y sus acudientes."""
    nombre: str = Field(min_length=1, max_length=120)
    edad: int = Field(ge=3, le=15)
    pin: Pin
    docente_id: Optional[IdUsuario] = None
    acudientes_ids: list[IdUsuario] = Field(default_factory=list)
    autoriza_datos_menor: bool = Field(
        default=False,
        description="El coordinador declara contar con la autorización del padre/madre o "
        "acudiente para tratar los datos del niño (Ley 1581 de 2012, Decreto 1377 de 2013).",
    )


class AsignarEstudiante(BaseModel):
    """Cambia el docente y/o los acudientes de un niño (lo que no se envía no cambia)."""
    docente_id: Optional[IdUsuario] = None
    quitar_docente: bool = False
    acudientes_ids: Optional[list[IdUsuario]] = None


class CambiarEstado(BaseModel):
    """El coordinador edita una cuenta (RF01): todo es opcional; solo cambia lo que llega."""
    activo: Optional[bool] = None
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=120)
    edad: Optional[int] = Field(default=None, ge=3, le=15)  # solo estudiantes
    email: Optional[Email | Literal[""]] = None  # solo adultos; "" lo quita


class NuevoPin(BaseModel):
    pin: Pin


class UsuarioOut(UsuarioBase):
    """Nunca incluye el PIN ni su hash: no debe salir de la API una vez creado."""

    id_usuario: str
    activo: bool = True
    creado_en: Optional[datetime] = None
    codigo_acceso: Optional[str] = Field(
        default=None,
        description="Solo estudiantes: código corto (6 caracteres) que el niño escribe "
        "en el login junto con su PIN.",
    )
    usuario: Optional[str] = Field(default=None, description="Adultos: su usuario de login.")


class LoginRequest(BaseModel):
    """Docente/padre/coordinador: inicio de sesión con su usuario (o su correo) y contraseña."""
    usuario: str = Field(max_length=254)
    password: str = Field(max_length=128)


class CambiarPassword(BaseModel):
    actual: str = Field(max_length=128)
    nueva: Password
    acepta_terminos: bool = Field(
        default=False,
        description="Obligatorio en el primer ingreso: acepta los Términos de uso y la "
        "Política de datos (frontend/terminos.html).",
    )


class PinLoginRequest(BaseModel):
    """RF01 CA3: acceso simplificado del estudiante mediante código corto + PIN."""
    codigo: str = Field(max_length=20, description="Código de acceso del estudiante (p. ej. K7M3QX)")
    pin: str


class SesionOut(BaseModel):
    token: str
    id_usuario: str
    rol: Rol
    nombre: Optional[str] = None
    codigo_acceso: Optional[str] = None
    # Adultos: true con la contraseña temporal que les dio el coordinador; deben cambiarla
    # (y aceptar los términos) antes de usar su panel.
    debe_cambiar_password: bool = False


class ActividadCreate(BaseModel):
    nombre: str = Field(max_length=200)
    descripcion: str = ""
    nivel: int = Field(ge=1, le=10, description="El máximo alcanzable lo define config.nivel_umbrales")
    tipo: Literal["vocabulario", "gramatica"] = "vocabulario"
    puntaje_maximo: int = 100
    # Ubicación en el temario (app/curriculo.py). Las actividades sin unidad quedan
    # fuera del camino guiado de lecciones.
    seccion: Optional[Literal["vocabulario", "gramatica"]] = None
    unidad: Optional[str] = Field(default=None, max_length=80)
    leccion: Optional[int] = Field(default=None, ge=1)
    orden: Optional[int] = Field(default=None, ge=1)
    formato_opciones: Literal["texto", "emoji"] = "texto"
    # Contenido interpretado por el frontend (frontend/activity.html) para renderizar
    # la actividad sin necesidad de tocar código (RNF-ESC-01): imagen, pregunta y
    # opciones con la respuesta correcta marcada.
    pregunta: Optional[str] = None
    opciones: list[str] = Field(default_factory=list)
    respuesta_correcta: Optional[str] = None
    icono: Optional[str] = Field(
        default=None, max_length=16, description="Emoji o ícono corto que ilustra la actividad/pregunta"
    )


class ActividadOut(ActividadCreate):
    id_actividad: str
    activo: bool = True


class ResultadoActividad(BaseModel):
    """Payload que envía el frontend cuando un niño termina una actividad (RF03/RF04)."""
    id_actividad: str = Field(max_length=80)
    tiempo_empleado: int = Field(ge=0, description="segundos")
    intentos: int = Field(ge=1)
    puntaje_obtenido: int = Field(ge=0)


class RespuestaLeccion(BaseModel):
    id_actividad: str
    respuesta: str
    tiempo_ms: int = Field(default=0, ge=0)


class ResultadoLeccion(BaseModel):
    """Lo que envía el frontend al terminar (o perder) una lección. El servidor califica
    comparando cada respuesta con la correcta: no confía en un puntaje del cliente."""
    unidad: str
    leccion: int = Field(ge=1)
    respuestas: list[RespuestaLeccion] = Field(min_length=1, max_length=50)


class FeedbackCreate(BaseModel):
    id_estudiante: IdUsuario
    comentario: str
    tipo: Literal["progreso", "conducta", "recomendacion"] = "progreso"
    visible_para_padres: bool = True


class FeedbackOut(FeedbackCreate):
    id_feedback: str
    id_docente: str
    fecha: Optional[datetime] = None
