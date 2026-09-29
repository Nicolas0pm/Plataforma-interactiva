// Escapa texto antes de meterlo en un template con innerHTML.
// Todo dato que venga de la API (nombres, comentarios, preguntas) pasa por aquí: así un
// "nombre" como <img onerror=...> se muestra como texto y nunca se ejecuta (XSS).
export function esc(valor) {
  return String(valor ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// Convierte **negrita** y *cursiva* (solo eso) de textos propios, ya escapados.
export function miniMarkdown(texto) {
  return esc(texto)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

export function porcentaje(valor) {
  return valor === null || valor === undefined ? "—" : `${Math.round(valor * 100)} %`;
}

// Fechas de la API (UTC) mostradas en la hora local del navegador.
function locale(idioma) {
  return idioma === "en" ? "en-US" : "es-CO";
}

export function hora(fechaIso, idioma = "es") {
  return new Date(fechaIso).toLocaleTimeString(locale(idioma), { hour: "numeric", minute: "2-digit" });
}

/** "hoy 3:45 p. m." · "ayer 9:10 a. m." · "12 sep, 4:20 p. m." */
export function cuando(fechaIso, idioma = "es") {
  if (!fechaIso) return "—";
  const fecha = new Date(fechaIso);
  const hoy = new Date();
  const ayer = new Date(hoy);
  ayer.setDate(hoy.getDate() - 1);
  const mismoDia = (a, b) => a.toDateString() === b.toDateString();
  const h = hora(fechaIso, idioma);
  if (mismoDia(fecha, hoy)) return `${idioma === "en" ? "today" : "hoy"} ${h}`;
  if (mismoDia(fecha, ayer)) return `${idioma === "en" ? "yesterday" : "ayer"} ${h}`;
  return `${fecha.toLocaleDateString(locale(idioma), { day: "numeric", month: "short" })}, ${h}`;
}
