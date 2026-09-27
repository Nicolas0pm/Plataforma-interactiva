import { inicializarLangToggle } from "../i18n.js";
import "../nav.js";
import { cerrarSesion, obtenerSesion } from "../session.js";

inicializarLangToggle();

const DESTINO_POR_ROL = {
  estudiante: "kid-dashboard.html",
  docente: "teacher.html",
  padre: "parent.html",
  admin: "teacher.html",
};

// Con sesión abierta no se redirige automáticamente (eso atrapaba el botón "atrás"
// del navegador en un bucle): se ofrece continuar o cerrar sesión.
const sesion = obtenerSesion();
if (sesion && DESTINO_POR_ROL[sesion.rol]) {
  document.getElementById("sesion-nombre").textContent = sesion.nombre || "";
  document.getElementById("sesion-activa").classList.remove("oculto");
  document.getElementById("btn-continuar").addEventListener("click", () => {
    window.location.href = DESTINO_POR_ROL[sesion.rol];
  });
  document.getElementById("btn-no-soy-yo").addEventListener("click", () => {
    cerrarSesion();
    document.getElementById("sesion-activa").classList.add("oculto");
  });
}

document.querySelectorAll(".role-card").forEach((boton) => {
  boton.addEventListener("click", () => {
    const rol = boton.dataset.rol;
    if (rol === "estudiante") {
      window.location.href = "kid-login.html";
    } else {
      window.location.href = `adult-login.html?rol=${rol}`;
    }
  });
});
