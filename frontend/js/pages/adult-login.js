import { apiFetch, despertarServidor } from "../api.js";
import { inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { guardarSesion, obtenerSesion } from "../session.js";

// Mientras la persona elige o escribe, el servidor va despertando (plan gratis de Render).
despertarServidor();
inicializarLangToggle();

const params = new URLSearchParams(window.location.search);
const rolElegido = params.get("rol") === "padre" ? "padre" : "docente";

const DESTINO_POR_ROL = { docente: "teacher.html", padre: "parent.html", admin: "teacher.html" };

// Un adulto con sesión abierta va directo a su panel en vez de ver el login otra vez.
const sesionActual = obtenerSesion();
if (sesionActual && DESTINO_POR_ROL[sesionActual.rol]) window.location.replace(DESTINO_POR_ROL[sesionActual.rol]);

function entrar(sesion) {
  guardarSesion({ token: sesion.token, id_usuario: sesion.id_usuario, rol: sesion.rol, nombre: sesion.nombre });
  window.location.replace(DESTINO_POR_ROL[sesion.rol] || "index.html");
}

/** Deshabilita el botón mientras se espera la respuesta (evita registros dobles). */
async function conBotonOcupado(formulario, accion) {
  const boton = formulario.querySelector("button[type=submit]");
  boton.disabled = true;
  try {
    await accion();
  } finally {
    boton.disabled = false;
  }
}

function iniciarSesion(email, password) {
  return apiFetch("/api/usuarios/login", { method: "POST", body: { email, password }, esLogin: true });
}

document.getElementById("form-login").addEventListener("submit", (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("error-login");
  errorEl.textContent = "";
  conBotonOcupado(e.target, async () => {
    try {
      entrar(await iniciarSesion(document.getElementById("email").value, document.getElementById("password").value));
    } catch (err) {
      errorEl.textContent = err.message;
    }
  });
});

document.getElementById("form-registro").addEventListener("submit", (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("error-registro");
  errorEl.textContent = "";
  conBotonOcupado(e.target, async () => {
    try {
      const email = document.getElementById("reg-email").value;
      const password = document.getElementById("reg-password").value;
      await apiFetch("/api/usuarios", {
        method: "POST",
        body: {
          nombre: document.getElementById("reg-nombre").value, edad: 99, rol: rolElegido,
          acudientes_ids: [], docente_id: null, email, password,
          acepta_terminos: document.getElementById("reg-terminos").checked,
        },
      });
      entrar(await iniciarSesion(email, password));
    } catch (err) {
      errorEl.textContent = err.message;
    }
  });
});

document.getElementById("form-dev-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("error-dev-login");
  errorEl.textContent = "";
  try {
    entrar(await apiFetch("/api/usuarios/login-dev", {
      method: "POST",
      body: { id_usuario: document.getElementById("dev-id").value.trim(), rol: rolElegido },
      esLogin: true,
    }));
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("form-dev-registro").addEventListener("submit", async (e) => {
  e.preventDefault();
  const resultadoEl = document.getElementById("dev-registro-resultado");
  resultadoEl.textContent = "";
  try {
    const nombre = document.getElementById("dev-reg-nombre").value;
    const perfil = await apiFetch("/api/usuarios", {
      method: "POST",
      // Modo de prueba (base de datos en memoria): se asume la aceptación para agilizar.
      body: { nombre, edad: 99, rol: rolElegido, acudientes_ids: [], docente_id: null, email: null, acepta_terminos: true },
    });
    resultadoEl.textContent = `${t("login.dev_created")} ${perfil.id_usuario}`;
    document.getElementById("dev-id").value = perfil.id_usuario;
  } catch (err) {
    resultadoEl.textContent = err.message;
  }
});
