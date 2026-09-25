import {
  auth,
  createUserWithEmailAndPassword,
  firebaseConfigurado,
  signInWithEmailAndPassword,
} from "../firebase-config.js";
import { apiFetch } from "../api.js";
import { inicializarLangToggle, t } from "../i18n.js";
import { guardarSesion } from "../session.js";

inicializarLangToggle();

const params = new URLSearchParams(window.location.search);
const rolElegido = params.get("rol") === "padre" ? "padre" : "docente";

const DESTINO_POR_ROL = { docente: "teacher.html", padre: "parent.html", admin: "teacher.html" };

if (!firebaseConfigurado) {
  document.getElementById("hint-firebase").textContent =
    "Este proyecto no tiene Firebase configurado todavía (frontend/js/firebase-config.js). " +
    "Usa el modo de prueba de abajo mientras tanto.";
  document.getElementById("form-login").querySelector("button").disabled = true;
  document.getElementById("form-registro").querySelector("button").disabled = true;
}

function irADestino(rol) {
  window.location.href = DESTINO_POR_ROL[rol] || "index.html";
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
    guardarSesion({ token: idToken, id_usuario: perfil.id_usuario, rol: perfil.rol, nombre: perfil.nombre });
    irADestino(perfil.rol);
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
    guardarSesion({ token: idToken, id_usuario: perfil.id_usuario, rol: perfil.rol, nombre: perfil.nombre });
    irADestino(perfil.rol);
  } catch (err) {
    errorEl.textContent = err.message;
  }
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
    guardarSesion(sesion);
    irADestino(sesion.rol);
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
