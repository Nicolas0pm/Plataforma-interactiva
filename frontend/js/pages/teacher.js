import { apiFetch } from "../api.js";
import { emojiHtml } from "../emoji.js";
import { cuando, esc, hora, porcentaje } from "../html.js";
import { idiomaActual, inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { agregarCambioDePassword } from "../cambiar-password.js";
import { exigirRol, salir } from "../session.js";

const sesion = exigirRol("docente");
inicializarLangToggle();
document.getElementById("btn-logout").addEventListener("click", salir);
agregarCambioDePassword();


// RF06/RF09: los botones de arriba eligen qué se ve abajo. La vista queda en la URL
// (#ayuda, #progreso...) para que al volver o recargar se mantenga.
const VISTAS = ["estudiantes", "ayuda", "progreso", "activos", "mundos", "temario"];
let resumen = null;
let mundos = [];
let temario = null;
let temaAbierto = null; // mundo del temario con sus preguntas a la vista

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
  document.getElementById("premio-cada").value = String(resumen.premio_cada_mundos || 1);
  [mundos, temario] = await Promise.all([apiFetch("/api/mundos"), apiFetch("/api/temario/salon")]);
  document.getElementById("stat-mundos").textContent = mundos.length;
  contarTemario();
  pintarVista();
}

// ---------- RF06: cada cuántos mundos se entrega el premio ----------
document.getElementById("form-premio").addEventListener("submit", (e) => e.preventDefault());
document.getElementById("premio-cada").addEventListener("change", async (e) => {
  const estado = document.getElementById("premio-estado");
  try {
    const r = await apiFetch(`/api/usuarios/docente/${sesion.id_usuario}/premio`, {
      method: "PUT",
      body: { cada_mundos: Number(e.target.value) },
    });
    estado.textContent = `✅ ${t("machine.every_saved").replace("{n}", r.cada_mundos)}`;
  } catch (err) {
    estado.textContent = err.message;
  }
});

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
  if (vista === "temario") return pintarTemario(contenido);

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

  const examenes = (aprendizaje.examenes || [])
    .map((x) => `<li>${x.estado === "aprobado" ? "✅" : "📝"} ${x.mundos.map((m) => `${esc(m.emoji)} ${esc(titulo(m))}`).join(", ")}
        <span class="hint">${x.intentos ? `${x.mejor}/${x.total} · ${x.intentos} ${t("exam.attempts")}` : t("exam.not_taken")}${x.da_premio ? " · 🎁" : ""}</span></li>`)
    .join("");

  detalle.innerHTML = `
    <div class="detalle-grid">
      <section><h3>📝 ${t("exam.title_plural")}</h3><ul class="lista-intentos">${examenes || `<li class="hint">${t("exam.none")}</li>`}</ul></section>
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


// ---------- RF07: qué mundos del temario ve el salón y en qué orden ----------
const visible = (m) => m.activo && m.global_activo;

function contarTemario() {
  const n = Object.values(temario).flat().filter(visible).length;
  document.getElementById("stat-temario").textContent = n;
}

function pintarTemario(contenido) {
  const secciones = [["vocabulario", "📚", "path.vocabulary"], ["gramatica", "✏️", "path.grammar"]];
  for (const [seccion, emoji, clave] of secciones) {
    const bloque = document.createElement("section");
    bloque.className = "bloque-temario";
    bloque.dataset.seccion = seccion;
    bloque.innerHTML = `<h3>${emoji} ${t(clave)}</h3><ol class="lista-temario"></ol><p class="error-msg" role="alert"></p>`;
    const lista = bloque.querySelector("ol");
    const unidades = temario[seccion];
    unidades.forEach((m, i) => {
      const li = document.createElement("li");
      li.className = `tema${visible(m) ? "" : " apagado"}`;
      const id = `tema-${m.id}`;
      li.innerHTML = `
        <input type="checkbox" id="${id}" ${m.activo ? "checked" : ""} ${m.global_activo ? "" : "disabled"} />
        <label for="${id}"><span aria-hidden="true">${m.emoji}</span> ${esc(titulo(m))}
          <small>${m.lecciones} ${t("syllabus.lessons")}${m.global_activo ? "" : ` · ${t("syllabus.off_global")}`}</small></label>
        <span class="mover">
          <button type="button" class="secundario btn-editar-tema" aria-expanded="${temaAbierto === m.id}"
            aria-label="${t("syllabus.edit_questions")}: ${esc(titulo(m))}" title="${t("syllabus.edit_questions")}">✏️</button>
          <button type="button" class="secundario" data-mover="-1" ${i === 0 ? "disabled" : ""} aria-label="${t("syllabus.up")}">↑</button>
          <button type="button" class="secundario" data-mover="1" ${i === unidades.length - 1 ? "disabled" : ""} aria-label="${t("syllabus.down")}">↓</button>
        </span>`;
      li.querySelector("input").addEventListener("change", (e) => {
        const nuevo = unidades.map((u) => (u.id === m.id ? { ...u, activo: e.target.checked } : u));
        guardarTemario(seccion, nuevo);
      });
      li.querySelectorAll("[data-mover]").forEach((b) => b.addEventListener("click", () => {
        const nuevo = [...unidades];
        const j = i + Number(b.dataset.mover);
        [nuevo[i], nuevo[j]] = [nuevo[j], nuevo[i]];
        guardarTemario(seccion, nuevo, m.id, b.dataset.mover);
      }));
      li.querySelector(".btn-editar-tema").addEventListener("click", () => {
        temaAbierto = temaAbierto === m.id ? null : m.id;
        pintarVista();
        document.querySelector(`#tema-${m.id}`)?.closest("li").querySelector(".btn-editar-tema")?.focus();
      });
      lista.appendChild(li);
      if (temaAbierto === m.id) {
        const panel = document.createElement("div");
        panel.className = "panel-preguntas-tema";
        li.appendChild(panel);
        pintarPreguntasTema(m, panel);
      }
    });
    contenido.appendChild(bloque);
  }
}

// ---------- Preguntas de un mundo del temario, cambiadas solo para este salón ----------
async function pintarPreguntasTema(mundo, panel) {
  panel.innerHTML = `<p class="hint">${t("activity.loading")}</p>`;
  const datos = await apiFetch(`/api/temario/salon/${mundo.id}/preguntas`);
  const opcionHtml = (p, o) => (p.formato_opciones === "emoji" ? emojiHtml(o) : esc(o));
  panel.innerHTML = `
    <p class="hint">${t("syllabus.questions_hint")}</p>
    <p class="error-msg" role="alert"></p>
    ${datos.lecciones.map((l) => `
      <h4>${t("path.lesson")} ${l.numero}</h4>
      <ol class="lista-preguntas">${l.preguntas.map((p) => `
        <li class="${p.visible ? "" : "oculta"}" data-id="${esc(p.id_actividad)}">
          <span>${p.icono ? emojiHtml(p.icono) + " " : ""}<strong>${esc(p.pregunta)}</strong>
            ${p.editada ? `<span class="pill">${t("syllabus.edited")}</span>` : ""}
            ${p.visible ? "" : `<span class="pill">${t("syllabus.hidden")}</span>`}</span>
          <span class="hint">${p.opciones.map((o) => (o === p.respuesta_correcta ? `✅ ${opcionHtml(p, o)}` : opcionHtml(p, o))).join(" · ")}</span>
          <span class="acciones-pregunta">
            <button type="button" class="secundario" data-accion="editar">${t("syllabus.edit")}</button>
            <button type="button" class="secundario" data-accion="${p.visible ? "ocultar" : "mostrar"}">${t(p.visible ? "syllabus.hide" : "syllabus.show")}</button>
            ${p.editada || !p.visible ? `<button type="button" class="secundario" data-accion="restaurar">${t("syllabus.restore")}</button>` : ""}
          </span>
        </li>`).join("")}</ol>`).join("")}`;
  const error = panel.querySelector(".error-msg");
  const preguntas = Object.fromEntries(datos.lecciones.flatMap((l) => l.preguntas).map((p) => [p.id_actividad, p]));
  const recargar = () => pintarPreguntasTema(mundo, panel);
  panel.querySelectorAll("[data-accion]").forEach((boton) => boton.addEventListener("click", async () => {
    const li = boton.closest("li");
    const p = preguntas[li.dataset.id];
    const url = `/api/temario/salon/preguntas/${encodeURIComponent(p.id_actividad)}`;
    error.textContent = "";
    try {
      if (boton.dataset.accion === "editar") return editarPreguntaTema(p, li, url, recargar);
      if (boton.dataset.accion === "restaurar") await apiFetch(url, { method: "DELETE" });
      else await apiFetch(url, { method: "PATCH", body: { activo: boton.dataset.accion === "mostrar" } });
      await recargar();
    } catch (err) {
      error.textContent = err.message;
    }
  }));
}

function editarPreguntaTema(p, li, url, recargar) {
  li.innerHTML = `
    <form class="form-pregunta">
      <label>${t("worlds.question")}<input name="pregunta" maxlength="200" required value="${esc(p.pregunta)}" /></label>
      ${[0, 1, 2, 3].map((i) => `<label class="opcion-form">
          <input type="radio" name="correcta" value="${i}" ${p.opciones[i] === p.respuesta_correcta ? "checked" : ""}
            aria-label="${t("worlds.mark_correct")}" />
          <input name="opcion${i}" maxlength="60" ${i < 2 ? "required" : ""} value="${esc(p.opciones[i] || "")}"
            placeholder="${t("worlds.option")} ${i + 1}${i < 2 ? "" : ` (${t("worlds.optional")})`}" />
        </label>`).join("")}
      <p class="hint">🔘 = ${t("worlds.mark_correct")}</p>
      <div class="fila-form">
        <button type="submit">${t("syllabus.save")}</button>
        <button type="button" class="secundario btn-cancelar">${t("password.cancel")}</button>
      </div>
      <p class="error-msg" role="alert"></p>
    </form>`;
  const form = li.querySelector("form");
  form.querySelector('input[name="pregunta"]').focus();
  form.querySelector(".btn-cancelar").addEventListener("click", recargar);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const datos = new FormData(form);
    const opciones = [0, 1, 2, 3].map((i) => (datos.get(`opcion${i}`) || "").trim());
    const correcta = opciones[Number(datos.get("correcta"))];
    if (!correcta) {
      form.querySelector(".error-msg").textContent = t("worlds.correct_empty");
      return;
    }
    try {
      await apiFetch(url, { method: "PUT", body: { pregunta: datos.get("pregunta"), opciones: opciones.filter(Boolean), respuesta_correcta: correcta } });
      await recargar();
    } catch (err) {
      form.querySelector(".error-msg").textContent = err.message;
    }
  });
}

async function guardarTemario(seccion, unidades, enfocar, direccion) {
  try {
    temario = await apiFetch(`/api/temario/salon/${seccion}`, {
      method: "PUT",
      body: { unidades: unidades.map(({ id, activo }) => ({ id, activo })) },
    });
    contarTemario();
    pintarVista();
    // Al mover con el teclado, el foco sigue al mundo que se movió.
    if (enfocar) {
      const boton = document.querySelector(`#tema-${enfocar}`)?.closest("li").querySelector(`[data-mover="${direccion}"]`);
      (boton && !boton.disabled ? boton : document.getElementById(`tema-${enfocar}`))?.focus();
    }
  } catch (err) {
    pintarVista(); // vuelve a mostrar lo que quedó guardado
    document.querySelector(`[data-seccion="${seccion}"] .error-msg`).textContent = err.message;
  }
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
