import { apiFetch } from "../api.js";
import { emojiHtml } from "../emoji.js";
import { esc, miniMarkdown } from "../html.js";
import { idiomaActual, inicializarLangToggle, t } from "../i18n.js";
import { volver } from "../nav.js";
import { exigirRol } from "../session.js";
import { alternarSonido, sonar, sonidoActivo } from "../sonidos.js";
import { corazones, minutosHasta } from "../vidas.js";

// Lección estilo Duolingo (sin audios):
// - La lección la elige el servidor (sin parámetros). Con ?unidad=&leccion= solo se puede
//   repetir una lección ya aprobada (práctica).
// - Un intento por pregunta: si se equivoca se muestra el error y la respuesta correcta, y
//   pierde una vida ❤️. Las vidas se guardan entre lecciones y se recarga una cada 30 min;
//   sin vidas, la lección termina. Practicar (repetir una aprobada) no gasta vidas.
// - Al final se envían las respuestas y el servidor califica.
// - Con ?examen=<id> es el examen de varios mundos: no gasta vidas ni muestra si cada
//   respuesta estaba bien (la respuesta correcta no llega al navegador); al final el
//   servidor califica y, si aprueba el examen de los mundos del profe, llega el premio.

const sesion = exigirRol("estudiante");
inicializarLangToggle();

// Botón 🔊/🔇 para silenciar los sonidos (queda guardado).
const botonSonido = document.getElementById("btn-sonido");
function pintarBotonSonido() {
  const activo = sonidoActivo();
  botonSonido.textContent = activo ? "🔊" : "🔇";
  botonSonido.setAttribute("aria-pressed", String(activo));
  botonSonido.setAttribute("aria-label", t(activo ? "activity.sound_off" : "activity.sound_on"));
  botonSonido.title = botonSonido.getAttribute("aria-label");
}
pintarBotonSonido();
botonSonido.addEventListener("click", () => {
  if (alternarSonido()) sonar("acierto"); // para que escuche que volvió el sonido
  pintarBotonSonido();
});

const params = new URLSearchParams(window.location.search);
const SECCIONES = ["vocabulario", "gramatica", "profesor"];
const tarjeta = document.getElementById("tarjeta-actividad");
const aviso = document.getElementById("aviso");
const overlay = document.getElementById("overlay");
const confetiEl = document.getElementById("confeti");

let leccion = null;
const idExamen = params.get("examen");
let indice = 0;
let vidas = 0;
let inicioPregunta = 0;
const respuestas = [];

if (sesion) cargar();

async function cargarExamen() {
  try {
    leccion = await apiFetch(`/api/examenes/${encodeURIComponent(idExamen)}`);
  } catch (err) {
    tarjeta.innerHTML = `<span class="hero-emoji">⚠️</span><p>${esc(err.message)}</p>
      <button type="button" id="btn-al-mapa">${t("activity.back_dashboard")}</button>`;
    document.getElementById("btn-al-mapa").addEventListener("click", irAlMapa);
    return;
  }
  document.getElementById("vidas").classList.add("oculto");
  const mundos = leccion.mundos.map((m) => `${m.emoji} ${m.titulo[idiomaActual()] || m.titulo.es}`).join(", ");
  document.getElementById("leccion-nombre").textContent = `📝 ${t("exam.title")}: ${mundos}`;
  mostrarPregunta();
}

async function cargar() {
  if (idExamen) return cargarExamen();
  const consulta = params.get("unidad")
    ? `?unidad=${encodeURIComponent(params.get("unidad"))}&leccion=${encodeURIComponent(params.get("leccion"))}`
    : `?seccion=${SECCIONES.includes(params.get("seccion")) ? params.get("seccion") : "vocabulario"}`;
  try {
    leccion = await apiFetch(`/api/lecciones/jugar${consulta}`);
  } catch (err) {
    // P. ej. "Te quedaste sin vidas…": se explica y se ofrece volver al mapa.
    tarjeta.innerHTML = `<span class="hero-emoji">${err.message.includes("❤️") ? "💔" : "⚠️"}</span>
      <p>${esc(err.message)}</p>
      <button type="button" id="btn-al-mapa">${t("activity.back_dashboard")}</button>`;
    document.getElementById("btn-al-mapa").addEventListener("click", irAlMapa);
    return;
  }
  vidas = leccion.vidas;
  const titulo = leccion.unidad.titulo[idiomaActual()] || leccion.unidad.titulo.es;
  const modo = { nueva: "", repaso: ` · 🔁 ${t("path.review")}`, practica: ` · ${t("path.practice")}` }[leccion.modo];
  document.getElementById("leccion-nombre").textContent =
    `${leccion.unidad.emoji} ${titulo} · ${t("path.lesson")} ${leccion.leccion}${modo}`;
  pintarVidas();

  if (leccion.unidad.explicacion) mostrarExplicacion(titulo);
  else mostrarPregunta();
}

// Gramática: antes de los ejercicios, la tarjeta "Cómo se usa".
function mostrarExplicacion(titulo) {
  const lineas = leccion.unidad.explicacion[idiomaActual()] || leccion.unidad.explicacion.es;
  tarjeta.innerHTML = `
    <div class="explicacion">
      <span class="hero-emoji">${emojiHtml(leccion.unidad.emoji)}</span>
      <h2>📖 ${t("activity.how_to_use")}: ${esc(titulo)}</h2>
      <ul>${lineas.map((l) => `<li>${miniMarkdown(l)}</li>`).join("")}</ul>
      <button type="button" id="btn-entendido">${t("activity.got_it")}</button>
    </div>`;
  document.getElementById("btn-entendido").addEventListener("click", mostrarPregunta);
}

function pintarVidas() {
  document.getElementById("vidas").textContent = corazones(vidas, leccion.vidas_max);
  document.getElementById("vidas").setAttribute("aria-label", `${vidas} ${t("activity.lives")}`);
}

function barajar(lista) {
  const copia = [...lista];
  for (let i = copia.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copia[i], copia[j]] = [copia[j], copia[i]];
  }
  return copia;
}

function mostrarPregunta() {
  const pregunta = leccion.preguntas[indice];
  inicioPregunta = Date.now();
  aviso.classList.add("oculto");
  document.getElementById("barra-actividad").style.width = `${Math.round((indice / leccion.preguntas.length) * 100)}%`;

  tarjeta.innerHTML = `
    ${pregunta.imagen ? `<img class="quiz-foto" src="${esc(pregunta.imagen)}" alt="" />` : ""}
    ${pregunta.icono ? `<div class="quiz-imagen">${emojiHtml(pregunta.icono)}</div>` : ""}
    <h2 class="quiz-pregunta">${esc(pregunta.pregunta)}</h2>
    <div class="quiz-opciones ${pregunta.formato_opciones === "emoji" ? "emoji" : ""} ${pregunta.opciones.length % 2 ? "una-columna" : ""}" id="opciones"></div>
  `;
  const contenedor = document.getElementById("opciones");
  for (const opcion of barajar(pregunta.opciones)) {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.dataset.opcion = opcion;
    // Las opciones "emoji" (¿cuál es "dog"?) se muestran con su ilustración.
    if (pregunta.formato_opciones === "emoji") boton.innerHTML = emojiHtml(opcion);
    else boton.textContent = opcion;
    boton.addEventListener("click", () => responder(boton, opcion, pregunta));
    contenedor.appendChild(boton);
  }
}

function responder(boton, opcion, pregunta) {
  const botones = [...document.querySelectorAll("#opciones button")];
  botones.forEach((b) => (b.disabled = true));
  respuestas.push({ id_actividad: pregunta.id_actividad, respuesta: opcion, tiempo_ms: Date.now() - inicioPregunta });

  if (idExamen) {
    // En el examen no se dice si estaba bien: se marca la elegida y se sigue.
    boton.classList.add("elegida");
    sonar("acierto");
    setTimeout(avanzar, 500);
    return;
  }

  const correcta = opcion === pregunta.respuesta_correcta;
  if (correcta) {
    sonar("acierto");
    boton.classList.add("correcta");
    mostrarAviso(true, `✅ ${t("activity.correct")}`);
    setTimeout(avanzar, 1100);
    return;
  }

  // Error: se marca, se muestra la respuesta correcta y se pierde una vida.
  boton.classList.add("incorrecta");
  botones.find((b) => b.dataset.opcion === pregunta.respuesta_correcta)?.classList.add("correcta");
  vidas -= 1;
  sonar("error");
  pintarVidas();
  mostrarAviso(false, `❌ ${t("activity.wrong")} ${t("activity.right_answer")}: <strong>${
    pregunta.formato_opciones === "emoji" ? emojiHtml(pregunta.respuesta_correcta) : esc(pregunta.respuesta_correcta)
  }</strong>`);
  document.getElementById("btn-aviso").onclick = avanzar;
}

function mostrarAviso(bien, html) {
  aviso.className = `aviso-respuesta ${bien ? "bien" : "mal"}`;
  document.getElementById("aviso-texto").innerHTML = html;
  document.getElementById("btn-aviso").classList.toggle("oculto", bien);
  if (!bien) document.getElementById("btn-aviso").focus();
}

function avanzar() {
  if ((!idExamen && vidas <= 0) || indice === leccion.preguntas.length - 1) {
    terminar();
    return;
  }
  indice += 1;
  mostrarPregunta();
}

async function terminarExamen() {
  document.getElementById("barra-actividad").style.width = "100%";
  let r;
  try {
    r = await apiFetch(`/api/examenes/${encodeURIComponent(idExamen)}/resultado`, { method: "POST", body: { respuestas } });
  } catch (err) {
    mostrarModal({ emoji: "⚠️", titulo: err.message, extra: [], principal: [t("activity.back_dashboard"), irAlMapa] });
    return;
  }
  const extra = [t("activity.lesson_summary").replace("{aciertos}", r.aciertos).replace("{total}", r.total)];
  if (r.aprobado) {
    if (r.recompensa?.device_id) extra.unshift(t("exam.prize_machine"));
    else if (r.recompensa) extra.unshift(t("exam.prize_no_machine"));
    else if (!r.primera_vez) extra.push(t("exam.already_passed"));
    mostrarModal({ emoji: r.recompensa?.device_id ? "🏅🎁" : "🏅", titulo: t("exam.passed"), extra,
                   principal: [t("activity.continue"), irAlMapa] });
    sonar("ganar");
    lanzarConfeti();
  } else {
    extra.push(t("exam.need").replace("{n}", r.necesarios).replace("{total}", r.total));
    sonar("perder");
    mostrarModal({ emoji: "💪", titulo: t("exam.failed"), extra,
                   principal: [t("activity.try_again"), () => window.location.reload()],
                   secundario: [t("activity.back_dashboard"), irAlMapa] });
  }
}

async function terminar() {
  aviso.classList.add("oculto");
  if (idExamen) return terminarExamen();
  document.getElementById("barra-actividad").style.width = vidas > 0 ? "100%" : document.getElementById("barra-actividad").style.width;
  let resultado;
  try {
    resultado = await apiFetch("/api/lecciones/resultado", {
      method: "POST",
      body: { unidad: leccion.unidad.id, leccion: leccion.leccion, respuestas },
    });
  } catch (err) {
    mostrarModal({ emoji: "⚠️", titulo: err.message, extra: [], principal: [t("activity.back_dashboard"), irAlMapa] });
    return;
  }

  if (resultado.aprobada) {
    const extra = [t("activity.lesson_summary").replace("{aciertos}", resultado.aciertos).replace("{total}", resultado.total)];
    extra.push(
      resultado.modo === "practica"
        ? t("activity.practice_no_points")
        : `+${resultado.puntos_ganados} ⭐ ${t("activity.points_for_shop")}`
    );
    if (resultado.subio_de_nivel) extra.push(t("activity.level_up"));
    extra.push(`${corazones(resultado.vidas.actuales, resultado.vidas.maximo)}${
      resultado.vida_recuperada ? ` · ${t("activity.practice_life")}` : ""
    }`);

    const mundo = resultado.mundo_completado;
    if (mundo) {
      // ¡Completó todo un mundo! Cada N mundos del apartado le sale un examen de esos
      // mundos; si es de los mundos del profe, aprobarlo le da el premio de la máquina.
      const nombreMundo = mundo.titulo[idiomaActual()] || mundo.titulo.es;
      extra.unshift(t("activity.world_done").replace("{mundo}", nombreMundo));
      if (mundo.examen) {
        extra.splice(1, 0, t(mundo.examen.da_premio ? "exam.ready_prize" : "exam.ready"));
        mostrarModal({ emoji: `${mundo.emoji}📝`, titulo: t("activity.world_title"), extra,
                       principal: [t("exam.take"), () => (window.location.href = `activity.html?examen=${mundo.examen.id_examen}`)],
                       secundario: [t("exam.later"), irAlMapa] });
      } else {
        if (mundo.faltan_mundos) {
          extra.splice(1, 0, t(mundo.faltan_mundos === 1 ? "exam.one_more" : "exam.more").replace("{n}", mundo.faltan_mundos));
        }
        mostrarModal({ emoji: `${mundo.emoji}🎉`, titulo: t("activity.world_title"), extra, principal: [t("activity.continue"), irAlMapa] });
      }
    } else {
      mostrarModal({ emoji: "🏆", titulo: t("activity.lesson_passed"), extra, principal: [t("activity.continue"), irAlMapa] });
    }
    sonar("ganar");
    lanzarConfeti();
  } else {
    sonar("perder");
    const v = resultado.vidas;
    if (resultado.modo !== "practica" && v.actuales === 0) {
      // Sin vidas: toca esperar la recarga (o practicar una lección ya aprobada).
      mostrarModal({
        emoji: "💔",
        titulo: t("activity.out_of_lives"),
        extra: [
          t("activity.lives_wait").replace("{min}", v.minutos_por_vida).replace("{proxima}", minutosHasta(v.proxima_vida)),
          t("activity.lives_practice"),
        ],
        principal: [t("activity.back_dashboard"), irAlMapa],
      });
    } else {
      mostrarModal({
        emoji: "💔",
        titulo: t("activity.out_of_lives"),
        extra: [t("activity.try_again_hint")],
        principal: [t("activity.try_again"), () => window.location.reload()],
        secundario: [t("activity.back_dashboard"), irAlMapa],
      });
    }
  }
}

function irAlMapa() {
  volver("kid-dashboard.html");
}

function mostrarModal({ emoji, titulo, extra, principal, secundario }) {
  document.getElementById("modal-emoji").textContent = emoji;
  document.getElementById("modal-titulo").textContent = titulo;
  document.getElementById("modal-extra").innerHTML = extra.map((e) => `<span>${esc(e)}</span>`).join("<br />");
  const boton = document.getElementById("btn-continuar");
  boton.textContent = principal[0];
  boton.onclick = principal[1];
  const botonSecundario = document.getElementById("btn-secundario");
  botonSecundario.classList.toggle("oculto", !secundario);
  if (secundario) {
    botonSecundario.textContent = secundario[0];
    botonSecundario.onclick = secundario[1];
  }
  overlay.hidden = false;
  boton.focus();
}

function lanzarConfeti() {
  confetiEl.hidden = false;
  confetiEl.innerHTML = "";
  const emojis = ["⭐", "🎉", "🟡", "💚", "✨"];
  for (let i = 0; i < 24; i++) {
    const span = document.createElement("span");
    span.textContent = emojis[i % emojis.length];
    span.style.left = `${Math.random() * 100}%`;
    span.style.animationDuration = `${1.2 + Math.random()}s`;
    span.style.animationDelay = `${Math.random() * 0.4}s`;
    confetiEl.appendChild(span);
  }
  setTimeout(() => {
    confetiEl.hidden = true;
  }, 2200);
}
