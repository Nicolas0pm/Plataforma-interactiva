import { apiFetch } from "../api.js";
import { inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { exigirRol, salir } from "../session.js";

const sesion = exigirRol("estudiante");
if (sesion) iniciar(sesion);

inicializarLangToggle();

document.getElementById("btn-logout").addEventListener("click", salir);

// Debe reflejar app/config.py Settings.nivel_umbrales del backend.
const NIVELES = [
  { nivel: 1, umbral: 0, emoji: "🐾", clave: "dash.world1" },
  { nivel: 2, umbral: 150, emoji: "🎨", clave: "dash.world2" },
  { nivel: 3, umbral: 400, emoji: "🍎", clave: "dash.world3" },
  { nivel: 4, umbral: 700, emoji: "🔢", clave: "dash.world4" },
  { nivel: 5, umbral: 1100, emoji: "🚗", clave: "dash.world5" },
  { nivel: 6, umbral: 1550, emoji: "🖐️", clave: "dash.world6" },
];

async function iniciar(sesion) {
  document.getElementById("titulo-hola").textContent = `${t("dash.hello")} ${sesion.nombre || ""} 👋`;
  if (sesion.codigo_acceso) {
    document.getElementById("mi-codigo-valor").textContent = sesion.codigo_acceso;
    document.getElementById("mi-codigo").classList.remove("oculto");
  }

  let progreso;
  try {
    progreso = await apiFetch(`/api/usuarios/${sesion.id_usuario}/progreso`);
  } catch {
    progreso = { puntaje_total: 0, nivel_logrado: 1, actividades_completadas: 0, puntos_para_siguiente_nivel: 150 };
  }

  document.getElementById("stat-nivel").textContent = progreso.nivel_logrado;
  document.getElementById("stat-puntos").textContent = progreso.puntaje_total;
  document.getElementById("stat-racha").textContent = `🔥${progreso.actividades_completadas}`;

  const siguienteUmbral = NIVELES.find((n) => n.nivel === progreso.nivel_logrado + 1)?.umbral;
  const anteriorUmbral = NIVELES.find((n) => n.nivel === progreso.nivel_logrado)?.umbral ?? 0;
  if (siguienteUmbral !== undefined) {
    const rango = siguienteUmbral - anteriorUmbral;
    const avance = Math.min(100, Math.round(((progreso.puntaje_total - anteriorUmbral) / rango) * 100));
    document.getElementById("barra-nivel").style.width = `${avance}%`;
    document.getElementById("texto-siguiente-nivel").textContent =
      `${progreso.puntos_para_siguiente_nivel} ${t("dash.next_level")}`;
  } else {
    document.getElementById("barra-nivel").style.width = "100%";
    document.getElementById("texto-siguiente-nivel").textContent = t("dash.max_level");
  }

  const contenedor = document.getElementById("mundos");
  contenedor.innerHTML = "";
  for (const mundo of NIVELES) {
    const desbloqueado = mundo.nivel <= progreso.nivel_logrado;
    const div = document.createElement("div");
    div.className = `world-card ${desbloqueado ? "" : "bloqueado"}`.trim();
    div.innerHTML = `
      <span class="emoji">${desbloqueado ? mundo.emoji : "🔒"}</span>
      <h3>${t(mundo.clave)}</h3>
      <button type="button" ${desbloqueado ? "" : "disabled"}>${
        desbloqueado ? t("dash.play") : `⭐ ${mundo.umbral} ${t("dash.points").toLowerCase()}`
      }</button>
    `;
    if (desbloqueado) {
      div.querySelector("button").addEventListener("click", () => {
        window.location.href = `activity.html?nivel=${mundo.nivel}`;
      });
    }
    contenedor.appendChild(div);
  }
}
