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
  const valida = () => {
    const actual = obtenerSesion();
    return actual && rolesPermitidos.includes(actual.rol) ? actual : null;
  };
  // Al volver con "atrás", el navegador puede mostrar esta página desde su caché (bfcache)
  // sin volver a ejecutar el script: si ya no hay sesión se va al inicio, y si la hay se
  // recarga para no mostrar datos viejos (p. ej. el progreso antes de terminar una lección).
  window.addEventListener("pageshow", (evento) => {
    if (!evento.persisted) return;
    if (!valida()) window.location.replace("index.html");
    else window.location.reload();
  });
  const sesion = valida();
  if (!sesion) {
    window.location.replace("index.html");
    return null;
  }
  return sesion;
}

/** Cierra la sesión y vuelve al inicio sin dejar el panel en el historial. */
export function salir() {
  cerrarSesion();
  window.location.replace("index.html");
}
