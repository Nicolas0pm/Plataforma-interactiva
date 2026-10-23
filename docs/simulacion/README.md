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
- **Mundos del profe (4):** saludos y emociones, el salón de clase, la familia, y los días y el
  clima, con 16 preguntas cada uno, basados en los temas del Currículo Sugerido de Inglés para
  1.° y 2.° (MEN, 2016). Se publican en las semanas 1, 1, 3 y 5.
- **La docente:** registra la máquina, elige «examen cada 2 mundos», cambia el enunciado de una
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
| Lecciones jugadas / aprobadas | 1.122 / 907 |
| Lecciones nuevas / repasos | 780 / 342 |
| Aciertos en general | 73,7 % |
| Aciertos en las semanas 1–2 / en las 2 últimas | 68,0 % / 77,7 % |
| Lecciones jugadas en casa | 57,5 % |
| Mundos completados | 154 |
| Exámenes creados / aprobados | 71 / 71 |
| Exámenes aprobados al primer intento | 65 de 71 |
| Premios entregados por la máquina | 24 (todos en horario de clase) |
| Veces que un niño se quedó sin vidas | 116 |
| PIN mal escritos / códigos bloqueados | 25 / 0 |
| Comentarios de la docente / consultas de acudientes | 21 / 35 |
| Compras en la tienda | 68 |

Por semana y por estudiante: `datos/por_semana_simulacion.csv` y
`datos/por_estudiante_simulacion.csv`. Gráficos en `graficos/` y capturas de los paneles con
estos datos en `capturas/`.

## Hallazgos de la simulación

- **Todo el flujo funcionó de punta a punta**: lecciones, vidas, repasos, mundos del profe,
  exámenes cada 2 mundos, premios en la cola de la máquina, panel de la docente, comentarios,
  panel de acudientes, tienda, PIN errados y edición del temario por salón.
- **El contenido se acaba pronto para los más activos (simulación):** una estudiante aprobó las
  103 lecciones (todo el temario y los mundos del profe) y otra terminó todo el vocabulario antes
  de las 9 semanas. Para un uso de varios meses hace falta más contenido o que la docente agregue
  mundos con frecuencia. En el otro extremo, cuatro estudiantes aprobaron 30 lecciones o menos.
- **Quedarse sin vidas es frecuente en los perfiles impulsivos (simulación):** la estudiante
  «rápida pero descuidada» se quedó sin vidas 51 veces; las vidas cumplen su función de frenar
  el juego al azar.
- **Premios fuera de clase:** en esta simulación los 24 premios se entregaron en clase, porque
  los mundos del profe se jugaron allí. Pero la máquina entrega en cuanto aparece un premio: si
  un niño aprobara en casa un examen de los mundos del profe, la máquina soltaría el juguete
  con el salón vacío. Conviene que la docente confirme la entrega o limitar la máquina al
  horario de clase.
- **Necesitan ayuda (simulación):** el panel marcó a 4 estudiantes en la semana 1 y a 1 en la
  semana 8.

## Limitaciones

Los perfiles, las probabilidades de acierto y la mejora son supuestos del equipo, no
mediciones. Los resultados describen cómo responde la plataforma a esos comportamientos; no
permiten concluir nada sobre la motivación ni el aprendizaje de niños reales, que corresponde a
la prueba piloto.
