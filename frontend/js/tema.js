// Selector de tema (claro, oscuro, noche morada, rosa dulce o automático).
//
// El tema se guarda en localStorage y se aplica como <html data-tema="...">; los
// colores están en css/style.css. Cada página tiene además un script mínimo en el
// <head> que aplica el tema guardado antes de dibujar, para que no parpadee.
// Este módulo agrega el botón 🎨 al final de la barra superior de la página.

import { t } from "./i18n.js";

const CLAVE_TEMA = "pik_tema";

export const TEMAS = [
  { id: "auto", icono: "🖥️", clave: "theme.auto", muestra: ["#f6f9fc", "#0f1720"] },
  { id: "claro", icono: "☀️", clave: "theme.light", muestra: ["#f6f9fc", "#3aa9d6"] },
  { id: "oscuro", icono: "🌙", clave: "theme.dark", muestra: ["#0f1720", "#4cb8e4"] },
  { id: "morado", icono: "🔮", clave: "theme.purple", muestra: ["#130d22", "#a88bff"] },
  { id: "dulce", icono: "🍬", clave: "theme.pink", muestra: ["#fff5f9", "#ff78b0"] },
];

export function temaActual() {
  try {
    const guardado = localStorage.getItem(CLAVE_TEMA);
    return TEMAS.some((tema) => tema.id === guardado) ? guardado : "auto";
  } catch {
    return "auto";
  }
}

export function aplicarTema(id) {
  document.documentElement.dataset.tema = id;
  try {
    localStorage.setItem(CLAVE_TEMA, id);
  } catch {
    /* sin almacenamiento (modo privado): el tema dura solo esta página */
  }
}

function crearSelector() {
  const barras = document.querySelectorAll(".topbar .topbar-actions");
  const contenedor = barras[barras.length - 1];
  if (!contenedor) return;

  const envoltura = document.createElement("div");
  envoltura.className = "selector-tema";
  envoltura.innerHTML = `
    <button type="button" class="btn-tema" aria-haspopup="true" aria-expanded="false"
            data-i18n-title="theme.title" title="${t("theme.title")}">🎨</button>
    <div class="menu-tema" role="menu" hidden>
      <p class="menu-tema-titulo" data-i18n="theme.title">${t("theme.title")}</p>
      ${TEMAS.map(
        (tema) => `
        <button type="button" role="menuitemradio" data-tema="${tema.id}">
          <span class="muestra" style="background: linear-gradient(135deg, ${tema.muestra[0]} 50%, ${tema.muestra[1]} 50%)"></span>
          <span>${tema.icono}</span>
          <span data-i18n="${tema.clave}">${t(tema.clave)}</span>
        </button>`
      ).join("")}
    </div>
  `;
  contenedor.prepend(envoltura);

  const boton = envoltura.querySelector(".btn-tema");
  const menu = envoltura.querySelector(".menu-tema");

  const marcarActual = () => {
    const actual = temaActual();
    menu.querySelectorAll("[data-tema]").forEach((opcion) => {
      opcion.setAttribute("aria-checked", String(opcion.dataset.tema === actual));
    });
  };
  const abrir = (abierto) => {
    menu.hidden = !abierto;
    boton.setAttribute("aria-expanded", String(abierto));
    if (abierto) marcarActual();
  };

  boton.addEventListener("click", (evento) => {
    evento.stopPropagation();
    abrir(menu.hidden);
  });
  menu.addEventListener("click", (evento) => {
    const opcion = evento.target.closest("[data-tema]");
    if (!opcion) return;
    aplicarTema(opcion.dataset.tema);
    abrir(false);
    boton.focus();
  });
  document.addEventListener("click", (evento) => {
    if (!envoltura.contains(evento.target)) abrir(false);
  });
  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape" && !menu.hidden) {
      abrir(false);
      boton.focus();
    }
  });
}

document.documentElement.dataset.tema = temaActual();
crearSelector();
