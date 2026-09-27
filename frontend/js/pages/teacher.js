import { apiFetch } from "../api.js";
import { montarRegistrar, montarVincular } from "../estudiantes-ui.js";
import { inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { exigirRol, salir } from "../session.js";

const sesion = exigirRol("docente", "admin");
inicializarLangToggle();

document.getElementById("btn-logout").addEventListener("click", salir);

if (sesion) cargar(sesion);

montarVincular({ onVinculado: () => cargar(sesion) });
montarRegistrar({ onCreado: () => cargar(sesion) });

async function cargar(sesion) {
  const [estudiantes, estadisticas] = await Promise.all([
    apiFetch(`/api/usuarios/docente/${sesion.id_usuario}/estudiantes`),
    apiFetch(`/api/usuarios/docente/${sesion.id_usuario}/estadisticas`),
  ]);

  document.getElementById("stat-total").textContent = estadisticas.total_estudiantes;
  document.getElementById("stat-promedio").textContent = estadisticas.progreso_promedio;
  document.getElementById("stat-activos").textContent = estadisticas.activos_hoy;
  document.getElementById("stat-ayuda").textContent = estadisticas.necesitan_ayuda.length;

  const idsConAyuda = new Set(estadisticas.necesitan_ayuda.map((e) => e.id_usuario));

  const lista = document.getElementById("lista-estudiantes");
  lista.innerHTML = "";

  for (const estudiante of estudiantes) {
    let progreso = { puntaje_total: 0, nivel_logrado: 1 };
    try {
      progreso = await apiFetch(`/api/usuarios/${estudiante.id_usuario}/progreso`);
    } catch {
      /* sin progreso todavía */
    }

    const li = document.createElement("li");
    li.className = "student-row";
    li.innerHTML = `
      <span class="emoji">🧒</span>
      <div class="info">
        <strong>${estudiante.nombre}</strong> — ${t("dash.level")} ${progreso.nivel_logrado}
        ${estudiante.codigo_acceso ? `<span class="pill pill-codigo">🪪 ${estudiante.codigo_acceso}</span>` : ""}
        <div class="progress-bar"><div class="progress-bar-fill" style="width:${Math.min(100, progreso.puntaje_total)}%"></div></div>
      </div>
      ${idsConAyuda.has(estudiante.id_usuario) ? `<span class="pill alerta">${t("teacher.needs_help_badge")}</span>` : ""}
      <div class="acciones">
        <button type="button" class="secundario" data-accion="detalles">${t("teacher.view_progress")}</button>
      </div>
    `;

    const panelDetalle = document.createElement("div");
    panelDetalle.className = "oculto";
    panelDetalle.innerHTML = `
      <div id="feedback-${estudiante.id_usuario}"></div>
      <form data-form-feedback>
        <textarea placeholder="..." required></textarea>
        <button type="submit" class="secundario">${t("teacher.leave_feedback")}</button>
      </form>
    `;

    li.querySelector("[data-accion='detalles']").addEventListener("click", async () => {
      panelDetalle.classList.toggle("oculto");
      if (!panelDetalle.classList.contains("oculto")) {
        await cargarFeedback(estudiante.id_usuario);
      }
    });

    panelDetalle.querySelector("[data-form-feedback]").addEventListener("submit", async (e) => {
      e.preventDefault();
      const textarea = e.target.querySelector("textarea");
      await apiFetch("/api/feedback", {
        method: "POST",
        body: { id_estudiante: estudiante.id_usuario, comentario: textarea.value, tipo: "progreso", visible_para_padres: true },
      });
      textarea.value = "";
      await cargarFeedback(estudiante.id_usuario);
    });

    lista.appendChild(li);
    lista.appendChild(panelDetalle);
  }
}

async function cargarFeedback(idEstudiante) {
  const feedback = await apiFetch(`/api/feedback/estudiante/${idEstudiante}`);
  const contenedor = document.getElementById(`feedback-${idEstudiante}`);
  contenedor.innerHTML = feedback
    .map((f) => `<div class="feedback-item">${f.comentario}</div>`)
    .join("") || `<p class="hint">—</p>`;
}
