"""
Temario de la plataforma (estilo Duolingo, sin audios).

Dos apartados:
- **Vocabulario**: mundos temáticos (animales, colores...). Cada mundo tiene 3 lecciones
  de 8 preguntas: dos de "¿qué es esto?" (imagen → palabra) y una de repaso
  "¿cuál es ...?" (palabra → imagen).
- **Gramática**: temas (verbo to be, presente simple, presente continuo, pasado simple).
  Cada tema trae una explicación corta ("Cómo se usa") y 2 lecciones de 8 ejercicios de
  completar.

El niño no elige qué aprender: el orden lo decide `ORDEN_UNIDADES` (intercala
vocabulario y gramática) y `app/services/lecciones_service.py` elige la siguiente
lección (o un repaso de lo que le fue peor).

Este módulo solo DEFINE el contenido. Las preguntas viven en Firestore (colección
`actividades`) para que un docente pueda agregar o editar sin tocar código
(RNF-ESC-01); `scripts/sembrar_temario.py` las crea a partir de aquí.
"""
import random

PREGUNTAS_POR_LECCION = 8
VIDAS_POR_LECCION = 3  # errores permitidos: al perder las 3 vidas la lección se reinicia
PUNTOS_POR_ACIERTO = 10

# ---------------------------------------------------------------------------
# Vocabulario: (palabra en inglés, emoji)
# ---------------------------------------------------------------------------
VOCABULARIO = {
    "animals": {
        "titulo": {"es": "Animales", "en": "Animals"},
        "emoji": "🐾",
        "pregunta": "What animal is this?",
        "palabras": [
            ("Dog", "🐶"), ("Cat", "🐱"), ("Bird", "🐦"), ("Fish", "🐟"),
            ("Horse", "🐴"), ("Cow", "🐮"), ("Pig", "🐷"), ("Sheep", "🐑"),
            ("Lion", "🦁"), ("Tiger", "🐯"), ("Monkey", "🐵"), ("Elephant", "🐘"),
            ("Rabbit", "🐰"), ("Duck", "🦆"), ("Frog", "🐸"), ("Bear", "🐻"),
        ],
    },
    "colors": {
        "titulo": {"es": "Colores", "en": "Colors"},
        "emoji": "🎨",
        "pregunta": "What color is this?",
        "palabras": [
            ("Red", "🔴"), ("Blue", "🔵"), ("Green", "🟢"), ("Yellow", "🟡"),
            ("Orange", "🟠"), ("Purple", "🟣"), ("Black", "⚫"), ("White", "⚪"),
            ("Brown", "🟤"), ("Pink", "🩷"),
        ],
    },
    "food": {
        "titulo": {"es": "Comida", "en": "Food"},
        "emoji": "🍎",
        "pregunta": "What food is this?",
        "palabras": [
            ("Apple", "🍎"), ("Banana", "🍌"), ("Bread", "🍞"), ("Milk", "🥛"),
            ("Pizza", "🍕"), ("Egg", "🥚"), ("Cheese", "🧀"), ("Rice", "🍚"),
            ("Carrot", "🥕"), ("Grapes", "🍇"), ("Cake", "🍰"), ("Ice cream", "🍦"),
            ("Strawberry", "🍓"), ("Cookie", "🍪"), ("Chicken", "🍗"), ("Corn", "🌽"),
        ],
    },
    "numbers": {
        "titulo": {"es": "Números", "en": "Numbers"},
        "emoji": "🔢",
        "pregunta": "What number is this?",
        "palabras": [
            ("One", "1️⃣"), ("Two", "2️⃣"), ("Three", "3️⃣"), ("Four", "4️⃣"), ("Five", "5️⃣"),
            ("Six", "6️⃣"), ("Seven", "7️⃣"), ("Eight", "8️⃣"), ("Nine", "9️⃣"), ("Ten", "🔟"),
        ],
    },
    "transport": {
        "titulo": {"es": "Transporte", "en": "Transport"},
        "emoji": "🚗",
        "pregunta": "What is this?",
        "palabras": [
            ("Car", "🚗"), ("Bus", "🚌"), ("Bike", "🚲"), ("Plane", "✈️"),
            ("Train", "🚂"), ("Boat", "🚢"), ("Truck", "🚚"), ("Helicopter", "🚁"),
            ("Taxi", "🚕"), ("Motorcycle", "🏍️"), ("Rocket", "🚀"), ("Tractor", "🚜"),
            ("Ambulance", "🚑"), ("Fire truck", "🚒"), ("Police car", "🚓"), ("Scooter", "🛴"),
        ],
    },
    "body": {
        "titulo": {"es": "Mi cuerpo", "en": "My body"},
        "emoji": "🖐️",
        "pregunta": "What part of the body is this?",
        "palabras": [
            ("Eye", "👁️"), ("Ear", "👂"), ("Nose", "👃"), ("Mouth", "👄"), ("Hand", "✋"),
            ("Foot", "🦶"), ("Leg", "🦵"), ("Arm", "💪"), ("Tooth", "🦷"), ("Tongue", "👅"),
        ],
    },
}

# ---------------------------------------------------------------------------
# Gramática: (oración con ___, respuesta correcta, [distractores])
# ---------------------------------------------------------------------------
GRAMATICA = {
    "to-be": {
        "titulo": {"es": "Verbo to be", "en": "Verb to be"},
        "emoji": "🙋",
        "explicacion": {
            "es": [
                "El verbo **to be** significa **ser** o **estar**.",
                "**I** → **am** · I am happy (Yo estoy feliz).",
                "**He / She / It** → **is** · She is my sister (Ella es mi hermana).",
                "**You / We / They** → **are** · They are friends (Ellos son amigos).",
            ],
            "en": [
                "The verb **to be** means *ser* or *estar*.",
                "**I** → **am** · I am happy.",
                "**He / She / It** → **is** · She is my sister.",
                "**You / We / They** → **are** · They are friends.",
            ],
        },
        "lecciones": [
            [
                ("I ___ happy.", "am", ["is", "are"]),
                ("She ___ my sister.", "is", ["am", "are"]),
                ("They ___ friends.", "are", ["is", "am"]),
                ("The dog ___ big.", "is", ["are", "am"]),
                ("We ___ at school.", "are", ["is", "am"]),
                ("You ___ my friend.", "are", ["is", "am"]),
                ("It ___ a cat.", "is", ["are", "am"]),
                ("I ___ seven years old.", "am", ["is", "are"]),
            ],
            [
                ("He ___ tall.", "is", ["are", "am"]),
                ("The cats ___ black.", "are", ["is", "am"]),
                ("My mom ___ a teacher.", "is", ["are", "am"]),
                ("I ___ not sad.", "am", ["is", "are"]),
                ("We ___ brothers.", "are", ["is", "am"]),
                ("The sun ___ hot.", "is", ["are", "am"]),
                ("You and I ___ friends.", "are", ["is", "am"]),
                ("My name ___ Ana.", "is", ["are", "am"]),
            ],
        ],
    },
    "simple-present": {
        "titulo": {"es": "Presente simple", "en": "Simple present"},
        "emoji": "🔁",
        "explicacion": {
            "es": [
                "Se usa para cosas que haces **siempre** o **todos los días**.",
                "Con **I / You / We / They** el verbo va igual · I **play** football.",
                "Con **He / She / It** se agrega **s** o **es** · She **plays** · He **watches**.",
                "Para negar: **don't** (I, you, we, they) y **doesn't** (he, she, it).",
                "Para preguntar: **Do** you...? · **Does** he...?",
            ],
            "en": [
                "We use it for things you do **always** or **every day**.",
                "With **I / You / We / They** the verb stays the same · I **play** football.",
                "With **He / She / It** add **s** or **es** · She **plays** · He **watches**.",
                "Negative: **don't** (I, you, we, they) and **doesn't** (he, she, it).",
                "Questions: **Do** you...? · **Does** he...?",
            ],
        },
        "lecciones": [
            [
                ("I ___ football.", "play", ["plays"]),
                ("She ___ milk every day.", "drinks", ["drink"]),
                ("He ___ to school.", "goes", ["go"]),
                ("We ___ apples.", "eat", ["eats"]),
                ("My cat ___ a lot.", "sleeps", ["sleep"]),
                ("They ___ English.", "speak", ["speaks"]),
                ("Tom ___ TV.", "watches", ["watch"]),
                ("I ___ my teeth.", "brush", ["brushes"]),
            ],
            [
                ("I ___ like carrots.", "don't", ["doesn't"]),
                ("She ___ like milk.", "doesn't", ["don't"]),
                ("___ you like pizza?", "Do", ["Does"]),
                ("___ he play football?", "Does", ["Do"]),
                ("He ___ swim.", "doesn't", ["don't"]),
                ("We ___ go to school on Sunday.", "don't", ["doesn't"]),
                ("___ your dog run?", "Does", ["Do"]),
                ("___ they read books?", "Do", ["Does"]),
            ],
        ],
    },
    "present-continuous": {
        "titulo": {"es": "Presente continuo", "en": "Present continuous"},
        "emoji": "🏃",
        "explicacion": {
            "es": [
                "Se usa para lo que está pasando **ahora mismo**.",
                "Se forma con **am / is / are** + verbo terminado en **-ing**.",
                "I **am playing** (Estoy jugando) · She **is reading** (Ella está leyendo).",
                "They **are running** (Ellos están corriendo).",
            ],
            "en": [
                "We use it for things happening **right now**.",
                "It is **am / is / are** + a verb ending in **-ing**.",
                "I **am playing** · She **is reading**.",
                "They **are running**.",
            ],
        },
        "lecciones": [
            [
                ("I am ___.", "playing", ["play", "plays"]),
                ("She is ___ a book.", "reading", ["read", "reads"]),
                ("They are ___.", "running", ["run", "runs"]),
                ("He ___ eating.", "is", ["are", "am"]),
                ("We ___ singing.", "are", ["is", "am"]),
                ("I ___ drawing.", "am", ["is", "are"]),
                ("The baby is ___.", "sleeping", ["sleep", "sleeps"]),
                ("The birds are ___.", "flying", ["fly", "flies"]),
            ],
            [
                ("Look! It ___ raining.", "is", ["are", "am"]),
                ("Mom is ___ dinner.", "cooking", ["cook", "cooks"]),
                ("Are you ___ TV?", "watching", ["watch", "watches"]),
                ("They ___ dancing.", "are", ["is", "am"]),
                ("He is ___ a bike.", "riding", ["ride", "rides"]),
                ("I am ___ my hands.", "washing", ["wash", "washes"]),
                ("The cat ___ drinking milk.", "is", ["are", "am"]),
                ("We are ___ a cake.", "making", ["make", "makes"]),
            ],
        ],
    },
    "simple-past": {
        "titulo": {"es": "Pasado simple", "en": "Simple past"},
        "emoji": "⏪",
        "explicacion": {
            "es": [
                "Se usa para cosas que **ya pasaron** (yesterday = ayer, last night = anoche).",
                "Verbos regulares: se agrega **-ed** · play → **played**, watch → **watched**.",
                "Verbos irregulares cambian: go → **went**, eat → **ate**, see → **saw**.",
                "Es igual para todos: I **played**, she **played**, they **played**.",
            ],
            "en": [
                "We use it for things that **already happened** (yesterday, last night).",
                "Regular verbs add **-ed** · play → **played**, watch → **watched**.",
                "Irregular verbs change: go → **went**, eat → **ate**, see → **saw**.",
                "It is the same for everyone: I **played**, she **played**, they **played**.",
            ],
        },
        "lecciones": [
            [
                ("Yesterday I ___ football.", "played", ["play", "plays"]),
                ("She ___ TV last night.", "watched", ["watch", "watches"]),
                ("We ___ to music.", "listened", ["listen", "listens"]),
                ("He ___ the door.", "opened", ["open", "opens"]),
                ("They ___ in the park.", "walked", ["walk", "walks"]),
                ("I ___ my room.", "cleaned", ["clean", "cleans"]),
                ("The baby ___ a lot.", "cried", ["cry", "cries"]),
                ("We ___ at the clown.", "laughed", ["laugh", "laughs"]),
            ],
            [
                ("Yesterday I ___ to the zoo.", "went", ["go", "goed"]),
                ("She ___ a cake.", "ate", ["eat", "eated"]),
                ("He ___ a big dog.", "saw", ["see", "seed"]),
                ("We ___ a sandcastle.", "made", ["make", "maked"]),
                ("They ___ orange juice.", "drank", ["drink", "drinked"]),
                ("I ___ a letter to grandma.", "wrote", ["write", "writed"]),
                ("My dad ___ a red car.", "had", ["have", "haved"]),
                ("The dog ___ very fast.", "ran", ["run", "runned"]),
            ],
        ],
    },
}

# Orden del camino: intercala vocabulario y gramática.
ORDEN_UNIDADES = [
    "animals", "to-be", "colors", "simple-present", "food",
    "present-continuous", "numbers", "simple-past", "transport", "body",
]

SECCIONES = [
    {"id": "vocabulario", "titulo": {"es": "Vocabulario", "en": "Vocabulary"}, "emoji": "📚"},
    {"id": "gramatica", "titulo": {"es": "Gramática", "en": "Grammar"}, "emoji": "✏️"},
]


def seccion_de(unidad: str) -> str:
    return "vocabulario" if unidad in VOCABULARIO else "gramatica"


def info_unidad(unidad: str) -> dict:
    datos = VOCABULARIO.get(unidad) or GRAMATICA[unidad]
    return {
        "id": unidad,
        "seccion": seccion_de(unidad),
        "titulo": datos["titulo"],
        "emoji": datos["emoji"],
        "lecciones": numero_de_lecciones(unidad),
        "explicacion": datos.get("explicacion"),
    }


def numero_de_lecciones(unidad: str) -> int:
    return 3 if unidad in VOCABULARIO else len(GRAMATICA[unidad]["lecciones"])


def lecciones_en_orden() -> list[tuple[str, int]]:
    """Todas las lecciones del camino, en el orden en que se desbloquean."""
    return [(u, n) for u in ORDEN_UNIDADES for n in range(1, numero_de_lecciones(u) + 1)]


def clave_leccion(unidad: str, leccion: int) -> str:
    return f"{unidad}-{leccion}"


def _preguntas_vocabulario(unidad: str) -> list[list[dict]]:
    datos = VOCABULARIO[unidad]
    palabras = datos["palabras"]
    azar = random.Random(unidad)  # determinista: sembrar dos veces da el mismo contenido
    n = PREGUNTAS_POR_LECCION

    def imagen_a_palabra(palabra, emoji):
        otras = [p for p, _ in palabras if p != palabra]
        return {"pregunta": datos["pregunta"], "icono": emoji, "respuesta_correcta": palabra,
                "opciones": [palabra, *azar.sample(otras, 3)], "formato_opciones": "texto"}

    def palabra_a_imagen(palabra, emoji):
        otras = [e for p, e in palabras if p != palabra]
        return {"pregunta": f"Which one is “{palabra.lower()}”?", "icono": None,
                "respuesta_correcta": emoji, "opciones": [emoji, *azar.sample(otras, 3)],
                "formato_opciones": "emoji"}

    primera = palabras[:n]
    segunda = palabras[n:2 * n]
    if len(segunda) < n:  # mundos con menos de 16 palabras: se completan al revés
        segunda = segunda + azar.sample(primera, n - len(segunda))
        leccion_2 = [imagen_a_palabra(*p) for p in palabras[n:]] + [
            palabra_a_imagen(*p) for p in segunda[len(palabras[n:]):]
        ]
    else:
        leccion_2 = [imagen_a_palabra(*p) for p in segunda]
    repaso = [palabra_a_imagen(*p) for p in azar.sample(palabras, n)]
    return [[imagen_a_palabra(*p) for p in primera], leccion_2, repaso]


def _preguntas_gramatica(unidad: str) -> list[list[dict]]:
    return [
        [
            {"pregunta": oracion, "icono": None, "respuesta_correcta": correcta,
             "opciones": [correcta, *distractores], "formato_opciones": "texto"}
            for oracion, correcta, distractores in leccion
        ]
        for leccion in GRAMATICA[unidad]["lecciones"]
    ]


def generar_actividades() -> list[dict]:
    """Todas las preguntas del temario, listas para guardar en Firestore."""
    actividades = []
    for indice, unidad in enumerate(ORDEN_UNIDADES, start=1):
        lecciones = _preguntas_vocabulario(unidad) if unidad in VOCABULARIO else _preguntas_gramatica(unidad)
        for numero, preguntas in enumerate(lecciones, start=1):
            for orden, pregunta in enumerate(preguntas, start=1):
                actividades.append({
                    "nombre": f"{unidad}-{numero}-{orden}",
                    "descripcion": "",
                    "seccion": seccion_de(unidad),
                    "unidad": unidad,
                    "leccion": numero,
                    "orden": orden,
                    "nivel": indice,
                    "tipo": "vocabulario" if unidad in VOCABULARIO else "gramatica",
                    "puntaje_maximo": PUNTOS_POR_ACIERTO,
                    "activo": True,
                    **pregunta,
                })
    return actividades
