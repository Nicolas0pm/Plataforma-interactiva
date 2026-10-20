// Panel del coordinador: crea las cuentas de profesores, padres, niños y otros
// coordinadores, asigna a cada niño su profesor y sus padres, restablece contraseñas y PIN,
// corrige los datos de cada cuenta, desactiva o reactiva cuentas (nada se borra) y
// gestiona el temario de la institución (RF08).

import { API_BASE_URL, apiFetch } from "../api.js";
import { agregarCambioDePassword } from "../cambiar-password.js";
import { esc } from "../html.js";
import { idiomaActual, inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { exigirRol, obtenerSesion, salir } from "../session.js";

const sesion = exigirRol("admin");
inicializarLangToggle();
document.getElementById("btn-logout").addEventListener("click", salir);
agregarCambioDePassword();

const $ = (id) => document.getElementById(id);
const ROL_DE_VISTA = { docentes: "docente", padres: "padre", coordinadores: "admin" };

let datos = { coordinadores: [], docentes: [], padres: [], estudiantes: [] };
let vista = "docentes";
let temario = { vocabulario: [], gramatica: [] };

// ---------------------------------------------------------------- datos y vistas

async function cargar() {
  [datos, temario] = await Promise.all([apiFetch("/api/coordinador/usuarios"), apiFetch("/api/coordinador/temario")]);
  for (const clave of Object.keys(datos)) $(`n-${clave}`).textContent = datos[clave].filter((u) => u.activo).length;
  contarTemario();
  pintarVista();
}

function contarTemario() {
  $("n-temario").textContent = Object.values(temario).flat().filter((m) => m.activo).length;
}

document.querySelectorAll("[data-vista]").forEach((boton) => {
  boton.addEventListener("click", () => {
    vista = boton.dataset.vista;
    document.querySelectorAll("[data-vista]").forEach((b) => b.setAttribute("aria-selected", String(b === boton)));
    cerrarFormularios();
    pintarVista();
  });
});

function nombreDe(id) {
  return [...datos.docentes, ...datos.padres].find((u) => u.id_usuario === id)?.nombre || "—";
}

const botonEditar = (u) =>
  `<button type="button" class="secundario pequeno" data-accion="editar" data-id="${esc(u.id_usuario)}">✏️ ${t("coord.edit_data")}</button>`;

function botonesDeEstado(u) {
  const esYo = u.id_usuario === sesion.id_usuario;
  return esYo ? "" : `<button type="button" class="secundario pequeno" data-accion="estado" data-id="${esc(u.id_usuario)}">
    ${u.activo ? t("coord.deactivate") : t("coord.activate")}</button>`;
}

function filaAdulto(u, extra) {
  return `<tr class="${u.activo ? "" : "inactivo"}">
    <td><strong>${esc(u.nombre)}</strong>${u.activo ? "" : ` <span class="hint">(${t("coord.inactive")})</span>`}
      ${u.debe_cambiar_password ? `<div class="hint">🔑 ${t("coord.temp_password")}</div>` : ""}</td>
    <td><code>${esc(u.usuario || "—")}</code></td>
    ${extra === undefined ? "" : `<td>${extra}</td>`}
    <td class="acciones-fila">
      ${botonEditar(u)}
      <button type="button" class="secundario pequeno" data-accion="password" data-id="${esc(u.id_usuario)}">${t("coord.new_password")}</button>
      ${botonesDeEstado(u)}
    </td>
  </tr>`;
}

function pintarVista() {
  const titulos = {
    docentes: ["👩‍🏫 " + t("coord.teachers"), t("coord.add_teacher"), t("coord.teachers_hint")],
    estudiantes: ["🧒 " + t("coord.kids"), t("kids.register"), t("coord.kids_hint")],
    padres: ["👨‍👩‍👧 " + t("coord.parents"), t("coord.add_parent"), t("coord.parents_hint")],
    coordinadores: ["🧭 " + t("coord.coordinators"), t("coord.add_coordinator"), t("coord.coordinators_hint")],
    temario: ["📖 " + t("syllabus.title"), "", t("coord.syllabus_hint")],
  };
  const [titulo, crear, ayuda] = titulos[vista];
  $("vista-titulo").textContent = titulo;
  $("btn-crear").textContent = `➕ ${crear}`;
  $("btn-crear").hidden = vista === "temario";
  $("vista-ayuda").textContent = ayuda;
  if (vista === "temario") return pintarTemario();

  const lista = datos[vista];
  if (!lista.length) {
    $("vista-contenido").innerHTML = `<p class="hint vacio">${t("coord.empty")}</p>`;
    return;
  }
  const cab = (...columnas) => `<thead><tr>${columnas.map((c) => `<th>${c}</th>`).join("")}</tr></thead>`;
  let tabla;
  if (vista === "estudiantes") {
    tabla = cab(t("login.name"), t("cred.code_title"), t("coord.teacher"), t("coord.parents_of"), "") +
      `<tbody>${lista.map((n) => `<tr class="${n.activo ? "" : "inactivo"}">
        <td><strong>${esc(n.nombre)}</strong>${n.activo ? "" : ` <span class="hint">(${t("coord.inactive")})</span>`}</td>
        <td><code>${esc(n.codigo_acceso)}</code></td>
        <td><select data-accion="docente" data-id="${esc(n.id_usuario)}" aria-label="${t("coord.teacher")}">
          ${opcionesDocente(n.docente_id)}</select></td>
        <td>${n.acudientes_ids.map((id) => esc(nombreDe(id))).join(", ") || "—"}
          <button type="button" class="secundario pequeno" data-accion="padres" data-id="${esc(n.id_usuario)}">${t("coord.edit")}</button></td>
        <td class="acciones-fila">
          ${botonEditar(n)}
          <button type="button" class="secundario pequeno" data-accion="pin" data-id="${esc(n.id_usuario)}">${t("coord.new_pin")}</button>
          ${botonesDeEstado(n)}
        </td></tr>`).join("")}</tbody>`;
  } else if (vista === "docentes") {
    tabla = cab(t("login.name"), t("login.user"), t("coord.kids"), "") +
      `<tbody>${lista.map((u) => filaAdulto(u, u.estudiantes)).join("")}</tbody>`;
  } else if (vista === "padres") {
    tabla = cab(t("login.name"), t("login.user"), t("coord.children"), "") +
      `<tbody>${lista.map((u) => filaAdulto(u, u.hijos)).join("")}</tbody>`;
  } else {
    tabla = cab(t("login.name"), t("login.user"), "") + `<tbody>${lista.map((u) => filaAdulto(u)).join("")}</tbody>`;
  }
  $("vista-contenido").innerHTML = `<div class="tabla-scroll"><table class="tabla-progreso tabla-cuentas">${tabla}</table></div>`;
  // En celular cada fila se muestra como tarjeta: cada celda lleva el nombre de su columna.
  const columnas = [...$("vista-contenido").querySelectorAll("th")].map((th) => th.textContent);
  $("vista-contenido").querySelectorAll("tbody tr").forEach((fila) => {
    [...fila.children].forEach((celda, i) => { if (columnas[i]) celda.dataset.etiqueta = columnas[i]; });
  });
}

// RF08: el coordinador apaga o enciende mundos del temario para toda la institución.
function pintarTemario() {
  const secciones = [["vocabulario", "📚", "path.vocabulary"], ["gramatica", "✏️", "path.grammar"]];
  $("vista-contenido").innerHTML = secciones.map(([seccion, emoji, clave]) => `
    <section class="bloque-temario">
      <h3>${emoji} ${t(clave)}</h3>
      <ol class="lista-temario">${temario[seccion].map((m) => `
        <li class="tema${m.activo ? "" : " apagado"}">
          <input type="checkbox" id="tema-${m.id}" data-tema="${m.id}" ${m.activo ? "checked" : ""} />
          <label for="tema-${m.id}"><span aria-hidden="true">${m.emoji}</span> ${esc(m.titulo[idiomaActual()] || m.titulo.es)}
            <small>${m.lecciones} ${t("syllabus.lessons")}${m.activo ? "" : ` · ${t("coord.syllabus_off")}`}</small></label>
        </li>`).join("")}</ol>
    </section>`).join("") + `<p class="error-msg" id="error-temario" role="alert"></p>`;
}

function opcionesDocente(seleccionado) {
  const activos = datos.docentes.filter((d) => d.activo || d.id_usuario === seleccionado);
  return `<option value="">${t("coord.no_teacher")}</option>` +
    activos.map((d) => `<option value="${esc(d.id_usuario)}" ${d.id_usuario === seleccionado ? "selected" : ""}>${esc(d.nombre)}</option>`).join("");
}

function casillasPadres(contenedor, marcados = []) {
  const activos = datos.padres.filter((p) => p.activo || marcados.includes(p.id_usuario));
  contenedor.innerHTML = activos.length
    ? activos.map((p) => `<label class="casilla"><input type="checkbox" value="${esc(p.id_usuario)}" ${marcados.includes(p.id_usuario) ? "checked" : ""} />
        <span>${esc(p.nombre)} <span class="hint">(${esc(p.usuario || "")})</span></span></label>`).join("")
    : `<p class="hint">${t("coord.no_parents_yet")}</p>`;
}

const padresMarcados = (contenedor) => [...contenedor.querySelectorAll("input:checked")].map((c) => c.value);

// ---------------------------------------------------------------- crear cuentas

function cerrarFormularios() {
  $("form-adulto").classList.add("oculto");
  $("form-nino").classList.add("oculto");
}

$("btn-crear").addEventListener("click", () => {
  const formulario = vista === "estudiantes" ? $("form-nino") : $("form-adulto");
  const abrir = formulario.classList.contains("oculto");
  cerrarFormularios();
  if (!abrir) return;
  formulario.reset();
  formulario.querySelector(".error-msg").textContent = "";
  if (vista === "estudiantes") {
    $("nino-docente").innerHTML = opcionesDocente(null);
    casillasPadres($("nino-padres"));
  }
  formulario.classList.remove("oculto");
  formulario.querySelector("input").focus();
});

/** Sugiere un usuario a partir del nombre: "Marta García López" → "mgarcia". */
function sugerirUsuario(nombre) {
  const partes = nombre.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9 ]/g, "").split(/\s+/).filter(Boolean);
  if (!partes.length) return "";
  return partes.length === 1 ? partes[0] : partes[0][0] + partes[1];
}

let usuarioEditado = false;
$("adulto-usuario").addEventListener("input", () => { usuarioEditado = true; });
$("adulto-nombre").addEventListener("input", () => {
  if (!usuarioEditado) $("adulto-usuario").value = sugerirUsuario($("adulto-nombre").value).slice(0, 40);
});

async function enviando(formulario, accion) {
  const boton = formulario.querySelector("button[type=submit]");
  boton.disabled = true;
  try {
    await accion();
  } finally {
    boton.disabled = false;
  }
}

$("form-adulto").addEventListener("submit", (e) => {
  e.preventDefault();
  enviando(e.target, async () => {
    try {
      const creado = await apiFetch("/api/coordinador/adultos", {
        method: "POST",
        body: {
          nombre: $("adulto-nombre").value, rol: ROL_DE_VISTA[vista],
          usuario: $("adulto-usuario").value.trim().toLowerCase(), email: $("adulto-email").value.trim() || null,
        },
      });
      usuarioEditado = false;
      cerrarFormularios();
      await cargar();
      mostrarCredenciales(creado.nombre, creado.usuario, creado.password_temporal);
    } catch (err) {
      $("error-adulto").textContent = err.message;
    }
  });
});

$("form-nino").addEventListener("submit", (e) => {
  e.preventDefault();
  const pin = $("nino-pin").value;
  enviando(e.target, async () => {
    try {
      const creado = await apiFetch("/api/coordinador/estudiantes", {
        method: "POST",
        body: {
          nombre: $("nino-nombre").value, edad: Number($("nino-edad").value), pin,
          docente_id: $("nino-docente").value || null, acudientes_ids: padresMarcados($("nino-padres")),
          autoriza_datos_menor: $("nino-autoriza").checked,
        },
      });
      cerrarFormularios();
      await cargar();
      mostrarCodigoNino(creado.nombre, creado.codigo_acceso, pin);
    } catch (err) {
      $("error-nino").textContent = err.message;
    }
  });
});

// ---------------------------------------------------------------- diálogo

let alAceptar = null;

function abrirDialogo({ titulo, cuerpo, aceptar = t("password.save"), soloInformar = false, onAceptar }) {
  if ($("dialogo").open) $("dialogo").close();
  $("dialogo-titulo").textContent = titulo;
  $("dialogo-cuerpo").innerHTML = cuerpo;
  $("dialogo-error").textContent = "";
  $("dialogo-aceptar").textContent = soloInformar ? t("coord.done") : aceptar;
  $("dialogo-cancelar").hidden = soloInformar;
  alAceptar = onAceptar || null;
  $("dialogo").showModal();
  $("dialogo-cuerpo").querySelector("input, select")?.focus();
}

$("dialogo-cancelar").addEventListener("click", () => $("dialogo").close());
$("dialogo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!alAceptar) return $("dialogo").close();
  const boton = $("dialogo-aceptar");
  boton.disabled = true;
  try {
    await alAceptar();
  } catch (err) {
    $("dialogo-error").textContent = err.message;
  } finally {
    boton.disabled = false;
  }
});

function mostrarCredenciales(nombre, usuario, password) {
  abrirDialogo({
    titulo: `✅ ${nombre}`,
    soloInformar: true,
    cuerpo: `<p class="hint">${t("coord.give_credentials")}</p>
      <div class="credenciales">
        <div class="credencial codigo"><span class="credencial-titulo">👤 ${t("login.user")}</span><strong>${esc(usuario)}</strong></div>
        <div class="credencial pin"><span class="credencial-titulo">🔑 ${t("coord.temp_password_title")}</span><strong>${esc(password)}</strong></div>
      </div>
      <p class="hint">${t("coord.shown_once")}</p>`,
  });
}

function mostrarCodigoNino(nombre, codigo, pin) {
  abrirDialogo({
    titulo: `✅ ${nombre}`,
    soloInformar: true,
    cuerpo: `<p class="hint">${t("teacher.created_body")}</p>
      <div class="credenciales">
        <div class="credencial codigo"><span class="credencial-titulo">🪪 ${t("cred.code_title")}</span><strong>${esc(codigo)}</strong>
          <span class="credencial-ayuda">${t("cred.code_help")}</span></div>
        <div class="credencial pin"><span class="credencial-titulo">🔒 ${t("cred.pin_title")}</span><strong>${esc(pin)}</strong>
          <span class="credencial-ayuda">${t("cred.pin_help")}</span></div>
      </div>`,
  });
}

// ---------------------------------------------------------------- acciones de cada fila

const buscar = (id) => Object.values(datos).flat().find((u) => u.id_usuario === id);

$("vista-contenido").addEventListener("click", (e) => {
  const boton = e.target.closest("button[data-accion]");
  if (!boton) return;
  const u = buscar(boton.dataset.id);
  const accion = boton.dataset.accion;

  if (accion === "editar") {
    const nino = u.rol === "estudiante";
    abrirDialogo({
      titulo: `✏️ ${u.nombre}`,
      cuerpo: `<label for="editar-nombre">${t("coord.full_name")}</label>
        <input id="editar-nombre" type="text" required maxlength="120" value="${esc(u.nombre)}" />
        ${nino
          ? `<label for="editar-edad">${t("kids.age")}</label>
             <input id="editar-edad" type="number" min="3" max="15" required value="${esc(u.edad)}" />`
          : `<label for="editar-email">${t("coord.email_optional")}</label>
             <input id="editar-email" type="email" maxlength="254" value="${esc(u.email || "")}" />`}`,
      onAceptar: async () => {
        const body = { nombre: $("editar-nombre").value };
        if (nino) body.edad = Number($("editar-edad").value);
        else body.email = $("editar-email").value.trim();
        await apiFetch(`/api/coordinador/usuarios/${u.id_usuario}`, { method: "PATCH", body });
        $("dialogo").close();
        await cargar();
      },
    });
  } else if (accion === "password") {
    abrirDialogo({
      titulo: `🔑 ${u.nombre}`,
      cuerpo: `<p>${t("coord.reset_password_confirm")}</p>`,
      aceptar: t("coord.new_password"),
      onAceptar: async () => {
        const r = await apiFetch(`/api/coordinador/usuarios/${u.id_usuario}/restablecer-password`, { method: "POST" });
        await cargar();
        mostrarCredenciales(u.nombre, r.usuario, r.password_temporal);
      },
    });
  } else if (accion === "pin") {
    abrirDialogo({
      titulo: `🔒 ${u.nombre}`,
      cuerpo: `<label for="dialogo-pin">${t("teacher.pin_label")}</label>
        <input id="dialogo-pin" class="campo-pin" type="text" inputmode="numeric" pattern="[0-9]{4}" minlength="4" maxlength="4" required autocomplete="off" />`,
      onAceptar: async () => {
        const pin = $("dialogo-pin").value;
        await apiFetch(`/api/coordinador/estudiantes/${u.id_usuario}/pin`, { method: "POST", body: { pin } });
        mostrarCodigoNino(u.nombre, u.codigo_acceso, pin);
      },
    });
  } else if (accion === "padres") {
    abrirDialogo({
      titulo: `👨‍👩‍👧 ${u.nombre}`,
      cuerpo: `<fieldset class="lista-casillas"><legend>${t("coord.parents_of")}</legend><div id="dialogo-padres"></div></fieldset>`,
      onAceptar: async () => {
        await apiFetch(`/api/coordinador/estudiantes/${u.id_usuario}`, {
          method: "PATCH", body: { acudientes_ids: padresMarcados($("dialogo-padres")) },
        });
        $("dialogo").close();
        await cargar();
      },
    });
    casillasPadres($("dialogo-padres"), u.acudientes_ids);
  } else if (accion === "estado") {
    abrirDialogo({
      titulo: u.nombre,
      cuerpo: `<p>${u.activo ? t("coord.deactivate_confirm") : t("coord.activate_confirm")}</p>`,
      aceptar: u.activo ? t("coord.deactivate") : t("coord.activate"),
      onAceptar: async () => {
        await apiFetch(`/api/coordinador/usuarios/${u.id_usuario}`, { method: "PATCH", body: { activo: !u.activo } });
        $("dialogo").close();
        await cargar();
      },
    });
  }
});

// Cambiar el profesor de un niño directamente desde la tabla.
$("vista-contenido").addEventListener("change", async (e) => {
  const casilla = e.target.closest("input[data-tema]");
  if (casilla) return cambiarTema(casilla);
  const select = e.target.closest("select[data-accion=docente]");
  if (!select) return;
  select.disabled = true;
  try {
    const body = select.value ? { docente_id: select.value } : { quitar_docente: true };
    await apiFetch(`/api/coordinador/estudiantes/${select.dataset.id}`, { method: "PATCH", body });
    await cargar();
  } catch (err) {
    alert(err.message);
    await cargar();
  }
});

async function cambiarTema(casilla) {
  casilla.disabled = true;
  try {
    await apiFetch(`/api/coordinador/temario/${casilla.dataset.tema}`, { method: "PATCH", body: { activo: casilla.checked } });
    temario = await apiFetch("/api/coordinador/temario");
    contarTemario();
    pintarVista();
    $(`tema-${casilla.dataset.tema}`)?.focus();
  } catch (err) {
    pintarVista();
    $("error-temario").textContent = err.message;
  }
}

// ---------------------------------------------------------------- auditoría

$("btn-auditoria").addEventListener("click", async () => {
  $("error-auditoria").textContent = "";
  try {
    // Con fetch directo: la descarga necesita el token en el encabezado.
    const respuesta = await fetch(`${API_BASE_URL}/api/auditoria/exportar.csv`, {
      headers: { Authorization: `Bearer ${obtenerSesion()?.token}` },
      cache: "no-store",
    });
    if (!respuesta.ok) throw new Error(`Error ${respuesta.status}`);
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(await respuesta.blob());
    enlace.download = "auditoria.csv";
    enlace.click();
    URL.revokeObjectURL(enlace.href);
  } catch (err) {
    $("error-auditoria").textContent = err.message;
  }
});

if (sesion) cargar();
