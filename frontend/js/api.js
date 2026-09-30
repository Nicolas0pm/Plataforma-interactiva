import { cerrarSesion, obtenerSesion } from "./session.js";

import { API_BASE_URL } from "./config.js";

export { API_BASE_URL };

// El plan gratis de Render "duerme" el servidor tras 15 min sin uso y la primera respuesta
// tarda hasta ~50 s. Si una petición se demora, se avisa en vez de dejar la pantalla quieta.
const ESPERA_AVISO_MS = 3000;
let pendientesLentas = 0;

function avisoLento(mostrar) {
  let aviso = document.getElementById("aviso-servidor");
  if (!aviso && mostrar) {
    aviso = document.createElement("div");
    aviso.id = "aviso-servidor";
    aviso.setAttribute("role", "status");
    aviso.innerHTML = `<span class="girando">⏳</span> <span>${
      (localStorage.getItem("pik_idioma") || "es") === "en"
        ? "Waking up the server… this can take a few seconds."
        : "Despertando el servidor… puede tardar unos segundos."
    }</span>`;
    document.body.appendChild(aviso);
  }
  if (aviso) aviso.hidden = !mostrar;
}

/** Pide algo liviano al servidor para que vaya despertando mientras el usuario escribe. */
export function despertarServidor() {
  fetch(`${API_BASE_URL}/`, { cache: "no-store" }).catch(() => {});
}

/**
 * Wrapper de fetch: agrega el token de sesión (si existe), serializa JSON,
 * y ante un 401 cierra la sesión y vuelve a la pantalla de selección de usuario
 * (RNF-SEG-04: la sesión vencida no debe dejar a nadie "atascado").
 */
export async function apiFetch(ruta, { method = "GET", body, headers = {}, tokenOverride, esLogin = false } = {}) {
  const sesion = obtenerSesion();
  const token = tokenOverride ?? sesion?.token;
  const encabezados = { ...headers };
  if (body !== undefined) encabezados["Content-Type"] = "application/json";
  if (token) encabezados["Authorization"] = `Bearer ${token}`;

  let respuesta;
  let esLenta = false;
  const temporizador = setTimeout(() => {
    esLenta = true;
    pendientesLentas += 1;
    avisoLento(true);
  }, ESPERA_AVISO_MS);
  try {
    respuesta = await fetch(`${API_BASE_URL}${ruta}`, {
      // Datos personales y de progreso: nunca desde la caché del navegador (al volver
      // con "atrás" mostraría el progreso viejo).
      cache: "no-store",
      method,
      headers: encabezados,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new Error("No se pudo conectar con el servidor. Revisa tu conexión.");
  } finally {
    clearTimeout(temporizador);
    if (esLenta) {
      pendientesLentas -= 1;
      if (pendientesLentas === 0) avisoLento(false);
    }
  }

  // En un login, un 401 significa "credenciales incorrectas", no "sesión vencida":
  // se deja pasar como error normal para mostrarlo en la misma pantalla.
  if (respuesta.status === 401 && !esLogin) {
    cerrarSesion();
    window.location.replace("index.html");
    throw new Error("Sesión inválida o vencida");
  }

  if (!respuesta.ok) {
    let detalle = `Error ${respuesta.status}`;
    try {
      const cuerpo = await respuesta.json();
      if (Array.isArray(cuerpo.detail)) {
        detalle = cuerpo.detail.map((e) => String(e.msg || e).replace(/^Value error, /, "")).join(" · ");
      } else {
        detalle = cuerpo.detail || detalle;
      }
    } catch {
      /* respuesta sin cuerpo JSON */
    }
    throw new Error(detalle);
  }

  if (respuesta.status === 204) return null;
  const tipo = respuesta.headers.get("content-type") || "";
  return tipo.includes("application/json") ? respuesta.json() : respuesta.text();
}
