// Botón "🔑 Contraseña" de la barra superior de los paneles de docentes y padres: abre un
// diálogo para cambiar la contraseña (por ejemplo, la temporal que le dio el admin).

import { apiFetch } from "./api.js";
import { aplicarIdioma, t } from "./i18n.js";

export function agregarCambioDePassword() {
  const acciones = document.querySelector(".topbar .topbar-actions");
  const salir = document.getElementById("btn-logout");
  if (!acciones || !salir) return;

  const boton = document.createElement("button");
  boton.type = "button";
  boton.className = "secundario";
  boton.dataset.i18n = "password.button";
  acciones.insertBefore(boton, salir);

  const dialogo = document.createElement("dialog");
  dialogo.className = "card dialogo";
  dialogo.innerHTML = `
    <h2 data-i18n="password.title"></h2>
    <form method="dialog" id="form-password">
      <label for="pw-actual" data-i18n="password.current"></label>
      <input id="pw-actual" type="password" required autocomplete="current-password" />
      <label for="pw-nueva" data-i18n="password.new"></label>
      <input id="pw-nueva" type="password" required minlength="8" maxlength="128" autocomplete="new-password" />
      <p class="hint" data-i18n="login.password_hint"></p>
      <label for="pw-repetir" data-i18n="password.repeat"></label>
      <input id="pw-repetir" type="password" required minlength="8" maxlength="128" autocomplete="new-password" />
      <p class="error-msg" id="pw-error" role="alert"></p>
      <p class="hint" id="pw-listo" role="status"></p>
      <div class="acciones-dialogo">
        <button type="button" class="secundario" id="pw-cancelar" data-i18n="password.cancel"></button>
        <button type="submit" data-i18n="password.save"></button>
      </div>
    </form>`;
  document.body.appendChild(dialogo);
  aplicarIdioma();

  const formulario = dialogo.querySelector("form");
  const errorEl = dialogo.querySelector("#pw-error");
  const listoEl = dialogo.querySelector("#pw-listo");

  boton.addEventListener("click", () => {
    formulario.reset();
    errorEl.textContent = listoEl.textContent = "";
    dialogo.showModal();
  });
  dialogo.querySelector("#pw-cancelar").addEventListener("click", () => dialogo.close());

  formulario.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.textContent = listoEl.textContent = "";
    const nueva = dialogo.querySelector("#pw-nueva").value;
    if (nueva !== dialogo.querySelector("#pw-repetir").value) {
      errorEl.textContent = t("password.mismatch");
      return;
    }
    const guardar = formulario.querySelector("button[type=submit]");
    guardar.disabled = true;
    try {
      await apiFetch("/api/usuarios/cambiar-password", {
        method: "POST",
        body: { actual: dialogo.querySelector("#pw-actual").value, nueva },
      });
      formulario.reset();
      listoEl.textContent = t("password.done");
      setTimeout(() => dialogo.close(), 1500);
    } catch (err) {
      errorEl.textContent = err.message;
    } finally {
      guardar.disabled = false;
    }
  });
}
