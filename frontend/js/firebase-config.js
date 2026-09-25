// Pega aquí el firebaseConfig que te da la consola de Firebase
// (Configuración del proyecto → Tus apps → app web).
// Este SDK web se usa ÚNICAMENTE para el login de docentes/padres/admin
// (Firebase Authentication). Todos los datos de negocio pasan por la API.

const firebaseConfig = {
  apiKey: "AIzaSyD8py_Anjvb2NRFZZyF2KmmRyJFB5BpP2I",
  authDomain: "plataforma-ingles-kids.firebaseapp.com",
  databaseURL: "https://plataforma-ingles-kids-default-rtdb.firebaseio.com",
  projectId: "plataforma-ingles-kids",
  storageBucket: "plataforma-ingles-kids.firebasestorage.app",
  messagingSenderId: "774063165798",
  appId: "1:774063165798:web:c1b992a7d6f826db2a38a7",
};

// Se importa como módulo ES desde index.html via <script type="module">
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
} from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export { signInWithEmailAndPassword, createUserWithEmailAndPassword, signOut, onAuthStateChanged };

/** true si `firebaseConfig` sigue con los valores de ejemplo (no configurado). */
export const firebaseConfigurado = firebaseConfig.apiKey !== "TU_API_KEY";
