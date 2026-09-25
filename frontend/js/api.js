import { cerrarSesion, obtenerSesion } from "./session.js";

// Cambia esto por la URL real de la API cuando la despliegues (Cloud Run, Render, etc.)
export const API_BASE_URL = window.PIK_API_BASE_URL || "http://localhost:8000";

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
  try {
    respuesta = await fetch(`${API_BASE_URL}${ruta}`, {
      method,
      headers: encabezados,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new Error("No se pudo conectar con el servidor. Revisa tu conexión.");
  }

  // En un login, un 401 significa "credenciales incorrectas", no "sesión vencida":
  // se deja pasar como error normal para mostrarlo en la misma pantalla.
  if (respuesta.status === 401 && !esLogin) {
    cerrarSesion();
    window.location.href = "index.html";
    throw new Error("Sesión inválida o vencida");
  }

  if (!respuesta.ok) {
    let detalle = `Error ${respuesta.status}`;
    try {
      const cuerpo = await respuesta.json();
      detalle = cuerpo.detail || detalle;
    } catch {
      /* respuesta sin cuerpo JSON */
    }
    throw new Error(detalle);
  }

  if (respuesta.status === 204) return null;
  const tipo = respuesta.headers.get("content-type") || "";
  return tipo.includes("application/json") ? respuesta.json() : respuesta.text();
}
