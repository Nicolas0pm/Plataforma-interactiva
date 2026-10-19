import { apiFetch } from "../api.js";
import { montarPestanas, montarRegistrar, montarVincular } from "../estudiantes-ui.js";
import { cuando, esc, porcentaje } from "../html.js";
import { idiomaActual, inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { agregarCambioDePassword } from "../cambiar-password.js";
import { exigirRol, salir } from "../session.js";

const sesion = exigirRol("padre", "admin");
inicializarLangToggle();

document.getElementById("btn-logout").addEventListener("click", salir);
agregarCambioDePassword();

if (sesion) {
  cargar(sesion);
  montarPestanas();
  montarVincular({ onVinculado: () => cargar(sesion) });
  montarRegistrar({ onCreado: () => cargar(sesion) });
}

async function cargar(sesion) {
  const hijos = await apiFetch(`/api/usuarios/padre/${sesion.id_usuario}/hijos`);
  document.getElementById("sin-hijos").classList.toggle("oculto", hijos.length > 0);

  const contenedor = document.getElementById("hijos");
  contenedor.innerHTML = "";

  // Todos los hijos a la vez (antes se esperaba a uno para pedir el siguiente).
  const datos = await Promise.all(
    hijos.map((hijo) =>
      Promise.all([
        apiFetch(`/api/lecciones/resumen/${hijo.id_usuario}`).catch(() => null),
        apiFetch(`/api/feedback/estudiante/${hijo.id_usuario}`).catch(() => []),
      ])
    )
  );
  hijos.forEach((hijo, i) => {
    const [aprendizaje, feedback] = datos[i];
    const a = aprendizaje || { nivel_logrado: 1, puntaje_total: 0, lecciones_aprobadas: 0, total_lecciones: 0, precision: null, recientes: [], mundos_completados: 0, perfil: { avatar_emoji: "🧒" } };
    const titulo = (x) => x.titulo[idiomaActual()] || x.titulo.es;

    const tarjeta = document.createElement("div");
    tarjeta.className = "card";
    tarjeta.innerHTML = `
      <div class="child-banner">
        <strong>${esc(a.perfil?.avatar_emoji || "🧒")} ${esc(hijo.nombre)}</strong> — ${t("dash.level")} ${a.nivel_logrado}
        ${hijo.codigo_acceso ? `<div>🪪 ${t("teacher.code")}: <strong>${esc(hijo.codigo_acceso)}</strong></div>` : ""}
        ${["vocabulario", "gramatica", "profesor"].filter((sec) => a.siguiente?.[sec]).map((sec) =>
          `<div>${{ vocabulario: "📚", gramatica: "✏️", profesor: "👩‍🏫" }[sec]} ${t("teacher.now_on")}: ${esc(titulo(a.siguiente[sec].info))} · ${t("path.lesson")} ${a.siguiente[sec].leccion}</div>`).join("")}
        <div>🕑 ${t("teacher.last_active")}: ${a.ultima_actividad ? cuando(a.ultima_actividad, idiomaActual()) : t("teacher.never")}</div>
      </div>
      <div class="stat-row">
        <div class="stat-tile azul">
          <span class="valor">${a.puntaje_total}</span>
          <span class="etiqueta">${t("dash.points")}</span>
        </div>
        <div class="stat-tile verde">
          <span class="valor">${a.lecciones_aprobadas}/${a.total_lecciones}</span>
          <span class="etiqueta">${t("path.lessons")}</span>
        </div>
        <div class="stat-tile naranja">
          <span class="valor">${porcentaje(a.precision)}</span>
          <span class="etiqueta">${t("path.accuracy")}</span>
        </div>
        <div class="stat-tile morado">
          <span class="valor">${a.mundos_completados}</span>
          <span class="etiqueta">🏆 ${t("path.worlds_done")}</span>
        </div>
      </div>
      <h3>🕑 ${t("teacher.recent")}</h3>
      <ul class="lista-intentos">${
        a.recientes.length
          ? a.recientes.slice(0, 5).map((r) => `<li>${r.aprobada ? "✅" : "💔"} ${esc(r.emoji)} ${esc(titulo(r))} · ${t("path.lesson")} ${r.leccion}
              <span class="hint">${r.aprobada ? `${r.aciertos}/${r.total}` : `${r.errores} ${t("path.errors")}`} · ${cuando(r.fecha, idiomaActual())}</span></li>`).join("")
          : `<li class="hint">${t("path.no_attempts")}</li>`
      }</ul>
      <h3>${t("parent.feedback")}</h3>
      ${
        feedback.length
          ? feedback.map((f) => `<div class="feedback-item">${esc(f.comentario)}</div>`).join("")
          : `<p class="hint">—</p>`
      }
    `;
    contenedor.appendChild(tarjeta);
  });
}
