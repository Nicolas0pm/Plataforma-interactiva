import {
  auth,
  createUserWithEmailAndPassword,
  firebaseConfigurado,
  signInWithEmailAndPassword,
  signOut,
} from "../firebase-config.js";
import { apiFetch } from "../api.js";
import { inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { despertarServidor } from "../api.js";

// Mientras la persona elige o escribe, el servidor va despertando (plan gratis de Render).
despertarServidor();
import { guardarSesion, obtenerSesion } from "../session.js";

inicializarLangToggle();

const params = new URLSearchParams(window.location.search);
const rolElegido = params.get("rol") === "padre" ? "padre" : "docente";

const DESTINO_POR_ROL = { docente: "teacher.html", padre: "parent.html", admin: "teacher.html" };

// Un adulto con sesión abierta va directo a su panel en vez de ver el login otra vez.
const sesionActual = obtenerSesion();
if (sesionActual && DESTINO_POR_ROL[sesionActual.rol]) window.location.replace(DESTINO_POR_ROL[sesionActual.rol]);

if (!firebaseConfigurado) {
  document.getElementById("hint-firebase").textContent =
    "Este proyecto no tiene Firebase configurado todavía (frontend/js/firebase-config.js). " +
    "Usa el modo de prueba de abajo mientras tanto.";
  document.getElementById("form-login").querySelector("button").disabled = true;
  document.getElementById("form-registro").querySelector("button").disabled = true;
}

function irADestino(rol) {
  window.location.replace(DESTINO_POR_ROL[rol] || "index.html");
}

document.getElementById("form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("error-login");
  errorEl.textContent = "";
  try {
    const cred = await signInWithEmailAndPassword(
      auth,
      document.getElementById("email").value,
      document.getElementById("password").value
    );
    const idToken = await cred.user.getIdToken();
    const perfil = await apiFetch("/api/usuarios/sesion", { tokenOverride: idToken });
    entrar(idToken, perfil);
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("form-registro").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("error-registro");
  errorEl.textContent = "";
  try {
    const nombre = document.getElementById("reg-nombre").value;
    const email = document.getElementById("reg-email").value;
    const cred = await createUserWithEmailAndPassword(
      auth, email, document.getElementById("reg-password").value
    );
    const idToken = await cred.user.getIdToken();
    const perfil = await apiFetch("/api/usuarios", {
      method: "POST",
      tokenOverride: idToken,
      body: {
        nombre, edad: 99, rol: rolElegido, acudientes_ids: [], docente_id: null, email,
        acepta_terminos: document.getElementById("reg-terminos").checked,
      },
    });
    entrar(idToken, perfil);
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

// ---------- Confirmar el correo con el código de 6 dígitos ----------
// Mientras no lo confirme, la API no deja usar el panel: se muestra esta tarjeta en vez
// de entrar. La sesión se guarda solo cuando el correo queda confirmado.
let pendiente = null; // { idToken, perfil }

function entrar(idToken, perfil) {
  if (perfil.email_verificado === false) {
    mostrarVerificacion(idToken, perfil);
    return;
  }
  guardarSesion({ token: idToken, id_usuario: perfil.id_usuario, rol: perfil.rol, nombre: perfil.nombre });
  irADestino(perfil.rol);
}

function mostrarVerificacion(idToken, perfil) {
  pendiente = { idToken, perfil };
  for (const id of ["card-login", "card-registro", "card-dev"]) document.getElementById(id)?.classList.add("oculto");
  document.getElementById("card-verificar").classList.remove("oculto");
  document.getElementById("verificar-texto").textContent = t("verify.sent_to").replace("{email}", perfil.email || "");
  document.getElementById("codigo-verificacion").focus();
  esperarParaReenviar(60);
}

document.getElementById("form-verificar").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("error-verificar");
  errorEl.textContent = "";
  const campo = document.getElementById("codigo-verificacion");
  try {
    await apiFetch("/api/usuarios/verificacion/confirmar", {
      method: "POST",
      tokenOverride: pendiente.idToken,
      body: { codigo: campo.value.trim() },
    });
    entrar(pendiente.idToken, { ...pendiente.perfil, email_verificado: true });
  } catch (err) {
    errorEl.textContent = err.message;
    campo.select();
  }
});

// Solo dígitos, y al completar los 6 se envía solo.
document.getElementById("codigo-verificacion").addEventListener("input", (e) => {
  e.target.value = e.target.value.replace(/\D/g, "").slice(0, 6);
  if (e.target.value.length === 6) document.getElementById("form-verificar").requestSubmit();
});

let temporizador = null;
function esperarParaReenviar(segundos) {
  const boton = document.getElementById("btn-reenviar");
  clearInterval(temporizador);
  const pintar = () => {
    boton.disabled = segundos > 0;
    boton.textContent = segundos > 0 ? `${t("verify.resend")} (${segundos} s)` : t("verify.resend");
  };
  pintar();
  temporizador = setInterval(() => {
    segundos -= 1;
    pintar();
    if (segundos <= 0) clearInterval(temporizador);
  }, 1000);
}

document.getElementById("btn-reenviar").addEventListener("click", async () => {
  const aviso = document.getElementById("verificar-aviso");
  const errorEl = document.getElementById("error-verificar");
  aviso.textContent = "";
  errorEl.textContent = "";
  try {
    await apiFetch("/api/usuarios/verificacion/reenviar", { method: "POST", tokenOverride: pendiente.idToken });
    aviso.textContent = t("verify.resent");
    esperarParaReenviar(60);
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("btn-otra-cuenta").addEventListener("click", async () => {
  if (firebaseConfigurado) await signOut(auth).catch(() => {});
  window.location.reload();
});

document.getElementById("form-dev-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("error-dev-login");
  errorEl.textContent = "";
  try {
    const sesion = await apiFetch("/api/usuarios/login-dev", {
      method: "POST",
      body: { id_usuario: document.getElementById("dev-id").value.trim(), rol: rolElegido },
    });
    // El modo de prueba también respeta la confirmación del correo.
    const perfil = await apiFetch("/api/usuarios/sesion", { tokenOverride: sesion.token });
    entrar(sesion.token, perfil);
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
