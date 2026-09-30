import { apiFetch } from "../api.js";
import { inicializarLangToggle, t } from "../i18n.js";
import "../nav.js";
import { despertarServidor } from "../api.js";

// Mientras la persona elige o escribe, el servidor va despertando (plan gratis de Render).
despertarServidor();
import { guardarSesion, obtenerSesion } from "../session.js";

// Si el niño ya tiene sesión abierta, no tiene sentido volver a pedirle el PIN.
if (obtenerSesion()?.rol === "estudiante") window.location.replace("kid-dashboard.html");

inicializarLangToggle();

// Dos pasos separados para que el código (se escribe) y el PIN (secreto, números)
// no se confundan: primero el código, luego el teclado del PIN.
const LARGO_CODIGO = 6;
const PIN_LARGO = 4;
let codigo = "";
let pin = "";

const pasoCodigo = document.getElementById("paso-codigo");
const pasoPin = document.getElementById("paso-pin");
const codigoInput = document.getElementById("codigo");
const puntos = document.getElementById("pin-dots");
const errorEl = document.getElementById("error");

function normalizar(texto) {
  return texto.trim().toUpperCase().replace(/[\s-]/g, "");
}

function mostrarPaso(paso) {
  pasoCodigo.hidden = paso !== "codigo";
  pasoPin.hidden = paso !== "pin";
  if (paso === "codigo") {
    codigoInput.focus();
  } else {
    document.getElementById("codigo-elegido").textContent = codigo;
    pin = "";
    pintarPin();
  }
}

const botonEntrar = document.getElementById("btn-entrar");

function pintarPin() {
  // El PIN no se envía solo al marcar el 4.º número: el niño confirma con "Entrar".
  botonEntrar.disabled = pin.length !== PIN_LARGO;
  puntos.innerHTML = "";
  puntos.setAttribute("aria-label", `${pin.length} / ${PIN_LARGO}`);
  for (let i = 0; i < PIN_LARGO; i++) {
    const span = document.createElement("span");
    if (i < pin.length) span.classList.add("llena");
    puntos.appendChild(span);
  }
}

pasoCodigo.addEventListener("submit", (evento) => {
  evento.preventDefault();
  errorEl.textContent = "";
  const escrito = normalizar(codigoInput.value);
  if (escrito.length !== LARGO_CODIGO) {
    errorEl.textContent = t("kidlogin.code_invalid");
    return;
  }
  codigo = escrito;
  mostrarPaso("pin");
});

document.getElementById("btn-cambiar-codigo").addEventListener("click", () => {
  errorEl.textContent = "";
  mostrarPaso("codigo");
});

function marcarDigito(digito) {
  if (pin.length >= PIN_LARGO) return;
  pin += digito;
  errorEl.textContent = "";
  pintarPin();
}

botonEntrar.addEventListener("click", async () => {
  if (pin.length !== PIN_LARGO) return;
  botonEntrar.disabled = true;
  await intentarLogin();
});

document.getElementById("pin-pad").addEventListener("click", async (evento) => {
  const boton = evento.target.closest("button");
  if (!boton) return;
  if (boton.id === "btn-borrar") {
    pin = "";
    pintarPin();
    errorEl.textContent = "";
    return;
  }
  if (boton.dataset.num !== undefined) marcarDigito(boton.dataset.num);
});

// En computador, el PIN también se puede marcar con el teclado.
document.addEventListener("keydown", async (evento) => {
  if (pasoPin.hidden) return;
  if (/^[0-9]$/.test(evento.key)) marcarDigito(evento.key);
  else if (evento.key === "Enter" && pin.length === PIN_LARGO) botonEntrar.click();
  else if (evento.key === "Backspace") {
    pin = pin.slice(0, -1);
    pintarPin();
  }
});

async function intentarLogin() {
  try {
    const sesion = await apiFetch("/api/usuarios/login-pin", {
      method: "POST",
      body: { codigo, pin },
      esLogin: true,
    });
    guardarSesion(sesion);
    window.location.replace("kid-dashboard.html");
  } catch (err) {
    errorEl.textContent = err.message.startsWith("No se pudo conectar")
      ? t("kidlogin.no_server")
      : err.message.startsWith("Demasiados")
        ? t("kidlogin.locked")
        : t("kidlogin.wrong");
    pin = "";
    pintarPin();
  }
}

pintarPin();
mostrarPaso("codigo");
