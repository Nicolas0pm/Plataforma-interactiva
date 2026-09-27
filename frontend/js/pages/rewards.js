import { apiFetch } from "../api.js";
import { inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { exigirRol } from "../session.js";

const sesion = exigirRol("estudiante");
inicializarLangToggle();

const EMOJIS = ["🏅", "🎟️", "🧸", "🍬", "🌟"];

if (sesion) cargar(sesion);

async function cargar(sesion) {
  const recompensas = await apiFetch(`/api/recompensas/estudiante/${sesion.id_usuario}`);
  const lista = document.getElementById("lista-recompensas");
  lista.innerHTML = "";

  if (!recompensas.length) {
    document.getElementById("sin-recompensas").classList.remove("oculto");
    return;
  }

  recompensas.forEach((r, i) => {
    // El estado "Pendiente/Entregada" solo tiene sentido si hay un dispensador
    // (device_id) sincronizado a este estudiante. Sin eso, no hay una entrega
    // física en curso que anunciar — se muestra el logro sin esa parte.
    const pill = r.device_id
      ? `<span class="pill ${r.estado === "entregada" ? "entregada" : "pendiente"}">
           ${r.estado === "entregada" ? t("rewards.delivered") : t("rewards.pending")}
         </span>`
      : "";

    const li = document.createElement("li");
    li.className = "reward-item";
    li.innerHTML = `
      <span class="emoji">${EMOJIS[i % EMOJIS.length]}</span>
      <span>${r.puntos_consumidos} pts</span>
      ${pill}
    `;
    lista.appendChild(li);
  });
}
