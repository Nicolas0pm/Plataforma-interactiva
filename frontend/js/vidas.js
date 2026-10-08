// Vidas ❤️ (ver backend lecciones_service.estado_vidas): se guardan entre lecciones y se
// recarga una cada `minutos_por_vida` minutos.

export function corazones(actuales, maximo) {
  return "❤️".repeat(actuales) + "🤍".repeat(Math.max(0, maximo - actuales));
}

/** Minutos que faltan para una fecha ISO (mínimo 1). */
export function minutosHasta(fechaIso) {
  return Math.max(1, Math.ceil((new Date(fechaIso) - Date.now()) / 60000));
}

/** Avanza el estado de las vidas si ya pasó la hora de la próxima (sin volver a pedirlo al servidor). */
export function actualizarVidas(vidas) {
  const v = { ...vidas };
  while (v.proxima_vida && new Date(v.proxima_vida) <= Date.now() && v.actuales < v.maximo) {
    v.actuales += 1;
    v.proxima_vida =
      v.actuales < v.maximo ? new Date(new Date(v.proxima_vida).getTime() + v.minutos_por_vida * 60000).toISOString() : null;
  }
  return v;
}
