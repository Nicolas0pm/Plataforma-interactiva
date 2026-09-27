// Navegación coherente entre pantallas.
//
// - `reemplazarCon(url)`: para redirecciones (login → panel, "ya tienes sesión",
//   cerrar sesión). Usa location.replace para que la pantalla de paso no quede en el
//   historial y el botón "atrás" del navegador no devuelva al login ni cree bucles.
// - Botones `data-volver="destino.html"`: suben un nivel. Si la pantalla anterior
//   del historial ES ese destino, hacen history.back() (igual que el botón del
//   navegador); si no (se entró por un enlace directo, o desde otra pantalla), van
//   al destino sin dejar la pantalla actual en el historial.
// - `data-volver=""` (vacío): páginas que se abren en otra pestaña, como los
//   términos: cierran la pestaña si la abrió la app, o vuelven atrás / al inicio.

import "./tema.js";

export function reemplazarCon(url) {
  window.location.replace(url);
}

function anteriorEs(destino) {
  if (!document.referrer) return false;
  try {
    const anterior = new URL(document.referrer);
    if (anterior.origin !== window.location.origin) return false;
    const nombre = anterior.pathname.split("/").pop() || "index.html";
    return nombre === destino;
  } catch {
    return false;
  }
}

export function volver(destino) {
  if (!destino) {
    if (window.opener) {
      window.close();
      return;
    }
    if (document.referrer && new URL(document.referrer).origin === window.location.origin) {
      history.back();
      return;
    }
    reemplazarCon("index.html");
    return;
  }
  if (anteriorEs(destino)) {
    history.back();
  } else {
    reemplazarCon(destino);
  }
}

export function inicializarBotonesVolver() {
  document.querySelectorAll("[data-volver]").forEach((boton) => {
    boton.addEventListener("click", () => volver(boton.dataset.volver));
  });
}

inicializarBotonesVolver();
