import { apiFetch } from "../api.js";
import { inicializarLangToggle, t } from "../i18n.js";
import { volver } from "../nav.js";
import { exigirRol } from "../session.js";

const sesion = exigirRol("estudiante");
inicializarLangToggle();

const params = new URLSearchParams(window.location.search);
const nivel = Number(params.get("nivel") || 1);

const tarjeta = document.getElementById("tarjeta-actividad");
const overlay = document.getElementById("overlay");
const confetiEl = document.getElementById("confeti");

let actividades = [];
let indice = 0;
let intentos = 1;
let inicioPregunta = 0;

// Resumen de la sesión: se celebra una sola vez, al terminar todas las preguntas.
const resumen = { aLaPrimera: 0, puntos: 0, subioDeNivel: false, recompensa: null };

if (sesion) cargarActividades();

async function cargarActividades() {
  const todas = await apiFetch(`/api/actividades?nivel=${nivel}`);
  actividades = todas.filter((a) => a.pregunta && a.opciones?.length);
  if (!actividades.length) {
    tarjeta.innerHTML = `<p>${t("activity.empty")}</p>`;
    return;
  }
  mostrarPregunta();
}

function mostrarPregunta() {
  intentos = 1;
  inicioPregunta = Date.now();
  const actividad = actividades[indice];
  document.getElementById("barra-actividad").style.width = `${Math.round((indice / actividades.length) * 100)}%`;

  tarjeta.innerHTML = `
    <div class="quiz-imagen">${actividad.icono || "❓"}</div>
    <h2>${actividad.pregunta}</h2>
    <div class="quiz-opciones" id="opciones"></div>
    <p class="acierto" id="acierto" hidden>✅ ${t("activity.correct")}</p>
  `;

  const contenedor = document.getElementById("opciones");
  for (const opcion of actividad.opciones) {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.textContent = opcion;
    boton.addEventListener("click", () => elegirOpcion(boton, opcion, actividad));
    contenedor.appendChild(boton);
  }
}

async function elegirOpcion(boton, opcion, actividad) {
  if (opcion !== actividad.respuesta_correcta) {
    boton.classList.add("incorrecta");
    intentos += 1;
    setTimeout(() => boton.classList.remove("incorrecta"), 400);
    return;
  }

  boton.classList.add("correcta");
  document.querySelectorAll("#opciones button").forEach((b) => (b.disabled = true));
  // RF08: feedback inmediato y breve por pregunta; la celebración grande queda
  // para el final de la sesión.
  document.getElementById("acierto").hidden = false;

  const tiempoEmpleado = Math.max(1, Math.round((Date.now() - inicioPregunta) / 1000));
  const pausa = new Promise((r) => setTimeout(r, 1200));
  let resultado;
  try {
    resultado = await apiFetch(`/api/actividades/completar/${sesion.id_usuario}`, {
      method: "POST",
      body: {
        id_actividad: actividad.id_actividad,
        tiempo_empleado: tiempoEmpleado,
        intentos,
        puntaje_obtenido: actividad.puntaje_maximo,
      },
    });
  } catch {
    resultado = {};
  }
  await pausa;

  if (intentos === 1) resumen.aLaPrimera += 1;
  resumen.puntos += actividad.puntaje_maximo;
  if (resultado.subio_de_nivel) resumen.subioDeNivel = true;
  if (resultado.recompensa_generada) resumen.recompensa = resultado.recompensa_generada;

  if (indice === actividades.length - 1) {
    document.getElementById("barra-actividad").style.width = "100%";
    mostrarFinDeSesion();
  } else {
    indice += 1;
    mostrarPregunta();
  }
}

function mostrarFinDeSesion() {
  document.getElementById("modal-emoji").textContent = "🏆";
  document.getElementById("modal-titulo").textContent = t("activity.session_done");

  const extras = [
    t("activity.session_summary")
      .replace("{aciertos}", resumen.aLaPrimera)
      .replace("{total}", actividades.length)
      .replace("{puntos}", resumen.puntos),
  ];
  if (resumen.subioDeNivel) extras.push(t("activity.level_up"));
  // Solo se le dice "ve a revisar la máquina" si el estudiante tiene un
  // dispensador (device_id) sincronizado. Si no, el logro se celebra igual
  // (con un mensaje genérico), pero sin prometerle un premio físico que
  // todavía no existe en su salón ni pedirle que hable con el profe por algo
  // que la app no puede resolver.
  if (resumen.recompensa) {
    extras.push(resumen.recompensa.device_id ? t("activity.reward") : t("activity.reward_no_device"));
  }
  document.getElementById("modal-extra").innerHTML = extras.map((e) => `<span>${e}</span>`).join("<br />");

  const botonContinuar = document.getElementById("btn-continuar");
  botonContinuar.textContent = t("activity.back_dashboard");
  botonContinuar.onclick = () => volver("kid-dashboard.html");

  overlay.hidden = false;
  lanzarConfeti();
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
