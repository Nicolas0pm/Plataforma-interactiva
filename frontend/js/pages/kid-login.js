import { apiFetch } from "../api.js";
import { inicializarLangToggle, t } from "../i18n.js";
import { guardarSesion } from "../session.js";

inicializarLangToggle();

const PIN_LARGO = 4;
let pin = "";

const puntos = document.getElementById("pin-dots");
const errorEl = document.getElementById("error");
const codigoInput = document.getElementById("codigo");

function pintarPin() {
  puntos.innerHTML = "";
  for (let i = 0; i < PIN_LARGO; i++) {
    const span = document.createElement("span");
    if (i < pin.length) span.classList.add("llena");
    puntos.appendChild(span);
  }
}
pintarPin();

document.getElementById("pin-pad").addEventListener("click", async (evento) => {
  const boton = evento.target.closest("button");
  if (!boton) return;

  if (boton.id === "btn-borrar") {
    pin = "";
    pintarPin();
    errorEl.textContent = "";
    return;
  }

  if (boton.dataset.num === undefined || pin.length >= PIN_LARGO) return;
  pin += boton.dataset.num;
  pintarPin();

  if (pin.length === PIN_LARGO) {
    await intentarLogin();
  }
});

async function intentarLogin() {
  const codigo = codigoInput.value.trim().toUpperCase();
  if (!codigo) {
    errorEl.textContent = t("kidlogin.need_code");
    pin = "";
    pintarPin();
    return;
  }

  try {
    const sesion = await apiFetch("/api/usuarios/login-pin", {
      method: "POST",
      body: { codigo, pin },
      esLogin: true,
    });
    guardarSesion(sesion);
    window.location.href = "kid-dashboard.html";
  } catch (err) {
    errorEl.textContent = err.message.startsWith("No se pudo conectar") ? t("kidlogin.no_server") : t("kidlogin.wrong");
    pin = "";
    pintarPin();
  }
}
