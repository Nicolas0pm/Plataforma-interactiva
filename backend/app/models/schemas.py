from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Rol = Literal["estudiante", "docente", "padre", "admin"]


class UsuarioBase(BaseModel):
    nombre: str
    edad: int
    rol: Rol
    acudientes_ids: list[str] = Field(
        default_factory=list, description="Uno o más padres/acudientes vinculados (RF11)"
    )
    docente_id: Optional[str] = None
    email: Optional[str] = None
    device_id: Optional[str] = Field(
        default=None,
        description="Solo estudiantes: dispensador ESP32 asignado (fase futura del hardware). "
        "Si es None, el estudiante no tiene un dispensador sincronizado y el frontend no le "
        "muestra el aviso de 'recompensa física' al ganar una recompensa.",
    )


class UsuarioCreate(UsuarioBase):
    pin_acceso: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}$",
        description="Solo para estudiantes: PIN de exactamente 4 dígitos (el teclado del "
        "login infantil solo admite 4). La API lo convierte a hash antes de guardarlo; "
        "nunca se devuelve ni se almacena en texto plano.",
    )
    auth_uid: Optional[str] = Field(
        default=None, description="UID de Firebase Authentication, para docentes/padres/admin"
    )
    acepta_terminos: bool = Field(
        default=False,
        description="Docente/padre/admin: acepta los Términos de uso y la Política de datos "
        "(frontend/terminos.html). Obligatorio al auto-registrarse.",
    )
    autoriza_datos_menor: bool = Field(
        default=False,
        description="Estudiante: el adulto que lo registra declara contar con la autorización "
        "del padre/madre o acudiente para tratar los datos del niño (Ley 1581 de 2012, "
        "Decreto 1377 de 2013). Obligatorio al crear un estudiante.",
    )


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


class PinLoginRequest(BaseModel):
    """RF01 CA3: acceso simplificado del estudiante mediante código corto + PIN."""
    codigo: str = Field(description="Código de acceso del estudiante (p. ej. K7M3QX)")
    pin: str


class DevLoginRequest(BaseModel):
    """Login de desarrollo (solo con USE_FAKE_DB=true) para docentes/padres/admin
    sin necesitar un proyecto de Firebase Authentication real."""
    id_usuario: str
    rol: Literal["docente", "padre", "admin"]


class SesionOut(BaseModel):
    token: str
    id_usuario: str
    rol: Rol
    nombre: Optional[str] = None
    codigo_acceso: Optional[str] = None


class VincularConPin(BaseModel):
    """RF07/RF11: un padre o docente se vincula con un estudiante que ya existe,
    demostrando que tiene acceso a su cuenta (código de acceso + PIN del niño)."""
    codigo: str
    pin: str


class ActividadCreate(BaseModel):
    nombre: str
    descripcion: str = ""
    nivel: int = Field(ge=1, le=10, description="El máximo alcanzable lo define config.nivel_umbrales")
    tipo: Literal["vocabulario", "gramatica"] = "vocabulario"
    puntaje_maximo: int = 100
    # Ubicación en el temario (app/curriculo.py). Las actividades sin unidad quedan
    # fuera del camino guiado de lecciones.
    seccion: Optional[Literal["vocabulario", "gramatica"]] = None
    unidad: Optional[str] = None
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
        default=None, description="Emoji o ícono corto que ilustra la actividad/pregunta"
    )


class ActividadOut(ActividadCreate):
    id_actividad: str
    activo: bool = True


class ResultadoActividad(BaseModel):
    """Payload que envía el frontend cuando un niño termina una actividad (RF03/RF04)."""
    id_actividad: str
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
    id_estudiante: str
    comentario: str
    tipo: Literal["progreso", "conducta", "recomendacion"] = "progreso"
    visible_para_padres: bool = True


class FeedbackOut(FeedbackCreate):
    id_feedback: str
    id_docente: str
    fecha: Optional[datetime] = None
