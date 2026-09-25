// Guarda la sesión (token + rol + datos básicos) en localStorage.
// Es deliberadamente simple: el token expira solo (RNF-SEG-04, ver backend
// JWT_PIN_EXP_MINUTOS) y la API rechaza cualquier token vencido o inválido.

const CLAVE_SESION = "pik_sesion";

export function guardarSesion({ token, id_usuario, rol, nombre, codigo_acceso }) {
  localStorage.setItem(CLAVE_SESION, JSON.stringify({ token, id_usuario, rol, nombre, codigo_acceso }));
}

export function obtenerSesion() {
  const crudo = localStorage.getItem(CLAVE_SESION);
  if (!crudo) return null;
  try {
    return JSON.parse(crudo);
  } catch {
    return null;
  }
}

export function cerrarSesion() {
  localStorage.removeItem(CLAVE_SESION);
}

/** Redirige a index.html si no hay sesión o el rol no es uno de los permitidos. */
export function exigirRol(...rolesPermitidos) {
  const sesion = obtenerSesion();
  if (!sesion || !rolesPermitidos.includes(sesion.rol)) {
    window.location.href = "index.html";
    return null;
  }
  return sesion;
}
