// Sonidos de la lección (acierto, error, lección ganada o perdida).
// Se generan con Web Audio en el momento: no hay archivos de audio que descargar ni
// licencias que cuidar. El niño puede silenciarlos con el botón 🔊 (queda guardado).

const CLAVE = "pik_sonido";
let contexto = null;

export function sonidoActivo() {
  try {
    return localStorage.getItem(CLAVE) !== "no";
  } catch {
    return true;
  }
}

export function alternarSonido() {
  const activo = !sonidoActivo();
  try {
    localStorage.setItem(CLAVE, activo ? "si" : "no");
  } catch {
    /* sin almacenamiento: vale solo para esta visita */
  }
  return activo;
}

function audio() {
  if (!sonidoActivo()) return null;
  const Contexto = window.AudioContext || window.webkitAudioContext;
  if (!Contexto) return null;
  contexto ??= new Contexto();
  // Los navegadores arrancan el audio "suspendido" hasta que la persona toca algo.
  if (contexto.state === "suspended") contexto.resume();
  return contexto;
}

/** Una nota: frecuencia (Hz), cuándo empieza y cuánto dura (s), con volumen suave. */
function nota(ctx, frecuencia, inicio, duracion, { tipo = "sine", volumen = 0.18, hasta } = {}) {
  const osc = ctx.createOscillator();
  const gan = ctx.createGain();
  const t0 = ctx.currentTime + inicio;
  osc.type = tipo;
  osc.frequency.setValueAtTime(frecuencia, t0);
  if (hasta) osc.frequency.exponentialRampToValueAtTime(hasta, t0 + duracion);
  // Entrada y salida rápidas para que no "chasquee".
  gan.gain.setValueAtTime(0.0001, t0);
  gan.gain.exponentialRampToValueAtTime(volumen, t0 + 0.02);
  gan.gain.exponentialRampToValueAtTime(0.0001, t0 + duracion);
  osc.connect(gan).connect(ctx.destination);
  osc.start(t0);
  osc.stop(t0 + duracion + 0.05);
}

const SONIDOS = {
  // "¡Ding-ding!": dos notas que suben.
  acierto: (ctx) => {
    nota(ctx, 880, 0, 0.15, { tipo: "triangle" });
    nota(ctx, 1318.5, 0.1, 0.3, { tipo: "triangle" });
  },
  // "Bwomp": un tono grave que baja (avisa sin asustar).
  error: (ctx) => {
    nota(ctx, 220, 0, 0.35, { tipo: "square", volumen: 0.07, hasta: 140 });
    nota(ctx, 110, 0, 0.35, { tipo: "sine", volumen: 0.15, hasta: 80 });
  },
  // Fanfarria corta: do-mi-sol-do.
  ganar: (ctx) => {
    [523.25, 659.25, 783.99].forEach((f, i) => nota(ctx, f, i * 0.12, 0.2, { tipo: "triangle" }));
    nota(ctx, 1046.5, 0.36, 0.55, { tipo: "triangle", volumen: 0.2 });
  },
  // Tres notas que bajan.
  perder: (ctx) => {
    [392, 349.23, 293.66].forEach((f, i) => nota(ctx, f, i * 0.22, 0.3, { tipo: "triangle", volumen: 0.14 }));
  },
};

/** sonar("acierto" | "error" | "ganar" | "perder"). Nunca lanza errores. */
export function sonar(nombre) {
  try {
    const ctx = audio();
    if (ctx) SONIDOS[nombre]?.(ctx);
  } catch {
    /* sin audio no pasa nada: la lección sigue igual */
  }
}
