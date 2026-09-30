import { apiFetch } from "../api.js";
import { montarPestanas, montarRegistrar, montarVincular } from "../estudiantes-ui.js";
import { cuando, esc, hora, porcentaje } from "../html.js";
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
const VISTAS = ["estudiantes", "ayuda", "progreso", "activos", "mundos"];
let resumen = null;
let mundos = [];

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
  document.getElementById("maquina-id").value = resumen.dispensador || "";
  pintarEstadoMaquina(resumen.dispensador);
  mundos = await apiFetch("/api/mundos");
  document.getElementById("stat-mundos").textContent = mundos.length;
  pintarVista();
}

// ---------- Máquina de premios del salón ----------
function pintarEstadoMaquina(deviceId) {
  document.getElementById("maquina-estado").textContent = deviceId
    ? `✅ ${t("machine.connected").replace("{id}", deviceId)}`
    : `ℹ️ ${t("machine.none")}`;
}

document.getElementById("form-maquina").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await apiFetch(`/api/usuarios/docente/${sesion.id_usuario}/dispensador`, {
    method: "PUT",
    body: { device_id: document.getElementById("maquina-id").value.trim() || null },
  });
  pintarEstadoMaquina(r.device_id);
});

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
  if (vista === "mundos") return pintarMundos(contenido);

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
  lista.forEach((e) => ul.appendChild(filaEstudiante(e, vista)));
  contenido.appendChild(ul);
}

// "Va en": la próxima lección de cada camino (vocabulario y gramática son independientes).
function vaEn(siguiente) {
  const iconos = { vocabulario: "📚", gramatica: "✏️", profesor: "👩‍🏫" };
  const partes = Object.keys(iconos)
    .filter((sec) => siguiente[sec])
    .map((sec) => `${iconos[sec]} ${esc(titulo(siguiente[sec].info))} · ${t("path.lesson")} ${siguiente[sec].leccion}`);
  return partes.join(" &nbsp;·&nbsp; ") || "🏆";
}

// Agrupa las lecciones de hoy en sesiones: si entre una y otra pasan menos de 15 minutos,
// cuentan como la misma sesión. "9:10 – 9:40 p. m. · 5 lecciones".
function sesiones(horas, idioma) {
  const grupos = [];
  for (const iso of horas) {
    const fecha = new Date(iso);
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && fecha - ultimo.fin <= 15 * 60 * 1000) {
      ultimo.fin = fecha;
      ultimo.n += 1;
    } else {
      grupos.push({ inicio: fecha, fin: fecha, n: 1 });
    }
  }
  return grupos
    .map((g) => {
      const desde = hora(g.inicio.toISOString(), idioma);
      const hasta = hora(g.fin.toISOString(), idioma);
      const rango = desde === hasta ? desde : `${desde} – ${hasta}`;
      return `<span class="pill">${rango} · ${g.n} ${g.n === 1 ? t("teacher.lesson_one") : t("teacher.lessons_many")}</span>`;
    })
    .join(" ");
}

function filaEstudiante(e, vista) {
  const mostrarMotivos = vista === "ayuda";
  const idioma = idiomaActual();
  const li = document.createElement("li");
  li.className = "student-row";
  const avance = Math.round((e.lecciones_aprobadas / e.total_lecciones) * 100);
  li.innerHTML = `
    <span class="avatar-perfil mini ${esc(e.perfil?.marco || "")}">${esc(e.perfil?.avatar_emoji || "🧒")}</span>
    <div class="info">
      <strong>${esc(e.nombre)}</strong>
      ${e.codigo_acceso ? `<span class="pill pill-codigo">🪪 ${esc(e.codigo_acceso)}</span>` : ""}
      ${e.necesita_ayuda ? `<span class="pill alerta">${t("teacher.needs_help_badge")}</span>` : ""}
      <div class="hint">${t("path.lessons")}: ${e.lecciones_aprobadas}/${e.total_lecciones} · ${t("path.accuracy")}: ${porcentaje(e.precision)} · 🏆 ${e.mundos_completados}</div>
      <div class="hint">${t("teacher.now_on")}: ${vaEn(e.siguiente)}</div>
      <div class="hint">🕑 ${t("teacher.last_active")}: ${e.ultima_actividad ? cuando(e.ultima_actividad, idioma) : t("teacher.never")}</div>
      ${vista === "activos" && e.horas_hoy.length ? `<div class="horas-hoy">⚡ ${t("teacher.active_at")}: ${sesiones(e.horas_hoy, idioma)}</div>` : ""}
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
    .map((r) => `<li>${r.aprobada ? "✅" : "💔"} ${esc(r.emoji)} ${esc(titulo(r))} · ${t("path.lesson")} ${r.leccion}
        <span class="hint">${r.aprobada ? `${r.aciertos}/${r.total}` : `${r.errores} ${t("path.errors")}`}${r.modo === "practica" ? " · " + t("path.practice") : ""} · ${cuando(r.fecha, idiomaActual())}</span></li>`)
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


// ---------- Mis mundos: el docente crea mundos y preguntas de selección múltiple ----------
function pintarMundos(contenido) {
  contenido.innerHTML = `
    <form class="form-mundo" id="form-mundo">
      <h3>➕ ${t("worlds.create")}</h3>
      <div class="fila-form">
        <label class="sr-only" for="mundo-emoji">Emoji</label>
        <input id="mundo-emoji" class="campo-emoji" maxlength="8" value="🌟" aria-label="Emoji" />
        <label class="sr-only" for="mundo-titulo">${t("worlds.name")}</label>
        <input id="mundo-titulo" maxlength="40" required placeholder="${t("worlds.name_placeholder")}" />
      </div>
      <label for="mundo-descripcion">${t("worlds.description")}</label>
      <input id="mundo-descripcion" maxlength="140" placeholder="${t("worlds.description_placeholder")}" />
      <button type="submit">${t("worlds.create")}</button>
      <p class="error-msg" id="error-mundo" role="alert"></p>
    </form>
    <div id="lista-mundos"></div>
  `;
  document.getElementById("form-mundo").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await apiFetch("/api/mundos", {
        method: "POST",
        body: {
          titulo: document.getElementById("mundo-titulo").value,
          emoji: document.getElementById("mundo-emoji").value || "🌟",
          descripcion: document.getElementById("mundo-descripcion").value,
        },
      });
      await recargarMundos();
    } catch (err) {
      document.getElementById("error-mundo").textContent = err.message;
    }
  });
  pintarListaMundos();
}

async function recargarMundos(abrir) {
  mundos = await apiFetch("/api/mundos");
  document.getElementById("stat-mundos").textContent = mundos.length;
  pintarVista();
  if (abrir) document.querySelector(`[data-mundo="${abrir}"] .btn-preguntas`)?.click();
}

function pintarListaMundos() {
  const lista = document.getElementById("lista-mundos");
  if (!mundos.length) {
    lista.innerHTML = `<p class="vacio">🌍 ${t("worlds.empty")}</p>`;
    return;
  }
  lista.innerHTML = "";
  for (const m of mundos) {
    const tarjeta = document.createElement("div");
    tarjeta.className = "mundo-docente";
    tarjeta.dataset.mundo = m.id_mundo;
    tarjeta.innerHTML = `
      <div class="mundo-cabecera">
        <span class="unidad-emoji">${esc(m.emoji)}</span>
        <div class="unidad-info">
          <strong>${esc(m.titulo)}</strong>
          <span class="hint">${m.preguntas} ${t("worlds.questions")} · ${m.lecciones} ${t("path.lessons").toLowerCase()}
            ${m.preguntas ? "" : ` · ${t("worlds.hidden_until")}`}</span>
          ${m.descripcion ? `<span class="hint">${esc(m.descripcion)}</span>` : ""}
        </div>
        <div class="acciones">
          <button type="button" class="secundario btn-preguntas" aria-expanded="false">✏️ ${t("worlds.edit")}</button>
          <button type="button" class="secundario btn-borrar-mundo" aria-label="${t("worlds.delete")}">🗑️</button>
        </div>
      </div>
      <div class="mundo-preguntas oculto"></div>
    `;
    const panel = tarjeta.querySelector(".mundo-preguntas");
    const boton = tarjeta.querySelector(".btn-preguntas");
    boton.addEventListener("click", async () => {
      const abrir = panel.classList.contains("oculto");
      panel.classList.toggle("oculto", !abrir);
      boton.setAttribute("aria-expanded", String(abrir));
      if (abrir) await pintarPreguntas(m, panel);
    });
    tarjeta.querySelector(".btn-borrar-mundo").addEventListener("click", async () => {
      if (!confirm(t("worlds.confirm_delete").replace("{mundo}", m.titulo))) return;
      await apiFetch(`/api/mundos/${m.id_mundo}`, { method: "DELETE" });
      await recargarMundos();
    });
    lista.appendChild(tarjeta);
  }
}

async function pintarPreguntas(mundo, panel) {
  const preguntas = await apiFetch(`/api/mundos/${mundo.id_mundo}/preguntas`);
  panel.innerHTML = `
    <ol class="lista-preguntas">${
      preguntas
        .map((p, i) => `<li>
          ${i % 8 === 0 ? `<span class="pill">${t("path.lesson")} ${i / 8 + 1}</span>` : ""}
          ${p.imagen ? `<img class="miniatura-pregunta" src="${esc(p.imagen)}" alt="" />` : ""}
          <span>${p.icono ? esc(p.icono) + " " : ""}<strong>${esc(p.pregunta)}</strong></span>
          <span class="hint">${p.opciones.map((o) => (o === p.respuesta_correcta ? `✅ ${esc(o)}` : esc(o))).join(" · ")}</span>
          <button type="button" class="secundario btn-borrar-pregunta" data-id="${esc(p.id_actividad)}" aria-label="${t("worlds.delete")}">🗑️</button>
        </li>`)
        .join("") || `<li class="hint">${t("worlds.no_questions")}</li>`
    }</ol>
    <form class="form-pregunta">
      <h4>➕ ${t("worlds.new_question")}</h4>
      <p class="hint">${t("worlds.multiple_choice_hint")}</p>
      <div class="fila-form">
        <input class="campo-emoji" name="icono" maxlength="8" placeholder="🐶" aria-label="${t("worlds.icon")}" />
        <input name="pregunta" maxlength="200" required placeholder="${t("worlds.question_placeholder")}" aria-label="${t("worlds.question")}" />
      </div>
      <div class="campo-imagen">
        <label class="boton-archivo secundario">🖼️ ${t("worlds.image")}
          <input type="file" name="imagen" accept="image/*" class="sr-only" />
        </label>
        <img class="vista-imagen oculto" alt="" />
        <button type="button" class="secundario btn-quitar-imagen oculto">✖ ${t("worlds.remove_image")}</button>
      </div>
      ${[0, 1, 2, 3]
        .map((i) => `<label class="opcion-form">
          <input type="radio" name="correcta" value="${i}" ${i === 0 ? "checked" : ""} aria-label="${t("worlds.mark_correct")}" />
          <input name="opcion${i}" maxlength="60" ${i < 2 ? "required" : ""}
            placeholder="${t("worlds.option")} ${i + 1}${i < 2 ? "" : ` (${t("worlds.optional")})`}" />
        </label>`)
        .join("")}
      <p class="hint">🔘 = ${t("worlds.mark_correct")}</p>
      <button type="submit">${t("worlds.add_question")}</button>
      <p class="error-msg" role="alert"></p>
    </form>
  `;
  panel.querySelectorAll(".btn-borrar-pregunta").forEach((b) =>
    b.addEventListener("click", async () => {
      await apiFetch(`/api/mundos/${mundo.id_mundo}/preguntas/${b.dataset.id}`, { method: "DELETE" });
      await recargarMundos(mundo.id_mundo);
    })
  );
  const form = panel.querySelector(".form-pregunta");
  const error = form.querySelector(".error-msg");
  const entradaImagen = form.querySelector('input[name="imagen"]');
  const vista = form.querySelector(".vista-imagen");
  const quitar = form.querySelector(".btn-quitar-imagen");
  let imagen = null;
  const ponerImagen = (url) => {
    imagen = url;
    vista.src = url || "";
    vista.classList.toggle("oculto", !url);
    quitar.classList.toggle("oculto", !url);
  };
  entradaImagen.addEventListener("change", async () => {
    const archivo = entradaImagen.files[0];
    entradaImagen.value = "";
    if (!archivo) return;
    error.textContent = "";
    try {
      ponerImagen(await achicarImagen(archivo));
    } catch {
      ponerImagen(null);
      error.textContent = t("worlds.image_error");
    }
  });
  quitar.addEventListener("click", () => ponerImagen(null));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const datos = new FormData(form);
    const opciones = [0, 1, 2, 3].map((i) => (datos.get(`opcion${i}`) || "").trim());
    const correcta = opciones[Number(datos.get("correcta"))];
    if (!correcta) {
      error.textContent = t("worlds.correct_empty");
      return;
    }
    try {
      await apiFetch(`/api/mundos/${mundo.id_mundo}/preguntas`, {
        method: "POST",
        body: {
          pregunta: datos.get("pregunta"),
          icono: datos.get("icono") || null,
          imagen,
          opciones: opciones.filter(Boolean),
          respuesta_correcta: correcta,
        },
      });
      await recargarMundos(mundo.id_mundo);
    } catch (err) {
      error.textContent = err.message;
    }
  });
}

// La imagen se achica en el navegador (máx. 480 px, JPEG) antes de subirla: así pesa unos
// pocos KB y cabe dentro de la actividad en Firestore, sin necesitar otro almacenamiento.
const LADO_MAXIMO = 480;

function achicarImagen(archivo) {
  return new Promise((resolve, reject) => {
    if (!archivo.type.startsWith("image/")) return reject(new Error("no es imagen"));
    const url = URL.createObjectURL(archivo);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const escala = Math.min(1, LADO_MAXIMO / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * escala);
      canvas.height = Math.round(img.height * escala);
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#fff"; // las zonas transparentes de un PNG quedan blancas en JPEG
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL("image/jpeg", 0.8));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("imagen inválida"));
    };
    img.src = url;
  });
}
