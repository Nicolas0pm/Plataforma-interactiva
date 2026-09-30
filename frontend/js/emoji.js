import { esc } from "./html.js";

// Ilustraciones 3D de Microsoft Fluent Emoji (licencia MIT, ver img/emoji/LICENSE) para los
// emojis del temario. Cada archivo se llama como los códigos Unicode del emoji sin el
// selector de variación (🐶 → 1f436.webp, 👩‍🏫 → 1f469-200d-1f3eb.webp). Un emoji que no
// esté en la lista (p. ej. uno que escribió el docente) se sigue mostrando como texto.
const DISPONIBLES = new Set([
  "1f170", "1f308", "1f30a", "1f30e", "1f319", "1f327", "1f333", "1f338", "1f33d", "1f343", "1f347", "1f34c", "1f34e", "1f353", "1f355", "1f357", "1f35a", "1f35e", "1f366", "1f36a", "1f370", "1f381", "1f392", "1f3a8", "1f3b3", "1f3be", "1f3c0", "1f3c3", "1f3c4", "1f3c8", "1f3ca", "1f3cd", "1f3d0", "1f3d3", "1f3e0", "1f411", "1f418", "1f41f", "1f426", "1f42e", "1f42f", "1f430", "1f431", "1f434", "1f435", "1f436", "1f437", "1f438", "1f43b", "1f43e", "1f440", "1f441", "1f442", "1f443", "1f444", "1f445", "1f452", "1f453", "1f454", "1f455", "1f456", "1f457", "1f45f", "1f469-200d-1f3eb", "1f46f", "1f4a1", "1f4a8", "1f4aa", "1f4bb", "1f4cf", "1f4d3", "1f4d6", "1f4da", "1f4e6", "1f4f1", "1f4fa", "1f501", "1f511", "1f51f", "1f522", "1f525", "1f534", "1f535", "1f58a", "1f58c", "1f58d", "1f590", "1f64b", "1f680", "1f681", "1f682", "1f68c", "1f691", "1f692", "1f693", "1f695", "1f697", "1f69a", "1f69c", "1f6a2", "1f6aa", "1f6b2", "1f6b4", "1f6bd", "1f6c1", "1f6cb", "1f6cf", "1f6f4", "1f7e0", "1f7e1", "1f7e2", "1f7e3", "1f7e4", "1f94a", "1f955", "1f95a", "1f95b", "1f97e", "1f981", "1f986", "1f9b5", "1f9b6", "1f9b7", "1f9c0", "1f9e2", "1f9e3", "1f9e4", "1f9e5", "1f9e6", "1f9ee", "1fa71", "1fa73", "1fa77", "1fa91", "1fa9e", "1fa9f", "23ea", "23f0", "2600", "2601", "2602", "26aa", "26ab", "26bd", "26be", "26c8", "26f0", "26f3", "26f7", "26f8", "2702", "2708", "270b", "270f", "2744", "2b50", "31-20e3", "32-20e3", "33-20e3", "34-20e3", "35-20e3", "36-20e3", "37-20e3", "38-20e3", "39-20e3",
]);

function codigo(emoji) {
  return [...String(emoji)]
    .filter((c) => c !== "️")
    .map((c) => c.codePointAt(0).toString(16))
    .join("-");
}

/** HTML del emoji: su ilustración si la tenemos, o el emoji como texto. */
export function emojiHtml(emoji, clase = "emoji-img") {
  const archivo = codigo(emoji);
  if (!DISPONIBLES.has(archivo)) return esc(emoji);
  return `<img class="${clase}" src="img/emoji/${archivo}.webp" alt="${esc(emoji)}" draggable="false" />`;
}
