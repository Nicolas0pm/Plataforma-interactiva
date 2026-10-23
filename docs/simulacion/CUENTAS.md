# Cuentas de prueba y de la simulación

> Estas cuentas existen **solo** en las bases de prueba locales (modo de prueba y simulación).
> No sirven en la plataforma publicada en Render, cuyas cuentas reales crea el coordinador y
> cuyas contraseñas solo conoce cada persona.

## Cómo abrir la simulación

En la app, iniciar los servidores `api-simulacion` y `frontend` (`.claude/launch.json`), o desde
la carpeta `backend`:

```bash
cp ../docs/simulacion/datos/simulacion.db /tmp/simulacion-demo.db
USE_FAKE_DB=true DATABASE_URL=sqlite:////tmp/simulacion-demo.db .venv/bin/uvicorn app.main:app --port 8000
```

y la aplicación web con `python3 frontend/dev-server.py 5500` → http://localhost:5500.
Se trabaja sobre una copia, así que la base original de la simulación no cambia.

## Simulación (datos sintéticos)

| Rol | Usuario | Contraseña |
|---|---|---|
| Coordinador | `coordinador` | `coordinador123` |
| Docente (Laura Méndez) | `lmendez` | `clave-simulacion-1` |
| Acudientes (8) | `acudiente01` … `acudiente07` y `acudiente09` (ver tabla de abajo) | `clave-simulacion-1` |

| Estudiante | Código | PIN | Acudiente |
|---|---|---|---|
| Sofía Martínez | U3Z6N8 | 4826 | acudiente01 |
| Mateo Rojas | UPSUFV | 5830 | acudiente02 |
| Valentina Cruz | GJM23X | 7149 | acudiente03 |
| Samuel Torres | 2PVJQJ | 3958 | acudiente04 |
| Isabella Gómez | TZVFKQ | 6207 | acudiente05 |
| Santiago Díaz | Y5M8PS | 8415 | acudiente06 |
| Mariana López | GQ794M | 2693 | acudiente07 |
| Emiliano Ruiz | S42QJZ | 9071 | — |
| Luciana Herrera | SPYQWC | 1538 | acudiente09 |
| Tomás Castro | X9BZ3C | 4762 | — |
| Gabriela Vargas | C3TUJR | 3184 | — |
| Daniel Moreno | 39JN6P | 6529 | — |

Máquina de premios simulada: `aula-2b`, secreto `secreto-simulacion`.

## Modo de prueba (`api-fake`, base en memoria)

Cada vez que arranca está vacía, salvo `coordinador` / `coordinador123`. Las cuentas de las
capturas de los manuales (`mgarcia`, `cperez`, …) las crean los scripts de capturas con la
contraseña `clave-segura-1` y desaparecen al apagar el servidor.
