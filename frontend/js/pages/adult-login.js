import { apiFetch, despertarServidor } from "../api.js";
import { inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { guardarSesion, obtenerSesion } from "../session.js";

// Mientras la persona escribe, el servidor va despertando (plan gratis de Render).
despertarServidor();
inicializarLangToggle();

const DESTINO_POR_ROL = { docente: "teacher.html", padre: "parent.html", admin: "coordinador.html" };
const $ = (id) => document.getElementById(id);

// Un adulto con sesión abierta va directo a su panel en vez de ver el login otra vez.
const sesionActual = obtenerSesion();
if (sesionActual && DESTINO_POR_ROL[sesionActual.rol]) window.location.replace(DESTINO_POR_ROL[sesionActual.rol]);

function entrar(sesion) {
  guardarSesion({ token: sesion.token, id_usuario: sesion.id_usuario, rol: sesion.rol, nombre: sesion.nombre });
  window.location.replace(DESTINO_POR_ROL[sesion.rol] || "index.html");
}

/** Deshabilita el botón mientras se espera la respuesta (evita envíos dobles). */
async function conBotonOcupado(formulario, accion) {
  const boton = formulario.querySelector("button[type=submit]");
  boton.disabled = true;
  try {
    await accion();
  } finally {
    boton.disabled = false;
  }
}

// Primer ingreso (o contraseña restablecida por el coordinador): antes de entrar al panel
// cambia la contraseña temporal y acepta los términos.
let pendiente = null; // { sesion, temporal }

$("form-login").addEventListener("submit", (e) => {
  e.preventDefault();
  $("error-login").textContent = "";
  conBotonOcupado(e.target, async () => {
    try {
      const password = $("password").value;
      const sesion = await apiFetch("/api/usuarios/login", {
        method: "POST", body: { usuario: $("usuario").value, password }, esLogin: true,
      });
      if (!sesion.debe_cambiar_password) return entrar(sesion);
      pendiente = { sesion, temporal: password };
      $("card-login").classList.add("oculto");
      $("card-primer-ingreso").classList.remove("oculto");
      $("primera-nueva").focus();
    } catch (err) {
      $("error-login").textContent = err.message;
    }
  });
});

$("form-primer-ingreso").addEventListener("submit", (e) => {
  e.preventDefault();
  $("error-primer-ingreso").textContent = "";
  const nueva = $("primera-nueva").value;
  if (nueva !== $("primera-repetir").value) {
    $("error-primer-ingreso").textContent = t("password.mismatch");
    return;
  }
  conBotonOcupado(e.target, async () => {
    try {
      await apiFetch("/api/usuarios/cambiar-password", {
        method: "POST",
        tokenOverride: pendiente.sesion.token,
        body: { actual: pendiente.temporal, nueva, acepta_terminos: $("primera-terminos").checked },
      });
      entrar(pendiente.sesion);
    } catch (err) {
      $("error-primer-ingreso").textContent = err.message;
    }
  });
});
