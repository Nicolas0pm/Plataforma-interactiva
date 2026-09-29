import { apiFetch } from "../api.js";
import { esc, porcentaje } from "../html.js";
import { idiomaActual, inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { exigirRol, salir } from "../session.js";

const sesion = exigirRol("estudiante");
inicializarLangToggle();
document.getElementById("btn-logout").addEventListener("click", salir);
if (sesion) iniciar(sesion);

const titulo = (unidad) => unidad.titulo[idiomaActual()] || unidad.titulo.es;

async function iniciar(sesion) {
  document.getElementById("titulo-hola").textContent = `${t("dash.hello")} ${sesion.nombre || ""} 👋`;
  if (sesion.codigo_acceso) {
    document.getElementById("mi-codigo-valor").textContent = sesion.codigo_acceso;
    document.getElementById("mi-codigo").classList.remove("oculto");
  }

  const resumen = await apiFetch(`/api/lecciones/resumen/${sesion.id_usuario}`);
  pintarProxima(resumen.siguiente);
  pintarEstadisticas(resumen);
  pintarCamino(resumen, "vocabulario", document.getElementById("camino-vocabulario"));
  pintarCamino(resumen, "gramatica", document.getElementById("camino-gramatica"));
  pintarRecientes(resumen.recientes);
}

function pintarProxima(siguiente) {
  const boton = document.getElementById("btn-empezar");
  if (!siguiente) {
    document.getElementById("proxima-emoji").textContent = "🏆";
    document.getElementById("proxima-titulo").textContent = t("path.all_done");
    document.getElementById("proxima-detalle").textContent = t("path.all_done_hint");
    boton.classList.add("oculto");
    return;
  }
  const info = siguiente.info;
  document.getElementById("proxima-emoji").textContent = info.emoji;
  document.getElementById("proxima-titulo").textContent = titulo(info);
  const seccion = info.seccion === "vocabulario" ? t("path.vocabulary") : t("path.grammar");
  const modo = siguiente.modo === "repaso" ? ` · 🔁 ${t("path.review")}` : "";
  document.getElementById("proxima-detalle").textContent =
    `${seccion} · ${t("path.lesson")} ${siguiente.leccion} ${t("path.of")} ${info.lecciones}${modo}`;
  // Sin parámetros: la lección la vuelve a elegir el servidor al abrir la actividad.
  boton.addEventListener("click", () => (window.location.href = "activity.html"));
}

function pintarEstadisticas(resumen) {
  document.getElementById("stat-nivel").textContent = resumen.nivel_logrado;
  document.getElementById("stat-puntos").textContent = resumen.puntaje_total;
  document.getElementById("stat-lecciones").textContent = `${resumen.lecciones_aprobadas}/${resumen.total_lecciones}`;
  document.getElementById("stat-precision").textContent = porcentaje(resumen.precision);
  const avance = Math.round((resumen.lecciones_aprobadas / resumen.total_lecciones) * 100);
  document.getElementById("barra-nivel").style.width = `${avance}%`;
  document.getElementById("texto-siguiente-nivel").textContent =
    resumen.puntos_para_siguiente_nivel === null
      ? t("dash.max_level")
      : `${resumen.puntos_para_siguiente_nivel} ${t("dash.next_level")}`;
}

function pintarCamino(resumen, seccion, contenedor) {
  contenedor.innerHTML = "";
  for (const unidad of resumen.unidades.filter((u) => u.seccion === seccion)) {
    const fila = document.createElement("div");
    const bloqueada = unidad.lecciones.every((l) => l.estado === "bloqueada");
    fila.className = `unidad ${bloqueada ? "bloqueada" : ""}`.trim();
    fila.innerHTML = `
      <span class="unidad-emoji" aria-hidden="true">${bloqueada ? "🔒" : esc(unidad.emoji)}</span>
      <div class="unidad-info">
        <strong>${esc(titulo(unidad))}</strong>
        <span class="hint">${unidad.aprobadas}/${unidad.lecciones.length} ${t("path.lessons").toLowerCase()}
          ${unidad.precision !== null ? ` · ${porcentaje(unidad.precision)}` : ""}</span>
      </div>
      <div class="burbujas"></div>
    `;
    const burbujas = fila.querySelector(".burbujas");
    for (const leccion of unidad.lecciones) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = `burbuja ${leccion.estado}`;
      if (leccion.estado === "actual") {
        b.textContent = "▶";
        b.title = t("path.start");
        b.addEventListener("click", () => (window.location.href = "activity.html"));
      } else if (leccion.aprobada) {
        b.textContent = "✅";
        b.title = `${t("path.repeat")} · ${leccion.mejor}/${leccion.total}`;
        b.addEventListener("click", () => {
          window.location.href = `activity.html?unidad=${encodeURIComponent(unidad.id)}&leccion=${leccion.numero}`;
        });
      } else {
        b.textContent = "🔒";
        b.disabled = true;
        b.title = t("path.locked");
      }
      b.setAttribute("aria-label", `${titulo(unidad)} · ${t("path.lesson")} ${leccion.numero} · ${b.title}`);
      burbujas.appendChild(b);
    }
    contenedor.appendChild(fila);
  }
}

function pintarRecientes(recientes) {
  const lista = document.getElementById("recientes");
  if (!recientes.length) {
    lista.innerHTML = `<li class="hint">${t("path.no_attempts")}</li>`;
    return;
  }
  lista.innerHTML = recientes
    .map((r) => {
      const nombre = r.titulo[idiomaActual()] || r.titulo.es;
      const estado = r.aprobada ? "✅" : "💔";
      const extra = r.modo === "practica" ? ` · ${t("path.practice")}` : r.puntos ? ` · +${r.puntos} ⭐` : "";
      return `<li><span aria-hidden="true">${estado}</span>
        <span><strong>${esc(nombre)}</strong> · ${t("path.lesson")} ${r.leccion}</span>
        <span class="hint">${r.aprobada ? `${r.aciertos}/${r.total}${extra}` : `${r.errores} ${t("path.errors")}`}</span></li>`;
    })
    .join("");
}
