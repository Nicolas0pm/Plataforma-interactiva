"""
Tablas de la base de datos relacional (PostgreSQL). Ver `docs/data-model.md`.

Los identificadores públicos (usuarios, actividades, mundos, recompensas, feedback) son
texto: así se conservan los que venían de Firestore y el frontend no cambia. Los
registros internos que solo se agregan (intentos, errores, auditoría) usan un número
autoincremental.
"""
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, FechaUTC, ahora

JSONTipo = JSON().with_variant(JSONB(), "postgresql")


def nuevo_id() -> str:
    """Identificador aleatorio de 20 caracteres, como los de Firestore."""
    return secrets.token_urlsafe(15)


_FK_USUARIO = "usuarios.id_usuario"


# --------------------------------------------------------------------------- usuarios


class Usuario(Base):
    __tablename__ = "usuarios"
    # El usuario y el correo identifican a un adulto al iniciar sesión: no se repiten.
    __table_args__ = (
        Index("ux_usuarios_usuario", "usuario", unique=True),
        Index("ux_usuarios_email", "email", unique=True),
    )

    id_usuario: Mapped[str] = mapped_column(String(40), primary_key=True, default=nuevo_id)
    nombre: Mapped[str] = mapped_column(String(120))
    edad: Mapped[int] = mapped_column(Integer)
    rol: Mapped[str] = mapped_column(String(20), index=True)  # estudiante | docente | padre | admin
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)

    # Adultos (docente / padre / admin = coordinador): los crea el coordinador y entran
    # con usuario y contraseña.
    usuario: Mapped[Optional[str]] = mapped_column(String(40))  # siempre en minúsculas
    email: Mapped[Optional[str]] = mapped_column(String(254))  # opcional, en minúsculas
    password_hash: Mapped[Optional[str]] = mapped_column(String(200))  # scrypt, nunca la contraseña
    # True mientras tenga la contraseña temporal que le dio el coordinador.
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=False)
    terminos_version: Mapped[Optional[str]] = mapped_column(String(10))
    terminos_fecha: Mapped[Optional[datetime]] = mapped_column(FechaUTC)
    device_id_aula: Mapped[Optional[str]] = mapped_column(String(60))  # solo docentes

    # Estudiantes: entran con código + PIN.
    codigo_acceso: Mapped[Optional[str]] = mapped_column(String(10), unique=True)
    pin_hash: Mapped[Optional[str]] = mapped_column(String(64))
    docente_id: Mapped[Optional[str]] = mapped_column(ForeignKey(_FK_USUARIO), index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(60))
    # Evidencia de la autorización de datos del menor (Ley 1581 / Decreto 1377).
    autorizacion_otorgada_por: Mapped[Optional[str]] = mapped_column(ForeignKey(_FK_USUARIO))
    autorizacion_rol: Mapped[Optional[str]] = mapped_column(String(20))
    autorizacion_fecha: Mapped[Optional[datetime]] = mapped_column(FechaUTC)
    autorizacion_version: Mapped[Optional[str]] = mapped_column(String(10))

    vinculos_acudientes: Mapped[list["Acudiente"]] = relationship(
        foreign_keys="Acudiente.id_estudiante", lazy="selectin", cascade="all, delete-orphan",
        order_by="Acudiente.vinculado_en",
    )

    @property
    def acudientes_ids(self) -> list[str]:
        return [v.id_acudiente for v in self.vinculos_acudientes]

    def a_dict(self) -> dict:
        """Lo que puede salir de la API (sin `pin_hash`)."""
        return {
            "id_usuario": self.id_usuario,
            "nombre": self.nombre,
            "edad": self.edad,
            "rol": self.rol,
            "acudientes_ids": self.acudientes_ids,
            "docente_id": self.docente_id,
            "email": self.email,
            "device_id": self.device_id,
            "activo": self.activo,
            "creado_en": self.creado_en,
            "codigo_acceso": self.codigo_acceso,
            "usuario": self.usuario,
        }


class Acudiente(Base):
    """Padres/acudientes vinculados a un estudiante (RF11): un niño puede tener varios."""

    __tablename__ = "acudientes"

    id_estudiante: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"), primary_key=True)
    id_acudiente: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"), primary_key=True, index=True)
    vinculado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)


class IntentoFallido(Base):
    """Intentos fallidos seguidos de iniciar sesión (bloqueo temporal). `clave` es
    "pin:<código de acceso>" para los niños y "login:<usuario o correo>" para los adultos."""

    __tablename__ = "intentos_fallidos"

    clave: Mapped[str] = mapped_column(String(270), primary_key=True)
    fallos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[Optional[datetime]] = mapped_column(FechaUTC)


# --------------------------------------------------------------------- contenido


class MundoDocente(Base):
    """Mundo que crea un docente (apartado "Del profe")."""

    __tablename__ = "mundos_docente"

    id_mundo: Mapped[str] = mapped_column(String(40), primary_key=True, default=nuevo_id)
    id_docente: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO), index=True)
    titulo: Mapped[str] = mapped_column(String(40))
    emoji: Mapped[str] = mapped_column(String(8), default="🌟")
    descripcion: Mapped[str] = mapped_column(String(140), default="")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)


class Actividad(Base):
    """Una pregunta: del temario fijo (`app/curriculo.py`) o de un mundo del docente."""

    __tablename__ = "actividades"
    __table_args__ = (Index("ix_actividades_unidad_activo", "unidad", "activo"),)

    id_actividad: Mapped[str] = mapped_column(String(80), primary_key=True, default=nuevo_id)
    nombre: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    nivel: Mapped[int] = mapped_column(Integer, default=1)
    tipo: Mapped[str] = mapped_column(String(20), default="vocabulario")
    puntaje_maximo: Mapped[int] = mapped_column(Integer, default=100)
    seccion: Mapped[Optional[str]] = mapped_column(String(20))
    unidad: Mapped[Optional[str]] = mapped_column(String(80))
    leccion: Mapped[Optional[int]] = mapped_column(Integer)
    orden: Mapped[Optional[int]] = mapped_column(BigInteger)
    pregunta: Mapped[Optional[str]] = mapped_column(Text)
    opciones: Mapped[list] = mapped_column(JSONTipo, default=list)
    respuesta_correcta: Mapped[Optional[str]] = mapped_column(Text)
    icono: Mapped[Optional[str]] = mapped_column(String(16))
    imagen: Mapped[Optional[str]] = mapped_column(Text)  # data URL (≤ 300 KB), solo preguntas del docente
    formato_opciones: Mapped[str] = mapped_column(String(10), default="texto")
    id_docente: Mapped[Optional[str]] = mapped_column(ForeignKey(_FK_USUARIO))
    id_mundo: Mapped[Optional[str]] = mapped_column(ForeignKey("mundos_docente.id_mundo"), index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)

    CAMPOS = ("nombre", "descripcion", "nivel", "tipo", "puntaje_maximo", "seccion", "unidad", "leccion",
              "orden", "pregunta", "opciones", "respuesta_correcta", "icono", "imagen", "formato_opciones", "activo")

    def a_dict(self) -> dict:
        return {"id_actividad": self.id_actividad, **{c: getattr(self, c) for c in self.CAMPOS}}


# ---------------------------------------------------------------------- progreso


class Progreso(Base):
    """Progreso acumulado de un estudiante (una fila por estudiante)."""

    __tablename__ = "progreso"

    id_usuario: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"), primary_key=True)
    puntaje_total: Mapped[int] = mapped_column(Integer, default=0)
    nivel_logrado: Mapped[int] = mapped_column(Integer, default=1)
    actividades_completadas: Mapped[int] = mapped_column(Integer, default=0)
    respuestas_totales: Mapped[int] = mapped_column(Integer, default=0)
    respuestas_correctas: Mapped[int] = mapped_column(Integer, default=0)
    # Vidas que tenía en el instante `vidas_desde` (NULL = todas llenas).
    vidas_cantidad: Mapped[Optional[int]] = mapped_column(Integer)
    vidas_desde: Mapped[Optional[datetime]] = mapped_column(FechaUTC)
    # Perfil de la tienda
    avatar: Mapped[Optional[str]] = mapped_column(String(40))
    marco: Mapped[Optional[str]] = mapped_column(String(40))
    puntos_gastados: Mapped[int] = mapped_column(Integer, default=0)
    actualizado_en: Mapped[Optional[datetime]] = mapped_column(FechaUTC)


class ProgresoSeccion(Base):
    """Lecciones nuevas aprobadas desde el último repaso, por apartado."""

    __tablename__ = "progreso_secciones"

    id_usuario: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"), primary_key=True)
    seccion: Mapped[str] = mapped_column(String(20), primary_key=True)
    aprobadas_desde_repaso: Mapped[int] = mapped_column(Integer, default=0)


class ProgresoLeccion(Base):
    __tablename__ = "progreso_lecciones"

    id_usuario: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"), primary_key=True)
    unidad: Mapped[str] = mapped_column(String(80), primary_key=True)
    leccion: Mapped[int] = mapped_column(Integer, primary_key=True)
    aprobada: Mapped[bool] = mapped_column(Boolean, default=False)
    mejor: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    fallos: Mapped[int] = mapped_column(Integer, default=0)
    ultima: Mapped[Optional[datetime]] = mapped_column(FechaUTC)


class ProgresoUnidad(Base):
    """Precisión por tema y, si ya lo terminó, cuándo completó el mundo."""

    __tablename__ = "progreso_unidades"

    id_usuario: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"), primary_key=True)
    unidad: Mapped[str] = mapped_column(String(80), primary_key=True)
    respuestas: Mapped[int] = mapped_column(Integer, default=0)
    correctas: Mapped[int] = mapped_column(Integer, default=0)
    completado_en: Mapped[Optional[datetime]] = mapped_column(FechaUTC)


class ItemComprado(Base):
    __tablename__ = "items_comprados"

    id_usuario: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    comprado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)


class IntentoLeccion(Base):
    """Cada lección jugada (lo que ve el docente: en qué va bien y en qué va mal)."""

    __tablename__ = "intentos_leccion"
    __table_args__ = (Index("ix_intentos_usuario_fecha", "id_usuario", "fecha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_usuario: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"))
    unidad: Mapped[str] = mapped_column(String(80))
    seccion: Mapped[str] = mapped_column(String(20))
    titulo_es: Mapped[str] = mapped_column(String(80))
    titulo_en: Mapped[str] = mapped_column(String(80))
    emoji: Mapped[Optional[str]] = mapped_column(String(16))
    leccion: Mapped[int] = mapped_column(Integer)
    modo: Mapped[str] = mapped_column(String(10))  # nueva | repaso | practica
    aciertos: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    aprobada: Mapped[bool] = mapped_column(Boolean)
    puntos: Mapped[int] = mapped_column(Integer)
    fecha: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)

    errores: Mapped[list["ErrorIntento"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="ErrorIntento.id"
    )

    def a_dict(self) -> dict:
        return {
            "unidad": self.unidad, "seccion": self.seccion,
            "titulo": {"es": self.titulo_es, "en": self.titulo_en}, "emoji": self.emoji,
            "leccion": self.leccion, "modo": self.modo, "aciertos": self.aciertos, "total": self.total,
            "errores": [e.a_dict() for e in self.errores], "aprobada": self.aprobada,
            "puntos": self.puntos, "fecha": self.fecha,
        }


class ErrorIntento(Base):
    """Cada pregunta que el niño respondió mal en un intento."""

    __tablename__ = "errores_intento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_intento: Mapped[int] = mapped_column(ForeignKey("intentos_leccion.id", ondelete="CASCADE"), index=True)
    id_actividad: Mapped[str] = mapped_column(String(80))
    pregunta: Mapped[Optional[str]] = mapped_column(Text)
    icono: Mapped[Optional[str]] = mapped_column(String(16))
    respuesta_dada: Mapped[str] = mapped_column(Text)
    respuesta_correcta: Mapped[Optional[str]] = mapped_column(Text)

    def a_dict(self) -> dict:
        return {"id_actividad": self.id_actividad, "pregunta": self.pregunta, "icono": self.icono,
                "respuesta_dada": self.respuesta_dada, "respuesta_correcta": self.respuesta_correcta}


class HistorialActividad(Base):
    """Endpoint antiguo `/api/actividades/completar` (actividades sueltas)."""

    __tablename__ = "historial_actividades"

    id_historial: Mapped[str] = mapped_column(String(40), primary_key=True, default=nuevo_id)
    id_usuario: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"), index=True)
    id_actividad: Mapped[str] = mapped_column(String(80))
    fecha: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)
    tiempo_empleado: Mapped[int] = mapped_column(Integer)
    intentos: Mapped[int] = mapped_column(Integer)
    puntaje_obtenido: Mapped[int] = mapped_column(Integer)


# ---------------------------------------------------------- recompensas y otros


class HistorialRecompensa(Base):
    __tablename__ = "historial_recompensas"

    id_historial: Mapped[str] = mapped_column(String(40), primary_key=True, default=nuevo_id)
    id_usuario: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), default="umbral")  # mundo | umbral
    unidad: Mapped[Optional[str]] = mapped_column(String(80))
    titulo_es: Mapped[Optional[str]] = mapped_column(String(80))
    titulo_en: Mapped[Optional[str]] = mapped_column(String(80))
    emoji: Mapped[Optional[str]] = mapped_column(String(16))
    fecha_entrega: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)
    puntos_consumidos: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(String(20))  # pendiente | celebrada | entregada
    device_id: Mapped[Optional[str]] = mapped_column(String(60))

    def a_dict(self) -> dict:
        datos = {
            "id_historial": self.id_historial, "id_usuario": self.id_usuario, "tipo": self.tipo,
            "fecha_entrega": self.fecha_entrega, "puntos_consumidos": self.puntos_consumidos,
            "estado": self.estado, "device_id": self.device_id,
        }
        if self.tipo == "mundo":
            datos |= {"unidad": self.unidad, "titulo": {"es": self.titulo_es, "en": self.titulo_en}, "emoji": self.emoji}
        return datos


class Feedback(Base):
    __tablename__ = "feedback"

    id_feedback: Mapped[str] = mapped_column(String(40), primary_key=True, default=nuevo_id)
    id_estudiante: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO, ondelete="CASCADE"), index=True)
    id_docente: Mapped[str] = mapped_column(ForeignKey(_FK_USUARIO))
    comentario: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(20), default="progreso")
    visible_para_padres: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha: Mapped[datetime] = mapped_column(FechaUTC, default=ahora)

    def a_dict(self) -> dict:
        return {c: getattr(self, c) for c in
                ("id_feedback", "id_estudiante", "id_docente", "comentario", "tipo", "visible_para_padres", "fecha")}


class Auditoria(Base):
    """RNF-AUD-*: registro de solo-inserción (la API nunca edita ni borra filas aquí)."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(40), index=True)
    actor: Mapped[Optional[str]] = mapped_column(String(40))  # id de usuario, "esp32" o NULL
    detalle: Mapped[dict] = mapped_column(JSONTipo, default=dict)
    fecha: Mapped[datetime] = mapped_column(FechaUTC, default=ahora, index=True)
