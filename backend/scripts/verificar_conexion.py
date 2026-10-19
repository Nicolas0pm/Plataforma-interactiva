"""
Verifica que la configuración real funcione (backend/.env): la conexión a PostgreSQL (Neon),
que las tablas estén al día y qué cuentas de adultos todavía no tienen contraseña.
Opcionalmente vuelve a cargar el temario en la tabla `actividades` (después de cambiar
app/curriculo.py).

Uso (desde backend/):
    python scripts/verificar_conexion.py            # solo revisa
    python scripts/verificar_conexion.py --sembrar  # revisa y actualiza el temario
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings  # noqa: E402

OK, FALLA, AVISO = "✅", "❌", "⚠️ "


def _revisar_configuracion(settings) -> bool:
    if settings.use_fake_db:
        print(f"{FALLA} USE_FAKE_DB=true en .env: ponlo en false para usar la base de datos real.")
        return False
    if not settings.database_url.startswith("postgresql"):
        print(f"{FALLA} DATABASE_URL vacío: pega la cadena de conexión de Neon en .env.")
        return False
    if settings.jwt_secret.startswith("dev-") or settings.pin_pepper.startswith("dev-"):
        print(f"{AVISO} JWT_SECRET / PIN_PEPPER siguen con el valor de ejemplo.")
    return True


def _revisar_base_de_datos() -> bool:
    from sqlalchemy import func, select

    from app.db import SesionLocal, crear_tablas
    from app.models.tablas import Actividad, Usuario

    try:
        crear_tablas()
        with SesionLocal() as db:
            usuarios = db.scalar(select(func.count()).select_from(Usuario))
            actividades = db.scalar(select(func.count()).select_from(Actividad))
            sin_password = list(db.scalars(
                select(Usuario).where(Usuario.rol != "estudiante", Usuario.activo, Usuario.password_hash.is_(None))
            ))
    except Exception as exc:  # noqa: BLE001 - queremos mostrar cualquier error al usuario
        print(f"{FALLA} PostgreSQL no responde: {exc}\n   ¿Copiaste bien la cadena de conexión de Neon?")
        return False
    print(f"{OK} PostgreSQL responde y las tablas están al día ({usuarios} usuarios, {actividades} actividades).")
    for usuario in sin_password:
        print(f"{AVISO} {usuario.nombre} ({usuario.email or 'sin correo'}) no tiene contraseña: "
              f"python scripts/asignar_password.py {usuario.email or usuario.id_usuario}")
    return True


def _sembrar_actividades() -> None:
    """Carga el temario (app/curriculo.py): vocabulario + gramática."""
    from app.db import SesionLocal
    from app.services.lecciones_service import sembrar_temario

    with SesionLocal.begin() as db:
        r = sembrar_temario(db)
    print(f"{OK} Temario cargado: {r['creadas_o_actualizadas']} preguntas "
          f"({r['antiguas_desactivadas']} actividades antiguas desactivadas).")


def _asignar_codigos_faltantes() -> None:
    """Estudiantes creados antes de existir `codigo_acceso` no podrían iniciar sesión."""
    from sqlalchemy import select

    from app.db import SesionLocal
    from app.models.tablas import Usuario
    from app.services.estudiantes_service import generar_codigo_acceso

    with SesionLocal.begin() as db:
        sin_codigo = select(Usuario).where(Usuario.rol == "estudiante", Usuario.codigo_acceso.is_(None))
        for estudiante in list(db.scalars(sin_codigo)):
            estudiante.codigo_acceso = generar_codigo_acceso(db)
            db.flush()
            print(f"{OK} Código {estudiante.codigo_acceso} asignado a {estudiante.nombre}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sembrar", action="store_true", help="Vuelve a cargar el temario de app/curriculo.py")
    args = parser.parse_args()

    if not _revisar_configuracion(get_settings()) or not _revisar_base_de_datos():
        raise SystemExit("\nHay pasos pendientes: revisa los ❌ de arriba (docs/despliegue.md).")
    _asignar_codigos_faltantes()
    if args.sembrar:
        _sembrar_actividades()
    print("\nBase de datos configurada correctamente.")


if __name__ == "__main__":
    main()
