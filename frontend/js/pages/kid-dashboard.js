import { apiFetch } from "../api.js";
import { emojiHtml } from "../emoji.js";
import { esc, porcentaje } from "../html.js";
import { idiomaActual, inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { exigirRol, salir } from "../session.js";
import { actualizarVidas, corazones, minutosHasta } from "../vidas.js";

const sesion = exigirRol("estudiante");
inicializarLangToggle();
document.getElementById("btn-logout").addEventListener("click", salir);
if (sesion) iniciar(sesion);

const titulo = (unidad) => unidad.titulo[idiomaActual()] || unidad.titulo.es;

const CLAVE_SECCION = "pik_seccion";
let resumen = null;

const SECCIONES = {
  vocabulario: { emoji: "📚", clave: "path.vocabulary" },
  gramatica: { emoji: "✏️", clave: "path.grammar" },
  profesor: { emoji: "👩‍🏫", clave: "path.teacher" },
};

function seccionElegida() {
  try {
    const guardada = localStorage.getItem(CLAVE_SECCION);
    return SECCIONES[guardada] ? guardada : "vocabulario";
  } catch {
    return "vocabulario";
  }
}

// Botones "📚 Vocabulario | ✏️ Gramática": el niño elige el apartado.
document.querySelectorAll("[data-seccion]").forEach((boton) => {
  boton.addEventListener("click", () => {
    try {
      localStorage.setItem(CLAVE_SECCION, boton.dataset.seccion);
    } catch {
      /* sin almacenamiento: la elección dura solo esta visita */
    }
    pintarSeccion();
  });
});

async function iniciar(sesion) {
  document.getElementById("titulo-hola").textContent = `${t("dash.hello")} ${sesion.nombre || ""} 👋`;
  if (sesion.codigo_acceso) {
    document.getElementById("mi-codigo-valor").textContent = sesion.codigo_acceso;
    document.getElementById("mi-codigo").classList.remove("oculto");
  }

  resumen = await apiFetch(`/api/lecciones/resumen/${sesion.id_usuario}`);
  const avatar = document.getElementById("mi-avatar");
  avatar.textContent = resumen.perfil.avatar_emoji;
  if (resumen.perfil.marco) avatar.classList.add(resumen.perfil.marco);
  document.getElementById("saldo").textContent = resumen.perfil.saldo;
  document.getElementById("stat-mundos").textContent = resumen.mundos_completados;
  pintarEstadisticas(resumen);
  pintarRecientes(resumen.recientes);
  pintarSeccion();
  // Las vidas se recargan con el tiempo: se revisa cada 20 s sin volver a pedir nada al servidor.
  setInterval(() => {
    const antes = resumen.vidas.actuales;
    resumen.vidas = actualizarVidas(resumen.vidas);
    pintarVidas();
    if (resumen.vidas.actuales !== antes) pintarSeccion();
  }, 20000);
}

function pintarSeccion() {
  if (!resumen) return;
  const seccion = seccionElegida();
  document.querySelectorAll("[data-seccion]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.seccion === seccion)));
  document.getElementById("camino-titulo").textContent = `${SECCIONES[seccion].emoji} ${t(SECCIONES[seccion].clave)}`;
  const avance = resumen.por_seccion[seccion];
  document.getElementById("stat-lecciones").textContent = `${avance.aprobadas}/${avance.total}`;
  document.getElementById("barra-nivel").style.width = `${avance.total ? Math.round((avance.aprobadas / avance.total) * 100) : 0}%`;
  if (seccion === "profesor" && !avance.total) {
    // El profe todavía no ha creado mundos (o el niño no tiene profe vinculado).
    document.getElementById("proxima-emoji").textContent = "👩‍🏫";
    document.getElementById("proxima-titulo").textContent = t("path.teacher_empty");
    document.getElementById("proxima-detalle").textContent = t("path.teacher_empty_hint");
    document.getElementById("btn-empezar").classList.add("oculto");
    document.getElementById("camino").innerHTML = "";
    return;
  }
  pintarProxima(resumen.siguiente[seccion], seccion);
  pintarCamino(resumen, seccion, document.getElementById("camino"));
}

function pintarProxima(siguiente, seccion) {
  const boton = document.getElementById("btn-empezar");
  if (!siguiente) {
    document.getElementById("proxima-emoji").textContent = "🏆";
    document.getElementById("proxima-titulo").textContent = t("path.all_done");
    document.getElementById("proxima-detalle").textContent = t("path.all_done_hint");
    boton.classList.add("oculto");
    return;
  }
  boton.classList.remove("oculto");
  const info = siguiente.info;
  document.getElementById("proxima-emoji").innerHTML = emojiHtml(info.emoji);
  document.getElementById("proxima-titulo").textContent = titulo(info);
  const nombreSeccion = t(SECCIONES[seccion].clave);
  const modo = siguiente.modo === "repaso" ? ` · 🔁 ${t("path.review")}` : "";
  document.getElementById("proxima-detalle").textContent =
    `${nombreSeccion} · ${t("path.lesson")} ${siguiente.leccion} ${t("path.of")} ${info.lecciones}${modo}`;
  // Solo el apartado: la lección la vuelve a elegir el servidor al abrir la actividad.
  boton.onclick = () => (window.location.href = `activity.html?seccion=${seccion}`);
  // Sin vidas no puede empezar lecciones nuevas ni repasos (practicar sí, desde el camino).
  const sinVidas = resumen.vidas.actuales === 0;
  boton.disabled = sinVidas;
  if (sinVidas) {
    document.getElementById("proxima-detalle").textContent = t("path.no_lives").replace(
      "{min}", minutosHasta(resumen.vidas.proxima_vida)
    );
  }
}

function pintarVidas() {
  const v = resumen.vidas;
  document.getElementById("mis-vidas").textContent = corazones(v.actuales, v.maximo);
  document.getElementById("mis-vidas").setAttribute("aria-label", `${v.actuales} ${t("activity.lives")}`);
  document.getElementById("proxima-vida").textContent =
    v.actuales < v.maximo ? t("path.next_life").replace("{min}", minutosHasta(v.proxima_vida)) : t("path.lives_full");
}

function pintarEstadisticas(resumen) {
  pintarVidas();
  document.getElementById("stat-nivel").textContent = resumen.nivel_logrado;
  document.getElementById("stat-puntos").textContent = resumen.puntaje_total;
  document.getElementById("stat-precision").textContent = porcentaje(resumen.precision);
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
      <span class="unidad-emoji" aria-hidden="true">${bloqueada ? "🔒" : emojiHtml(unidad.emoji)}</span>
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
        // Si toca repasar una lección ya aprobada, se ve 🔁 (no ▶, que es lección nueva).
        b.textContent = leccion.aprobada ? "🔁" : "▶";
        b.title = leccion.aprobada ? `${t("path.review")} · ${leccion.mejor}/${leccion.total}` : t("path.start");
        b.addEventListener("click", () => (window.location.href = `activity.html?seccion=${seccion}`));
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
