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
| Sofía Martínez | 46BBNP | 4826 | acudiente01 |
| Mateo Rojas | 5J53WG | 5830 | acudiente02 |
| Valentina Cruz | 8PSBWK | 7149 | acudiente03 |
| Samuel Torres | 792JC2 | 3958 | acudiente04 |
| Isabella Gómez | XWAGKW | 6207 | acudiente05 |
| Santiago Díaz | KQ3Q6B | 8415 | acudiente06 |
| Mariana López | TJWP57 | 2693 | acudiente07 |
| Emiliano Ruiz | A8DE96 | 9071 | — |
| Luciana Herrera | Y4CVMU | 1538 | acudiente09 |
| Tomás Castro | F8GPTQ | 4762 | — |
| Gabriela Vargas | JH9JGN | 3184 | — |
| Daniel Moreno | TVNDJ9 | 6529 | — |

Máquina de premios simulada: `aula-2b`, secreto `secreto-simulacion`.

## Modo de prueba (`api-fake`, base en memoria)

Cada vez que arranca está vacía, salvo `coordinador` / `coordinador123`. Las cuentas de las
capturas de los manuales (`mgarcia`, `cperez`, …) las crean los scripts de capturas con la
contraseña `clave-segura-1` y desaparecen al apagar el servidor.
