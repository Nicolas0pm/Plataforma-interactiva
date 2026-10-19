"""Ayudas para las pruebas: las cuentas se crean como en la vida real (el coordinador las
crea por la API y cada adulto cambia su contraseña temporal al primer ingreso)."""
from app.db import SesionLocal
from app.models.tablas import Usuario
from app.services.auth_service import crear_token_sesion, hash_password

PASSWORD = "clave-segura-1"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def crear_coordinador(usuario: str = "coordinacion") -> tuple[str, str]:
    """El primer coordinador (en producción lo crea scripts/asignar_password.py). → (id, token)"""
    with SesionLocal.begin() as db:
        coord = Usuario(nombre="Coordinación", edad=0, rol="admin", usuario=usuario,
                        password_hash=hash_password(PASSWORD), activo=True, terminos_version="1.1")
        db.add(coord)
        db.flush()
        id_coord = coord.id_usuario
    return id_coord, crear_token_sesion(id_coord, "admin")


def crear_adulto(client, token_coord: str, rol: str, usuario: str, nombre: str = "Adulto") -> tuple[dict, str]:
    """El coordinador crea la cuenta y la persona entra y cambia su contraseña. → (perfil, token)"""
    creado = client.post("/api/coordinador/adultos", headers=auth(token_coord),
                         json={"nombre": nombre, "rol": rol, "usuario": usuario})
    assert creado.status_code == 201, creado.text
    sesion = client.post("/api/usuarios/login", json={"usuario": usuario, "password": creado.json()["password_temporal"]})
    assert sesion.status_code == 200 and sesion.json()["debe_cambiar_password"] is True, sesion.text
    token = sesion.json()["token"]
    cambio = client.post("/api/usuarios/cambiar-password", headers=auth(token), json={
        "actual": creado.json()["password_temporal"], "nueva": PASSWORD, "acepta_terminos": True,
    })
    assert cambio.status_code == 200, cambio.text
    return creado.json(), token


def crear_nino(client, token_coord: str, nombre: str = "Ana", pin: str = "1234",
               docente_id: str | None = None, acudientes_ids: tuple = ()) -> dict:
    r = client.post("/api/coordinador/estudiantes", headers=auth(token_coord), json={
        "nombre": nombre, "edad": 7, "pin": pin, "docente_id": docente_id,
        "acudientes_ids": list(acudientes_ids), "autoriza_datos_menor": True,
    })
    assert r.status_code == 201, r.text
    return r.json()


def login_nino(client, nino: dict, pin: str = "1234") -> str:
    r = client.post("/api/usuarios/login-pin", json={"codigo": nino["codigo_acceso"], "pin": pin})
    assert r.status_code == 200, r.text
    return r.json()["token"]
