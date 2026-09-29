import { apiFetch } from "../api.js";
import { montarPestanas, montarRegistrar, montarVincular } from "../estudiantes-ui.js";
import { esc, porcentaje } from "../html.js";
import { idiomaActual, inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { exigirRol, salir } from "../session.js";

const sesion = exigirRol("docente", "admin");
inicializarLangToggle();
document.getElementById("btn-logout").addEventListener("click", salir);

montarPestanas();
montarVincular({ onVinculado: () => cargar() });
montarRegistrar({ onCreado: () => cargar() });

// RF06/RF09: los botones de arriba eligen qué se ve abajo. La vista queda en la URL
// (#ayuda, #progreso...) para que al volver o recargar se mantenga.
const VISTAS = ["estudiantes", "ayuda", "progreso", "activos"];
let resumen = null;

const titulo = (u) => u.titulo[idiomaActual()] || u.titulo.es;

document.querySelectorAll("[data-vista]").forEach((boton) => {
  boton.addEventListener("click", () => {
    history.replaceState(null, "", `#${boton.dataset.vista}`);
    pintarVista();
  });
});

if (sesion) cargar();

async function cargar() {
  resumen = await apiFetch(`/api/lecciones/docente/${sesion.id_usuario}`);
  document.getElementById("stat-total").textContent = resumen.total_estudiantes;
  document.getElementById("stat-ayuda").textContent = resumen.necesitan_ayuda;
  document.getElementById("stat-promedio").textContent = `${resumen.progreso_promedio} %`;
  document.getElementById("stat-activos").textContent = resumen.activos_hoy;
  pintarVista();
}

function vistaActual() {
  const hash = window.location.hash.slice(1);
  return VISTAS.includes(hash) ? hash : "estudiantes";
}

function pintarVista() {
  if (!resumen) return;
  const vista = vistaActual();
  document.querySelectorAll("[data-vista]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.vista === vista)));
  document.getElementById("vista-titulo").textContent = t(`teacher.view_${vista}`);
  document.getElementById("vista-ayuda").textContent = t(`teacher.view_${vista}_hint`);
  const contenido = document.getElementById("vista-contenido");
  contenido.innerHTML = "";

  const estudiantes = resumen.estudiantes;
  if (!estudiantes.length) {
    contenido.innerHTML = `<p class="vacio">🧒 ${t("teacher.no_students")}</p>`;
    return;
  }
  if (vista === "progreso") return pintarProgreso(contenido);

  const lista =
    vista === "ayuda" ? estudiantes.filter((e) => e.necesita_ayuda)
    : vista === "activos" ? estudiantes.filter((e) => e.activo_hoy)
    : estudiantes;
  if (!lista.length) {
    contenido.innerHTML = `<p class="vacio">${vista === "ayuda" ? "🎉 " + t("teacher.nobody_needs_help") : "😴 " + t("teacher.nobody_active")}</p>`;
    return;
  }
  const ul = document.createElement("ul");
  ul.className = "lista-estudiantes";
  lista.forEach((e) => ul.appendChild(filaEstudiante(e, vista === "ayuda")));
  contenido.appendChild(ul);
}

function filaEstudiante(e, mostrarMotivos) {
  const li = document.createElement("li");
  li.className = "student-row";
  const avance = Math.round((e.lecciones_aprobadas / e.total_lecciones) * 100);
  const siguiente = e.siguiente ? `${e.siguiente.info.emoji} ${esc(titulo(e.siguiente.info))} · ${t("path.lesson")} ${e.siguiente.leccion}` : "🏆";
  li.innerHTML = `
    <span class="emoji">🧒</span>
    <div class="info">
      <strong>${esc(e.nombre)}</strong>
      ${e.codigo_acceso ? `<span class="pill pill-codigo">🪪 ${esc(e.codigo_acceso)}</span>` : ""}
      ${e.necesita_ayuda ? `<span class="pill alerta">${t("teacher.needs_help_badge")}</span>` : ""}
      <div class="hint">${t("path.lessons")}: ${e.lecciones_aprobadas}/${e.total_lecciones} · ${t("path.accuracy")}: ${porcentaje(e.precision)} · ${t("teacher.now_on")}: ${siguiente}</div>
      <div class="progress-bar"><div class="progress-bar-fill" style="width:${avance}%"></div></div>
      ${mostrarMotivos ? `<ul class="motivos">${e.motivos.map((m) => `<li>⚠️ ${esc(m)}</li>`).join("")}</ul>` : ""}
    </div>
    <div class="acciones">
      <button type="button" class="secundario" aria-expanded="false">${t("teacher.view_progress")}</button>
    </div>
    <div class="detalle oculto"></div>
  `;
  const boton = li.querySelector("button");
  const detalle = li.querySelector(".detalle");
  boton.addEventListener("click", async () => {
    const abrir = detalle.classList.contains("oculto");
    detalle.classList.toggle("oculto", !abrir);
    boton.setAttribute("aria-expanded", String(abrir));
    if (abrir && !detalle.dataset.cargado) await cargarDetalle(e, detalle);
  });
  return li;
}

// Detalle de un estudiante: en qué va bien y en qué va mal, sus últimos intentos,
// los errores que más repite y los comentarios del docente.
async function cargarDetalle(e, detalle) {
  detalle.innerHTML = `<p class="hint">${t("activity.loading")}</p>`;
  const [aprendizaje, feedback] = await Promise.all([
    apiFetch(`/api/lecciones/resumen/${e.id_usuario}`),
    apiFetch(`/api/feedback/estudiante/${e.id_usuario}`),
  ]);
  detalle.dataset.cargado = "1";

  const temas = aprendizaje.unidades
    .filter((u) => u.precision !== null)
    .map((u) => `<li class="${u.precision < 0.6 ? "mal" : u.precision >= 0.85 ? "bien" : ""}">
        ${esc(u.emoji)} ${esc(titulo(u))} <span>${porcentaje(u.precision)} · ${u.aprobadas}/${u.lecciones.length}</span></li>`)
    .join("");
  const errores = aprendizaje.errores_frecuentes
    .map((err) => `<li>${err.icono ? esc(err.icono) + " " : ""}${esc(err.pregunta)} → ${t("teacher.answered")} <strong>${esc(err.respuesta_dada)}</strong>,
        ${t("teacher.correct_was")} <strong>${esc(err.respuesta_correcta)}</strong> <span class="hint">(${err.veces}×)</span></li>`)
    .join("");
  const intentos = aprendizaje.recientes
    .map((r) => `<li>${r.aprobada ? "✅" : "💔"} ${esc(titulo(r))} · ${t("path.lesson")} ${r.leccion}
        <span class="hint">${r.aprobada ? `${r.aciertos}/${r.total}` : `${r.errores} ${t("path.errors")}`}${r.modo === "practica" ? " · " + t("path.practice") : ""}</span></li>`)
    .join("");

  detalle.innerHTML = `
    <div class="detalle-grid">
      <section><h3>📊 ${t("teacher.by_topic")}</h3><ul class="temas">${temas || `<li class="hint">—</li>`}</ul></section>
      <section><h3>❌ ${t("teacher.frequent_errors")}</h3><ul class="errores">${errores || `<li class="hint">${t("teacher.no_errors")}</li>`}</ul></section>
      <section><h3>🕑 ${t("teacher.recent")}</h3><ul class="lista-intentos">${intentos || `<li class="hint">${t("path.no_attempts")}</li>`}</ul></section>
      <section>
        <h3>💬 ${t("teacher.leave_feedback")}</h3>
        <div class="comentarios">${feedback.map((f) => `<div class="feedback-item">${esc(f.comentario)}</div>`).join("") || `<p class="hint">—</p>`}</div>
        <form class="form-feedback">
          <textarea required aria-label="${t("teacher.leave_feedback")}"></textarea>
          <button type="submit" class="secundario">${t("teacher.leave_feedback")}</button>
        </form>
      </section>
    </div>
  `;
  detalle.querySelector(".form-feedback").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const textarea = ev.target.querySelector("textarea");
    await apiFetch("/api/feedback", {
      method: "POST",
      body: { id_estudiante: e.id_usuario, comentario: textarea.value, tipo: "progreso", visible_para_padres: true },
    });
    delete detalle.dataset.cargado;
    await cargarDetalle(e, detalle);
  });
}

// Vista de progreso: temas más difíciles del grupo + avance de cada estudiante.
function pintarProgreso(contenido) {
  const temas = resumen.temas
    .map((tema) => `<li class="${tema.precision < 0.6 ? "mal" : tema.precision >= 0.85 ? "bien" : ""}">
        ${esc(tema.emoji)} ${esc(titulo(tema))} <span>${porcentaje(tema.precision)}</span></li>`)
    .join("");
  const filas = resumen.estudiantes
    .map((e) => {
      const avance = Math.round((e.lecciones_aprobadas / e.total_lecciones) * 100);
      return `<tr>
        <td><strong>${esc(e.nombre)}</strong></td>
        <td><div class="progress-bar"><div class="progress-bar-fill" style="width:${avance}%"></div></div>
            <span class="hint">${e.lecciones_aprobadas}/${e.total_lecciones}</span></td>
        <td>${porcentaje(e.precision)}</td>
        <td>${e.nivel_logrado}</td>
      </tr>`;
    })
    .join("");
  contenido.innerHTML = `
    <h3>🧩 ${t("teacher.hard_topics")}</h3>
    <ul class="temas">${temas || `<li class="hint">${t("teacher.no_data_yet")}</li>`}</ul>
    <div class="tabla-scroll">
      <table class="tabla-progreso">
        <thead><tr><th>${t("login.name")}</th><th>${t("path.lessons")}</th><th>${t("path.accuracy")}</th><th>${t("dash.level")}</th></tr></thead>
        <tbody>${filas}</tbody>
      </table>
    </div>
  `;
}
