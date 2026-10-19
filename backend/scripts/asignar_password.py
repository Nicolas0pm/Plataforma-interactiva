"""
Crea el primer coordinador, o le pone una contraseña temporal a una cuenta de adulto
desde la terminal. Lo normal es hacerlo desde el panel del coordinador; esto es para
cuando todavía no hay ningún coordinador o el único olvidó su contraseña.

Uso (desde backend/, con DATABASE_URL en .env):
    python scripts/asignar_password.py mgarcia                       # contraseña temporal
    python scripts/asignar_password.py coordinacion --crear-admin "Nombre del coordinador"
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SesionLocal, ahora, crear_tablas  # noqa: E402
from app.models.tablas import Usuario  # noqa: E402
from app.services.auth_service import hash_password, password_temporal, registrar_auditoria  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cuenta", help="Usuario (o correo) de la cuenta")
    parser.add_argument("--crear-admin", metavar="NOMBRE", help="Crea un coordinador con ese usuario")
    args = parser.parse_args()

    if get_settings().use_fake_db:
        raise SystemExit("USE_FAKE_DB=true: este script es para la base de datos real (DATABASE_URL).")
    crear_tablas()
    cuenta = args.cuenta.strip().lower()
    temporal = password_temporal()
    with SesionLocal.begin() as db:
        if args.crear_admin:
            if "@" in cuenta or db.scalar(select(Usuario).where(Usuario.usuario == cuenta)):
                raise SystemExit(f"«{cuenta}» no sirve como usuario o ya existe.")
            usuario = Usuario(nombre=args.crear_admin, edad=0, rol="admin", usuario=cuenta, activo=True, creado_en=ahora())
            db.add(usuario)
            db.flush()
        else:
            columna = Usuario.email if "@" in cuenta else Usuario.usuario
            usuario = db.scalar(select(Usuario).where(columna == cuenta))
            if usuario is None or usuario.rol == "estudiante":
                raise SystemExit("No hay ninguna cuenta de adulto con ese usuario o correo.")
        usuario.password_hash = hash_password(temporal)
        usuario.debe_cambiar_password = True
        registrar_auditoria(db, tipo="password_asignada", actor=None, detalle={"id_usuario": usuario.id_usuario})

    print(f"Cuenta: {usuario.nombre} ({'coordinador' if usuario.rol == 'admin' else usuario.rol})")
    print(f"Usuario: {usuario.usuario}")
    print(f"Contraseña temporal: {temporal}")
    print("Al entrar por primera vez le pedirá cambiarla y aceptar los términos.")


if __name__ == "__main__":
    main()
