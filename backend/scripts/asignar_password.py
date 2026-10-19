"""
Le pone una contraseña temporal a una cuenta de adulto (docente, padre o admin), o crea
una cuenta de administrador. Como la plataforma no envía correos, así se recupera una
cuenta que olvidó su contraseña: el admin corre esto y le entrega la contraseña temporal
a la persona, que después la cambia desde su panel.

Uso (desde backend/, con DATABASE_URL en .env):
    python scripts/asignar_password.py profe@colegio.edu.co
    python scripts/asignar_password.py admin@colegio.edu.co --crear-admin "Nombre del admin"
"""
import argparse
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SesionLocal, ahora, crear_tablas  # noqa: E402
from app.models.tablas import Usuario  # noqa: E402
from app.services.auth_service import hash_password, normalizar_email, registrar_auditoria  # noqa: E402

# Sin caracteres que se confundan al dictarlos (0/O, 1/l/I).
_ALFABETO = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cuenta", help="Correo (o id de usuario) de la cuenta")
    parser.add_argument("--crear-admin", metavar="NOMBRE", help="Crea una cuenta de admin con ese correo")
    args = parser.parse_args()

    if get_settings().use_fake_db:
        raise SystemExit("USE_FAKE_DB=true: este script es para la base de datos real (DATABASE_URL).")
    crear_tablas()
    temporal = "".join(secrets.choice(_ALFABETO) for _ in range(12))
    with SesionLocal.begin() as db:
        if args.crear_admin:
            email = normalizar_email(args.cuenta)
            if db.scalar(select(Usuario).where(Usuario.email == email)):
                raise SystemExit(f"Ya existe una cuenta con {email}.")
            usuario = Usuario(nombre=args.crear_admin, edad=99, rol="admin", email=email, activo=True,
                              terminos_version=get_settings().terminos_version, terminos_fecha=ahora())
            db.add(usuario)
            db.flush()
        else:
            usuario = db.scalar(select(Usuario).where(Usuario.email == normalizar_email(args.cuenta)))
            usuario = usuario or db.get(Usuario, args.cuenta)
            if usuario is None or usuario.rol == "estudiante":
                raise SystemExit("No hay ninguna cuenta de adulto con ese correo o id.")
        usuario.password_hash = hash_password(temporal)
        registrar_auditoria(db, tipo="password_asignada", actor=None, detalle={"id_usuario": usuario.id_usuario})

    print(f"Cuenta: {usuario.nombre} ({usuario.rol}) — {usuario.email}")
    print(f"Contraseña temporal: {temporal}")
    print("Entrégala a la persona y pídele que la cambie en su panel (🔑 Cambiar contraseña).")


if __name__ == "__main__":
    main()
