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
