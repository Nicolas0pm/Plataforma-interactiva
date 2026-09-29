// Formularios compartidos por el panel de padres y el del docente:
// - vincular un niño que ya tiene código (código + PIN del niño, RF07/RF11);
// - registrar un niño nuevo y mostrarle al adulto el código y el PIN (RF01).
// El HTML (con sus textos data-i18n) vive en cada página; aquí solo la lógica.

import { apiFetch } from "./api.js";
import { t } from "./i18n.js";

const $ = (id) => document.getElementById(id);

// Pestañas "➕ Registrar niño" (primero, abierta por defecto) y "🔗 Ingresar niño con código".
export function montarPestanas() {
  const pestanas = [$("tab-registrar"), $("tab-ingresar")];
  const activar = (activa) => {
    for (const pestana of pestanas) {
      const seleccionada = pestana === activa;
      pestana.setAttribute("aria-selected", String(seleccionada));
      $(pestana.getAttribute("aria-controls")).hidden = !seleccionada;
    }
  };
  pestanas.forEach((pestana) => pestana.addEventListener("click", () => activar(pestana)));
}

export function montarVincular({ onVinculado }) {
  $("form-vincular").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("error-vincular").textContent = "";
    $("exito-vincular").classList.add("oculto");
    try {
      const estudiante = await apiFetch("/api/vinculacion", {
        method: "POST",
        body: { codigo: $("vincular-codigo").value.trim().toUpperCase(), pin: $("vincular-pin").value },
        esLogin: true, // un 401 aquí es "código o PIN incorrecto", no una sesión vencida
      });
      $("form-vincular").reset();
      $("exito-vincular").textContent = `✅ ${estudiante.nombre} — ${t("kids.linked_ok")}`;
      $("exito-vincular").classList.remove("oculto");
      onVinculado?.(estudiante);
    } catch (err) {
      $("error-vincular").textContent = err.message;
    }
  });
}

export function montarRegistrar({ onCreado }) {
  $("form-registrar").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("error-registrar").textContent = "";
    const pin = $("nuevo-pin").value;
    try {
      const creado = await apiFetch("/api/usuarios", {
        method: "POST",
        body: {
          nombre: $("nuevo-nombre").value,
          edad: Number($("nuevo-edad").value),
          rol: "estudiante",
          acudientes_ids: [],
          docente_id: null,
          email: null,
          pin_acceso: pin,
          device_id: $("nuevo-device")?.value.trim() || null,
          autoriza_datos_menor: $("nuevo-autoriza").checked,
        },
      });
      $("form-registrar").reset();
      $("creado-nombre").textContent = creado.nombre;
      $("creado-codigo").textContent = creado.codigo_acceso;
      $("creado-pin").textContent = pin;
      $("estudiante-creado").classList.remove("oculto");
      $("estudiante-creado").scrollIntoView({ behavior: "smooth", block: "center" });
      onCreado?.(creado);
    } catch (err) {
      $("error-registrar").textContent = err.message;
    }
  });
}
