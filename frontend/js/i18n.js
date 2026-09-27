// RNF-LOC-01: la plataforma debe poder mostrar contenido en español e inglés.
// Diccionario simple + helper `data-i18n` (sin librerías, HTML/CSS/JS puro).

const DICCIONARIO = {
  es: {
    "nav.logout": "Cerrar sesión",
    "nav.back": "Volver",
    "app.title": "¡Aprendamos inglés!",

    "home.tagline": "Aprende inglés y gana premios reales",
    "home.pick_role": "¿Quién eres?",
    "home.kid": "Soy un niño",
    "theme.title": "Tema de colores",
    "theme.auto": "Automático",
    "theme.light": "Claro",
    "theme.dark": "Oscuro",
    "theme.purple": "Noche morada",
    "theme.pink": "Rosa dulce",
    "home.welcome_back": "¡Hola de nuevo,",
    "home.continue": "Continuar",
    "home.not_me": "No soy yo (cerrar sesión)",
    "home.teacher": "Soy docente",
    "home.parent": "Soy padre o acudiente",

    "login.title": "Iniciar sesión",
    "login.email": "Correo",
    "login.password": "Contraseña",
    "login.submit": "Entrar",
    "login.create_account": "Crear cuenta",
    "login.name": "Nombre",
    "login.dev_mode": "Modo de prueba (sin Firebase)",
    "login.dev_hint": "Solo funciona si el backend corre con USE_FAKE_DB=true.",
    "login.dev_id": "ID de usuario",
    "login.dev_login": "Entrar (prueba)",
    "login.dev_create": "Crear cuenta de prueba",
    "login.dev_created": "Cuenta creada. Tu ID de usuario es:",

    "kidlogin.title": "¡Hola! ¿Cuál es tu código?",
    "kidlogin.code": "Código",
    "kidlogin.pin_prompt": "Ahora tu PIN secreto",
    "kidlogin.code_hint": "Son 6 letras y números.",
    "kidlogin.code_invalid": "Tu código tiene 6 letras y números. ¡Revísalo!",
    "kidlogin.next": "Siguiente",
    "kidlogin.change": "Cambiar",
    "kidlogin.pin_hint": "Son 4 números. ¡No se lo muestres a nadie!",
    "kidlogin.locked": "Muchos intentos. Espera unos minutos y vuelve a intentar.",
    "cred.code_title": "Código",
    "cred.code_help": "Se escribe primero · letras y números",
    "cred.pin_title": "PIN secreto",
    "cred.pin_help": "Se marca después · solo 4 números",
    "kidlogin.clear": "Borrar",
    "kidlogin.wrong": "Código o PIN incorrecto, ¡inténtalo de nuevo!",
    "kidlogin.no_server": "No hay conexión con el servidor. Avísale a tu profe.",
    "kidlogin.need_code": "Pídele tu código de estudiante a tu profe o a tu familia.",

    "dash.hello": "¡Hola de nuevo,",
    "dash.level": "Nivel",
    "dash.points": "Puntos",
    "dash.streak": "Racha",
    "dash.worlds": "Elige un mundo para jugar",
    "dash.rewards_link": "Mis premios",
    "dash.next_level": "para el siguiente nivel",
    "dash.max_level": "¡Nivel máximo!",
    "dash.play": "¡Jugar!",
    "dash.world1": "Animales",
    "dash.world2": "Colores",
    "dash.world3": "Comida",
    "dash.world4": "Números",
    "dash.world5": "Transporte",
    "dash.world6": "Mi cuerpo",

    "activity.loading": "Cargando actividad...",
    "activity.correct": "¡Genial!",
    "activity.incorrect": "¡Casi! Intenta de nuevo",
    "activity.next": "Siguiente",
    "activity.finish": "Terminar",
    "activity.back_dashboard": "Volver al mapa",
    "activity.reward": "¡Ganaste una recompensa física! Ve a revisar la máquina.",
    "activity.reward_no_device": "¡Felicidades, lo lograste! 🌟",
    "activity.level_up": "¡Subiste de nivel!",
    "activity.session_done": "¡Felicidades! Terminaste el mundo",
    "activity.session_summary": "Acertaste {aciertos} de {total} a la primera y ganaste {puntos} puntos.",
    "activity.empty": "Todavía no hay actividades en este nivel.",

    "rewards.title": "Mis recompensas",
    "rewards.pending": "Pendiente",
    "rewards.delivered": "Entregada",
    "rewards.empty": "Todavía no tienes recompensas. ¡Sigue jugando!",

    "teacher.title": "Panel del docente",
    "teacher.total_students": "Estudiantes",
    "teacher.avg_progress": "Progreso promedio",
    "teacher.active_today": "Activos hoy",
    "teacher.needs_help": "Necesitan ayuda",
    "teacher.students_list": "Mis estudiantes",
    "teacher.leave_feedback": "Dejar comentario",
    "teacher.view_progress": "Ver progreso",
    "teacher.needs_help_badge": "Necesita ayuda",
    "teacher.device_id": "ID del dispensador (opcional)",
    "teacher.device_hint": "Déjalo vacío si el salón todavía no tiene el dispensador físico conectado.",
    "teacher.pin_label": "PIN (exactamente 4 números)",
    "teacher.pin_hint": "El niño lo marca en el teclado numérico. Anótalo: por seguridad no se vuelve a mostrar.",
    "teacher.created_title": "¡Registrado!",
    "teacher.created_body": "Para entrar, en \"Soy un niño\" escribe este código y luego el PIN:",
    "teacher.code": "Código",

    "notfound.title": "¡Uy! Esta página se perdió",
    "notfound.body": "El zorrito la buscó por todas partes, pero no existe o cambió de lugar.",
    "notfound.home": "Volver al inicio",
    "terms.accept": "He leído y acepto los",
    "terms.link": "Términos de uso y la Política de datos",
    "terms.policy_link": "(ver política de datos)",
    "terms.footer": "Términos de uso y privacidad",
    "terms.spanish_only": "",
    "teacher.consent": "Confirmo que la familia del niño autorizó el tratamiento de sus datos para fines educativos (Ley 1581 de 2012).",
    "parent.consent": "Soy el padre, madre o acudiente del niño y autorizo el tratamiento de sus datos para fines educativos (Ley 1581 de 2012).",
    "kids.code_label": "Código del niño",
    "kids.pin_label": "PIN del niño (4 números)",
    "kids.link_button": "Agregar a mi panel",
    "kids.linked_ok": "ya aparece en tu panel.",
    "kids.register": "Registrar niño",
    "kids.age": "Edad",
    "parent.have_code_title": "¿Tu hijo ya tiene código?",
    "parent.have_code_hint": "Si tu hijo ya fue registrado (por ti, por otro familiar o por su profe), escribe aquí su código y su PIN. Así comprobamos que tienes acceso a su cuenta y podrás ver su progreso.",
    "parent.new_title": "¿Tu hijo todavía no tiene código?",
    "parent.new_hint": "Regístralo aquí. Te mostraremos su código; con ese código y el PIN que elijas, tu hijo entra a jugar en \"Soy un niño\".",
    "teacher.have_code_title": "¿El estudiante ya tiene código?",
    "teacher.have_code_hint": "Si ya fue registrado (por su familia o por otro profe), escribe aquí su código y su PIN para agregarlo a tu grupo.",
    "teacher.new_title": "¿El estudiante todavía no tiene código?",
    "teacher.new_hint": "Regístralo aquí. Te mostraremos su código para que se lo des junto con el PIN que elijas.",
    "dash.my_code": "Tu código para entrar",
    "parent.title": "Panel de padres",
    "parent.my_children": "Mis hijos",
    "parent.progress": "Progreso",
    "parent.rewards": "Recompensas",
    "parent.feedback": "Comentarios del docente",
    "parent.no_children": "Todavía no tienes hijos vinculados.",

  },
  en: {
    "nav.logout": "Log out",
    "nav.back": "Back",
    "app.title": "Let's Learn English!",

    "home.tagline": "Learn English and win real prizes",
    "home.pick_role": "Who are you?",
    "home.kid": "I'm a kid",
    "theme.title": "Color theme",
    "theme.auto": "Automatic",
    "theme.light": "Light",
    "theme.dark": "Dark",
    "theme.purple": "Purple night",
    "theme.pink": "Sweet pink",
    "home.welcome_back": "Welcome back,",
    "home.continue": "Continue",
    "home.not_me": "Not me (sign out)",
    "home.teacher": "I'm a teacher",
    "home.parent": "I'm a parent",

    "login.title": "Log in",
    "login.email": "Email",
    "login.password": "Password",
    "login.submit": "Log in",
    "login.create_account": "Create account",
    "login.name": "Name",
    "login.dev_mode": "Test mode (no Firebase)",
    "login.dev_hint": "Only works if the backend runs with USE_FAKE_DB=true.",
    "login.dev_id": "User ID",
    "login.dev_login": "Log in (test)",
    "login.dev_create": "Create test account",
    "login.dev_created": "Account created. Your user ID is:",

    "kidlogin.title": "Hi! What's your code?",
    "kidlogin.code": "Code",
    "kidlogin.pin_prompt": "Now your secret PIN",
    "kidlogin.code_hint": "It has 6 letters and numbers.",
    "kidlogin.code_invalid": "Your code has 6 letters and numbers. Check it!",
    "kidlogin.next": "Next",
    "kidlogin.change": "Change",
    "kidlogin.pin_hint": "It has 4 numbers. Don't show it to anyone!",
    "kidlogin.locked": "Too many tries. Wait a few minutes and try again.",
    "cred.code_title": "Code",
    "cred.code_help": "Typed first · letters and numbers",
    "cred.pin_title": "Secret PIN",
    "cred.pin_help": "Entered second · only 4 numbers",
    "kidlogin.clear": "Clear",
    "kidlogin.wrong": "Wrong code or PIN, try again!",
    "kidlogin.no_server": "Can't reach the server. Tell your teacher.",
    "kidlogin.need_code": "Ask your teacher or family for your student code.",

    "dash.hello": "Welcome back,",
    "dash.level": "Level",
    "dash.points": "Points",
    "dash.streak": "Streak",
    "dash.worlds": "Pick a world to play",
    "dash.rewards_link": "My rewards",
    "dash.next_level": "to next level",
    "dash.max_level": "Max level!",
    "dash.play": "Play!",
    "dash.world1": "Animals",
    "dash.world2": "Colors",
    "dash.world3": "Food",
    "dash.world4": "Numbers",
    "dash.world5": "Transport",
    "dash.world6": "My body",

    "activity.loading": "Loading activity...",
    "activity.correct": "Amazing!",
    "activity.incorrect": "Almost! Try again",
    "activity.next": "Next",
    "activity.finish": "Finish",
    "activity.back_dashboard": "Back to map",
    "activity.reward": "You earned a physical reward! Go check the machine.",
    "activity.reward_no_device": "Congratulations, you did it! 🌟",
    "activity.level_up": "You leveled up!",
    "activity.session_done": "Congratulations! You finished the world",
    "activity.session_summary": "You got {aciertos} of {total} right on the first try and earned {puntos} points.",
    "activity.empty": "No activities in this level yet.",

    "rewards.title": "My rewards",
    "rewards.pending": "Pending",
    "rewards.delivered": "Delivered",
    "rewards.empty": "No rewards yet. Keep playing!",

    "teacher.title": "Teacher panel",
    "teacher.total_students": "Students",
    "teacher.avg_progress": "Average progress",
    "teacher.active_today": "Active today",
    "teacher.needs_help": "Need help",
    "teacher.students_list": "My students",
    "teacher.leave_feedback": "Leave feedback",
    "teacher.view_progress": "View progress",
    "teacher.needs_help_badge": "Needs help",
    "teacher.device_id": "Dispenser ID (optional)",
    "teacher.device_hint": "Leave it empty if the classroom doesn't have the physical dispenser connected yet.",
    "teacher.pin_label": "PIN (exactly 4 numbers)",
    "teacher.pin_hint": "The child types it on the number pad. Write it down: for security it isn't shown again.",
    "teacher.created_title": "Registered!",
    "teacher.created_body": "To sign in, on \"I'm a kid\" type this code and then the PIN:",
    "teacher.code": "Code",

    "notfound.title": "Oops! This page got lost",
    "notfound.body": "The little fox looked everywhere, but it doesn't exist or it moved.",
    "notfound.home": "Back to home",
    "terms.accept": "I have read and accept the",
    "terms.link": "Terms of use and Data policy",
    "terms.policy_link": "(see data policy)",
    "terms.footer": "Terms of use and privacy",
    "terms.spanish_only": "This document is only available in Spanish, the language that governs it under Colombian law.",
    "teacher.consent": "I confirm the child's family authorized the processing of their data for educational purposes (Colombian Law 1581 of 2012).",
    "parent.consent": "I am the child's parent or guardian and I authorize the processing of their data for educational purposes (Colombian Law 1581 of 2012).",
    "kids.code_label": "Child's code",
    "kids.pin_label": "Child's PIN (4 numbers)",
    "kids.link_button": "Add to my panel",
    "kids.linked_ok": "now shows up in your panel.",
    "kids.register": "Register child",
    "kids.age": "Age",
    "parent.have_code_title": "Does your child already have a code?",
    "parent.have_code_hint": "If your child is already registered (by you, another family member or their teacher), type their code and PIN here. That confirms you have access to their account, and you'll see their progress.",
    "parent.new_title": "Your child doesn't have a code yet?",
    "parent.new_hint": "Register them here. We'll show you their code; with that code and the PIN you choose, your child signs in on \"I'm a kid\".",
    "teacher.have_code_title": "Does the student already have a code?",
    "teacher.have_code_hint": "If they're already registered (by their family or another teacher), type their code and PIN here to add them to your group.",
    "teacher.new_title": "The student doesn't have a code yet?",
    "teacher.new_hint": "Register them here. We'll show you their code so you can give it to them along with the PIN you choose.",
    "dash.my_code": "Your sign-in code",
    "parent.title": "Parent panel",
    "parent.my_children": "My children",
    "parent.progress": "Progress",
    "parent.rewards": "Rewards",
    "parent.feedback": "Teacher's feedback",
    "parent.no_children": "No children linked yet.",

  },
};

const CLAVE_IDIOMA = "pik_idioma";

export function idiomaActual() {
  return localStorage.getItem(CLAVE_IDIOMA) || "es";
}

export function t(clave) {
  const idioma = idiomaActual();
  return DICCIONARIO[idioma]?.[clave] ?? DICCIONARIO.es[clave] ?? clave;
}

export function aplicarIdioma() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.setAttribute("title", t(el.dataset.i18nTitle));
    el.setAttribute("aria-label", t(el.dataset.i18nTitle));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.setAttribute("placeholder", t(el.dataset.i18nPlaceholder));
  });
  document.documentElement.lang = idiomaActual();
  document.querySelectorAll("[data-lang-toggle]").forEach((btn) => {
    btn.textContent = idiomaActual() === "es" ? "EN" : "ES";
  });
}

export function alternarIdioma() {
  localStorage.setItem(CLAVE_IDIOMA, idiomaActual() === "es" ? "en" : "es");
  aplicarIdioma();
}

export function inicializarLangToggle() {
  document.querySelectorAll("[data-lang-toggle]").forEach((btn) => {
    btn.addEventListener("click", alternarIdioma);
  });
  aplicarIdioma();
}
