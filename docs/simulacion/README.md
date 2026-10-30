# Simulación de un salón (datos sintéticos)

> **Todo lo de esta carpeta es una simulación.** Los estudiantes, la docente y los acudientes son
> ficticios, y sus respuestas las generó un programa. No es la prueba piloto con niños reales y
> no mide la motivación ni el aprendizaje de niños de verdad. Sirve como validación funcional de
> la plataforma con un salón completo durante varias semanas.

## Cómo se hizo

- **Programa:** `backend/scripts/simulacion/simular_salon.py` (con `mundos_profe.py`); los
  resultados los calcula `analizar.py`. Usa la API real de la plataforma (la misma lógica que en
  producción) sobre una base de datos SQLite aparte, nunca la de producción. Un reloj controlado
  (freezegun) da a cada acción su fecha simulada.
- **Periodo simulado:** del lunes 24 de agosto al jueves 22 de octubre de 2026 (9 semanas, la
  última incompleta).
- **Salón:** una docente (Laura Méndez), 12 estudiantes de 6 a 8 años y 8 acudientes, todos
  ficticios. Clase de inglés martes y jueves de 9:00 a 10:00, con la máquina de premios del
  salón; en casa, cada niño juega según su perfil.
- **Mundos del profe (16):** siguen el [plan de estudio](plan_de_estudio.md) de 8 semanas basado
  en el Currículo Sugerido de Inglés para 1.° y 2.° (MEN, 2016). Cada lunes la docente publica 2
  mundos con 2 o 3 temas, una estructura sencilla y 24 preguntas cada uno (384 en total).
- **La docente:** registra la máquina, elige «examen cada 4 mundos», cambia el enunciado de una
  pregunta del temario y oculta otra, y cada viernes revisa su panel y deja comentarios a quien
  necesita ayuda (hasta 3 por semana).
- **Perfiles de los estudiantes (supuestos de la simulación):** sobresaliente, constante, rápida
  pero descuidada, con dificultades, juega de noche, irregular, deja de practicar en casa, solo
  en clase, fines de semana, olvida el PIN, promedio, y con dificultades que mejora. Cada perfil
  fija la probabilidad de acertar al inicio, cuánto mejora hasta el final, las sesiones en casa
  por semana, el horario y las lecciones por sesión. La semilla es fija: la simulación se puede
  repetir y da los mismos resultados.

## Resultados principales (simulación)

| Indicador (simulación) | Valor |
|---|---|
| Lecciones jugadas / aprobadas | 1.169 / 966 |
| Lecciones nuevas / repasos | 911 / 258 |
| Aciertos en general | 75,8 % |
| Aciertos en las semanas 1–2 / en las 2 últimas | 69,1 % / 82,4 % |
| Lecciones jugadas en casa | 56,4 % |
| Mundos completados | 199 |
| Exámenes creados / aprobados | 36 / 36 |
| Exámenes aprobados al primer intento | 35 de 36 |
| Premios entregados por la máquina | 28 (2 fuera del horario de clase) |
| Veces que un niño se quedó sin vidas | 118 |
| PIN mal escritos / códigos bloqueados | 24 / 0 |
| Comentarios de la docente / consultas de acudientes | 13 / 33 |
| Compras en la tienda | 60 |

Por semana y por estudiante: `datos/por_semana_simulacion.csv` y
`datos/por_estudiante_simulacion.csv`. Gráficos en `graficos/` y capturas de los paneles con
estos datos en `capturas/`.

## Hallazgos de la simulación

- **Todo el flujo funcionó de punta a punta**: lecciones, vidas, repasos, mundos del profe,
  exámenes cada 2 mundos, premios en la cola de la máquina, panel de la docente, comentarios,
  panel de acudientes, tienda, PIN errados y edición del temario por salón.
- **El contenido se acaba pronto para los más activos (simulación):** aun con los 16 mundos del
  plan, una estudiante aprobó 139 de las 143 lecciones disponibles en las 9 semanas. En el otro
  extremo, cuatro estudiantes aprobaron 41 lecciones o menos.
- **Quedarse sin vidas es frecuente en los perfiles impulsivos (simulación):** la estudiante
  «rápida pero descuidada» se quedó sin vidas 51 veces; las vidas cumplen su función de frenar
  el juego al azar.
- **Premios fuera de clase:** de los 28 premios, 26 se entregaron en clase, pero 2 salieron a
  las 21:00, cuando una estudiante aprobó en casa un examen de los mundos del profe: la máquina
  soltó el juguete con el salón vacío. Conviene que la docente confirme la entrega o limitar la
  máquina al horario de clase.
- **Necesitan ayuda (simulación):** el panel marcó a 4 estudiantes en la semana 1 y a ninguno
  en la semana 8.

## Limitaciones

Los perfiles, las probabilidades de acierto y la mejora son supuestos del equipo, no
mediciones. Los resultados describen cómo responde la plataforma a esos comportamientos; no
permiten concluir nada sobre la motivación ni el aprendizaje de niños reales, que corresponde a
la prueba piloto.
