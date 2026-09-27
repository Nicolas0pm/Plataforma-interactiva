import { apiFetch } from "../api.js";
import { montarRegistrar, montarVincular } from "../estudiantes-ui.js";
import { inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { exigirRol, salir } from "../session.js";

const sesion = exigirRol("padre", "admin");
inicializarLangToggle();

document.getElementById("btn-logout").addEventListener("click", salir);

if (sesion) {
  cargar(sesion);
  montarVincular({ onVinculado: () => cargar(sesion) });
  montarRegistrar({ onCreado: () => cargar(sesion) });
}

async function cargar(sesion) {
  const hijos = await apiFetch(`/api/usuarios/padre/${sesion.id_usuario}/hijos`);
  document.getElementById("sin-hijos").classList.toggle("oculto", hijos.length > 0);

  const contenedor = document.getElementById("hijos");
  contenedor.innerHTML = "";

  for (const hijo of hijos) {
    const [progreso, recompensas, feedback] = await Promise.all([
      apiFetch(`/api/usuarios/${hijo.id_usuario}/progreso`).catch(() => ({
        puntaje_total: 0, nivel_logrado: 1, actividades_completadas: 0,
      })),
      apiFetch(`/api/recompensas/estudiante/${hijo.id_usuario}`).catch(() => []),
      apiFetch(`/api/feedback/estudiante/${hijo.id_usuario}`).catch(() => []),
    ]);

    const tarjeta = document.createElement("div");
    tarjeta.className = "card";
    tarjeta.innerHTML = `
      <div class="child-banner">
        <strong>🧒 ${hijo.nombre}</strong> — ${t("dash.level")} ${progreso.nivel_logrado}
        ${hijo.codigo_acceso ? `<div>🪪 ${t("teacher.code")}: <strong>${hijo.codigo_acceso}</strong></div>` : ""}
      </div>
      <div class="stat-row">
        <div class="stat-tile azul">
          <span class="valor">${progreso.puntaje_total}</span>
          <span class="etiqueta">${t("dash.points")}</span>
        </div>
        <div class="stat-tile amarillo">
          <span class="valor">${progreso.actividades_completadas}</span>
          <span class="etiqueta">🔥 ${t("dash.streak")}</span>
        </div>
        <div class="stat-tile morado">
          <span class="valor">${recompensas.length}</span>
          <span class="etiqueta">${t("parent.rewards")}</span>
        </div>
      </div>
      <h3>${t("parent.feedback")}</h3>
      ${
        feedback.length
          ? feedback.map((f) => `<div class="feedback-item">${f.comentario}</div>`).join("")
          : `<p class="hint">—</p>`
      }
    `;
    contenedor.appendChild(tarjeta);
  }
}
