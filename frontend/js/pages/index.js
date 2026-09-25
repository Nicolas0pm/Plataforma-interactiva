import { inicializarLangToggle } from "../i18n.js";
import { obtenerSesion } from "../session.js";

inicializarLangToggle();

const DESTINO_POR_ROL = {
  estudiante: "kid-dashboard.html",
  docente: "teacher.html",
  padre: "parent.html",
  admin: "teacher.html",
};

const sesion = obtenerSesion();
if (sesion && DESTINO_POR_ROL[sesion.rol]) {
  window.location.href = DESTINO_POR_ROL[sesion.rol];
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
