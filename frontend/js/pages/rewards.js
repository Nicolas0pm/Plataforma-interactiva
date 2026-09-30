import { apiFetch } from "../api.js";
import { esc } from "../html.js";
import { idiomaActual, inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { exigirRol } from "../session.js";

// Tienda del perfil (los puntos se gastan en avatares y marcos) + mundos completados
// (el premio real: con máquina suelta un juguete; sin máquina, es una felicitación).
const sesion = exigirRol("estudiante");
inicializarLangToggle();

let tienda = null;
if (sesion) {
  cargarTienda();
  cargarMundos(sesion);
}

const nombre = (x) => x[idiomaActual()] || x.es;

export function pintarAvatar(elemento, perfil) {
  elemento.textContent = perfil.avatar_emoji;
  elemento.className = `avatar-perfil ${elemento.classList.contains("grande") ? "grande" : ""} ${perfil.marco ? perfil.marco : ""}`.trim();
}

async function cargarTienda() {
  tienda = await apiFetch("/api/tienda");
  pintarTienda();
}

function pintarTienda() {
  const perfil = tienda.perfil;
  pintarAvatar(document.getElementById("mi-avatar"), perfil);
  document.getElementById("saldo").textContent = perfil.saldo;

  for (const tipo of ["avatar", "marco"]) {
    const contenedor = document.getElementById(tipo === "avatar" ? "tienda-avatares" : "tienda-marcos");
    contenedor.innerHTML = "";
    if (tipo === "marco") contenedor.appendChild(tarjetaQuitarMarco(perfil));
    for (const item of tienda.items.filter((i) => i.tipo === tipo)) {
      const tiene = perfil.comprados.includes(item.id);
      const puesto = perfil[tipo] === item.id;
      const alcanza = perfil.saldo >= item.precio;
      const tarjeta = document.createElement("div");
      tarjeta.className = `tienda-item ${puesto ? "puesto" : ""}`;
      tarjeta.innerHTML = `
        <div class="avatar-perfil ${tipo === "marco" ? item.id : ""}">${esc(tipo === "marco" ? perfil.avatar_emoji : item.emoji)}</div>
        <strong>${esc(nombre(item.nombre))}</strong>
        <button type="button" class="${tiene ? "secundario" : ""}" ${puesto || (!tiene && !alcanza) ? "disabled" : ""}>
          ${puesto ? `✅ ${t("shop.equipped")}` : tiene ? t("shop.use") : `⭐ ${item.precio}`}
        </button>`;
      tarjeta.querySelector("button").addEventListener("click", () => (tiene ? equipar(item.id, tipo) : comprar(item)));
      contenedor.appendChild(tarjeta);
    }
  }
}

function tarjetaQuitarMarco(perfil) {
  const tarjeta = document.createElement("div");
  tarjeta.className = `tienda-item ${perfil.marco ? "" : "puesto"}`;
  tarjeta.innerHTML = `
    <div class="avatar-perfil">${esc(perfil.avatar_emoji)}</div>
    <strong>${t("shop.no_frame")}</strong>
    <button type="button" class="secundario" ${perfil.marco ? "" : "disabled"}>${perfil.marco ? t("shop.use") : `✅ ${t("shop.equipped")}`}</button>`;
  tarjeta.querySelector("button").addEventListener("click", () => equipar(null, "marco"));
  return tarjeta;
}

async function comprar(item) {
  document.getElementById("error-tienda").textContent = "";
  try {
    tienda.perfil = await apiFetch("/api/tienda/comprar", { method: "POST", body: { item_id: item.id } });
    pintarTienda();
  } catch (err) {
    document.getElementById("error-tienda").textContent = err.message;
  }
}

async function equipar(itemId, tipo) {
  tienda.perfil = await apiFetch("/api/tienda/equipar", { method: "POST", body: { item_id: itemId, tipo } });
  pintarTienda();
}

async function cargarMundos(sesion) {
  const recompensas = (await apiFetch(`/api/recompensas/estudiante/${sesion.id_usuario}`)).filter((r) => r.tipo === "mundo");
  const lista = document.getElementById("lista-recompensas");
  lista.innerHTML = "";
  if (!recompensas.length) {
    document.getElementById("sin-recompensas").classList.remove("oculto");
    return;
  }
  recompensas.sort((a, b) => new Date(b.fecha_entrega) - new Date(a.fecha_entrega));
  for (const r of recompensas) {
    // "Pendiente/Entregado" solo si hay máquina: sin ella no hay entrega física que anunciar.
    const estado = r.device_id
      ? `<span class="pill ${r.estado === "entregada" ? "entregada" : "pendiente"}">
           ${r.estado === "entregada" ? `🎁 ${t("rewards.delivered")}` : `🎁 ${t("rewards.pending")}`}</span>`
      : `<span class="pill entregada">🎉</span>`;
    const li = document.createElement("li");
    li.className = "reward-item";
    li.innerHTML = `<span class="emoji">${esc(r.emoji || "🏆")}</span><span>${esc(nombre(r.titulo || { es: "" }))}</span>${estado}`;
    lista.appendChild(li);
  }
}
