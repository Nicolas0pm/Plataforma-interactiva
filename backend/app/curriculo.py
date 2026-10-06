"""
Temario de la plataforma (estilo Duolingo, sin audios).

Dos apartados independientes, cada uno con su propio camino:
- **Vocabulario**: 11 mundos temáticos (animales, colores, ropa, deportes...). Cada mundo
  tiene 5 lecciones de 8 preguntas, cada una con un enfoque distinto: conocer las palabras,
  encontrarlas, traducirlas, escribirlas y un desafío final (ver `_preguntas_vocabulario`).
- **Gramática**: 10 temas (verbo to be, artículos, plurales, posesivos, presente simple,
  preposiciones, there is/are, can, presente continuo, pasado simple). Cada tema trae una
  explicación corta ("Cómo se usa") y 4 lecciones de 8 ejercicios de completar.

El niño elige el apartado (vocabulario o gramática); dentro de él no elige: el orden lo
decide `ORDEN_VOCABULARIO` / `ORDEN_GRAMATICA` y `app/services/lecciones_service.py` elige
la siguiente lección (o un repaso de lo que le fue peor).

Este módulo solo DEFINE el contenido. Las preguntas viven en Firestore (colección
`actividades`) para que un docente pueda agregar o editar sin tocar código
(RNF-ESC-01); `python scripts/verificar_firebase.py --sembrar` las crea a partir de aquí.
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
    "clothes": {
        "titulo": {"es": "La ropa", "en": "Clothes"},
        "emoji": "👕",
        "pregunta": "What is this?",
        "palabras": [
            ("T-shirt", "👕"), ("Jeans", "👖"), ("Dress", "👗"), ("Sneakers", "👟"),
            ("Cap", "🧢"), ("Socks", "🧦"), ("Coat", "🧥"), ("Scarf", "🧣"),
            ("Gloves", "🧤"), ("Boots", "🥾"), ("Glasses", "👓"), ("Tie", "👔"),
            ("Backpack", "🎒"), ("Swimsuit", "🩱"), ("Shorts", "🩳"), ("Hat", "👒"),
        ],
    },
    "nature": {
        "titulo": {"es": "Naturaleza y clima", "en": "Nature and weather"},
        "emoji": "🌈",
        "pregunta": "What is this?",
        "palabras": [
            ("Sun", "☀️"), ("Rain", "🌧️"), ("Snow", "❄️"), ("Cloud", "☁️"),
            ("Wind", "💨"), ("Rainbow", "🌈"), ("Storm", "⛈️"), ("Moon", "🌙"),
            ("Star", "⭐"), ("Tree", "🌳"), ("Flower", "🌸"), ("Mountain", "⛰️"),
            ("Sea", "🌊"), ("Fire", "🔥"), ("Leaf", "🍃"), ("Umbrella", "☂️"),
        ],
    },
    "school": {
        "titulo": {"es": "Útiles escolares", "en": "School things"},
        "emoji": "✏️",
        "pregunta": "What is this?",
        "palabras": [
            ("Book", "📖"), ("Pencil", "✏️"), ("Pen", "🖊️"), ("Ruler", "📏"),
            ("Scissors", "✂️"), ("Notebook", "📓"), ("Crayon", "🖍️"), ("Paintbrush", "🖌️"),
            ("Computer", "💻"), ("Clock", "⏰"), ("Calculator", "🧮"), ("Globe", "🌎"),
        ],
    },
    "sports": {
        "titulo": {"es": "Deportes", "en": "Sports"},
        "emoji": "⚽",
        "pregunta": "What sport is this?",
        "palabras": [
            ("Soccer", "⚽"), ("Basketball", "🏀"), ("Baseball", "⚾"), ("Tennis", "🎾"),
            ("Volleyball", "🏐"), ("Swimming", "🏊"), ("Running", "🏃"), ("Cycling", "🚴"),
            ("Skating", "⛸️"), ("Skiing", "⛷️"), ("Boxing", "🥊"), ("Golf", "⛳"),
            ("Bowling", "🎳"), ("Ping-pong", "🏓"), ("Surfing", "🏄"), ("Football", "🏈"),
        ],
    },
    "home": {
        "titulo": {"es": "La casa", "en": "My home"},
        "emoji": "🏠",
        "pregunta": "What is this?",
        "palabras": [
            ("House", "🏠"), ("Bed", "🛏️"), ("Chair", "🪑"), ("Door", "🚪"),
            ("Window", "🪟"), ("Sofa", "🛋️"), ("Bathtub", "🛁"), ("Toilet", "🚽"),
            ("Key", "🔑"), ("TV", "📺"), ("Phone", "📱"), ("Mirror", "🪞"),
            ("Light", "💡"),
        ],
    },
}

# Pregunta "¿cuál NO es…?" de cada mundo (lección 5).
_INTRUSO = {
    "animals": "Which one is NOT an animal?",
    "colors": "Which one is NOT a color?",
    "food": "Which one is NOT food?",
    "numbers": "Which one is NOT a number?",
    "transport": "Which one is NOT a vehicle?",
    "body": "Which one is NOT a part of the body?",
    "clothes": "Which one is NOT something to wear?",
    "nature": "Which one is NOT about nature or the weather?",
    "school": "Which one is NOT a school thing?",
    "sports": "Which one is NOT a sport?",
    "home": "Which one is NOT in a house?",
}
for _unidad, _texto in _INTRUSO.items():
    VOCABULARIO[_unidad]["intruso"] = _texto

# De qué mundos sale el "intruso": mundos que no se confundan con el tema (en la naturaleza
# hay animales y en una casa hay reloj, así que esos no sirven de intruso ahí).
INTRUSOS_POR_DEFECTO = ["transport", "school"]
INTRUSOS = {
    "transport": ["animals", "food"],
    "school": ["animals", "food"],
    "home": ["animals", "transport"],
}

# Traducción de cada palabra (lección 3: «perro» → Dog y dog → «perro»).
TRADUCCIONES = {
    # animals
    "Dog": "Perro", "Cat": "Gato", "Bird": "Pájaro", "Fish": "Pez", "Horse": "Caballo",
    "Cow": "Vaca", "Pig": "Cerdo", "Sheep": "Oveja", "Lion": "León", "Tiger": "Tigre",
    "Monkey": "Mono", "Elephant": "Elefante", "Rabbit": "Conejo", "Duck": "Pato",
    "Frog": "Rana", "Bear": "Oso",
    # colors
    "Red": "Rojo", "Blue": "Azul", "Green": "Verde", "Yellow": "Amarillo", "Orange": "Naranja",
    "Purple": "Morado", "Black": "Negro", "White": "Blanco", "Brown": "Café", "Pink": "Rosado",
    # food
    "Apple": "Manzana", "Banana": "Banano", "Bread": "Pan", "Milk": "Leche", "Pizza": "Pizza",
    "Egg": "Huevo", "Cheese": "Queso", "Rice": "Arroz", "Carrot": "Zanahoria", "Grapes": "Uvas",
    "Cake": "Torta", "Ice cream": "Helado", "Strawberry": "Fresa", "Cookie": "Galleta",
    "Chicken": "Pollo", "Corn": "Maíz",
    # numbers
    "One": "Uno", "Two": "Dos", "Three": "Tres", "Four": "Cuatro", "Five": "Cinco",
    "Six": "Seis", "Seven": "Siete", "Eight": "Ocho", "Nine": "Nueve", "Ten": "Diez",
    # transport
    "Car": "Carro", "Bus": "Bus", "Bike": "Bicicleta", "Plane": "Avión", "Train": "Tren",
    "Boat": "Barco", "Truck": "Camión", "Helicopter": "Helicóptero", "Taxi": "Taxi",
    "Motorcycle": "Moto", "Rocket": "Cohete", "Tractor": "Tractor", "Ambulance": "Ambulancia",
    "Fire truck": "Camión de bomberos", "Police car": "Carro de policía", "Scooter": "Patineta",
    # body
    "Eye": "Ojo", "Ear": "Oreja", "Nose": "Nariz", "Mouth": "Boca", "Hand": "Mano",
    "Foot": "Pie", "Leg": "Pierna", "Arm": "Brazo", "Tooth": "Diente", "Tongue": "Lengua",
    # clothes
    "T-shirt": "Camiseta", "Jeans": "Jeans", "Dress": "Vestido", "Sneakers": "Tenis",
    "Cap": "Gorra", "Socks": "Medias", "Coat": "Abrigo", "Scarf": "Bufanda", "Gloves": "Guantes",
    "Boots": "Botas", "Glasses": "Gafas", "Tie": "Corbata", "Backpack": "Morral",
    "Swimsuit": "Vestido de baño", "Shorts": "Pantaloneta", "Hat": "Sombrero",
    # nature
    "Sun": "Sol", "Rain": "Lluvia", "Snow": "Nieve", "Cloud": "Nube", "Wind": "Viento",
    "Rainbow": "Arcoíris", "Storm": "Tormenta", "Moon": "Luna", "Star": "Estrella",
    "Tree": "Árbol", "Flower": "Flor", "Mountain": "Montaña", "Sea": "Mar", "Fire": "Fuego",
    "Leaf": "Hoja", "Umbrella": "Sombrilla",
    # school
    "Book": "Libro", "Pencil": "Lápiz", "Pen": "Lapicero", "Ruler": "Regla", "Scissors": "Tijeras",
    "Notebook": "Cuaderno", "Crayon": "Crayola", "Paintbrush": "Pincel", "Computer": "Computador",
    "Clock": "Reloj", "Calculator": "Calculadora", "Globe": "Globo terráqueo",
    # sports
    "Soccer": "Fútbol", "Basketball": "Baloncesto", "Baseball": "Béisbol", "Tennis": "Tenis",
    "Volleyball": "Voleibol", "Swimming": "Natación", "Running": "Atletismo", "Cycling": "Ciclismo",
    "Skating": "Patinaje", "Skiing": "Esquí", "Boxing": "Boxeo", "Golf": "Golf",
    "Bowling": "Bolos", "Ping-pong": "Ping-pong", "Surfing": "Surf", "Football": "Fútbol americano",
    # home
    "House": "Casa", "Bed": "Cama", "Chair": "Silla", "Door": "Puerta", "Window": "Ventana",
    "Sofa": "Sofá", "Bathtub": "Bañera", "Toilet": "Inodoro", "Key": "Llave", "TV": "Televisor",
    "Phone": "Celular", "Mirror": "Espejo", "Light": "Bombillo",
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
    "articles": {
        "titulo": {"es": "Artículos a / an", "en": "Articles a / an"},
        "emoji": "🅰️",
        "explicacion": {
            "es": [
                "**a** y **an** significan **un** o **una**.",
                "Usa **a** antes de un sonido de consonante · **a** dog, **a** banana.",
                "Usa **an** antes de un sonido de vocal (a, e, i, o, u) · **an** apple, **an** egg.",
            ],
            "en": [
                "**a** and **an** mean *one* thing.",
                "Use **a** before a consonant sound · **a** dog, **a** banana.",
                "Use **an** before a vowel sound (a, e, i, o, u) · **an** apple, **an** egg.",
            ],
        },
        "lecciones": [
            [
                ("I have ___ dog.", "a", ["an"]),
                ("She eats ___ apple.", "an", ["a"]),
                ("It is ___ egg.", "an", ["a"]),
                ("He has ___ ball.", "a", ["an"]),
                ("I see ___ elephant.", "an", ["a"]),
                ("This is ___ cat.", "a", ["an"]),
                ("I want ___ orange.", "an", ["a"]),
                ("She has ___ pencil.", "a", ["an"]),
            ],
            [
                ("It is ___ umbrella.", "an", ["a"]),
                ("We have ___ car.", "a", ["an"]),
                ("I see ___ bird.", "a", ["an"]),
                ("He is ___ astronaut.", "an", ["a"]),
                ("That is ___ ice cream.", "an", ["a"]),
                ("I read ___ book.", "a", ["an"]),
                ("There is ___ octopus.", "an", ["a"]),
                ("She has ___ banana.", "a", ["an"]),
            ],
        ],
    },
    "plurals": {
        "titulo": {"es": "Plurales", "en": "Plurals"},
        "emoji": "👯",
        "explicacion": {
            "es": [
                "Para hablar de **más de uno** casi siempre se agrega **s** · cat → cat**s**.",
                "Si termina en s, sh, ch, x se agrega **es** · box → box**es**, bus → bus**es**.",
                "Algunas palabras cambian: child → **children**, man → **men**, mouse → **mice**, foot → **feet**.",
            ],
            "en": [
                "For **more than one** we usually add **s** · cat → cat**s**.",
                "Words ending in s, sh, ch, x add **es** · box → box**es**, bus → bus**es**.",
                "Some words change: child → **children**, man → **men**, mouse → **mice**, foot → **feet**.",
            ],
        },
        "lecciones": [
            [
                ("One cat, two ___.", "cats", ["cat", "cates"]),
                ("One dog, three ___.", "dogs", ["dog", "doges"]),
                ("One box, two ___.", "boxes", ["boxs", "box"]),
                ("One bus, two ___.", "buses", ["buss", "bus"]),
                ("One apple, five ___.", "apples", ["apple", "applees"]),
                ("One watch, two ___.", "watches", ["watchs", "watch"]),
                ("One book, four ___.", "books", ["book", "bookes"]),
                ("One dish, two ___.", "dishes", ["dishs", "dish"]),
            ],
            [
                ("One child, two ___.", "children", ["childs", "childes"]),
                ("One man, two ___.", "men", ["mans", "manes"]),
                ("One woman, two ___.", "women", ["womans", "womanes"]),
                ("One mouse, two ___.", "mice", ["mouses", "mousees"]),
                ("One foot, two ___.", "feet", ["foots", "footes"]),
                ("One tooth, many ___.", "teeth", ["tooths", "toothes"]),
                ("One fish, many ___.", "fish", ["fishs", "fishies"]),
                ("One sheep, many ___.", "sheep", ["sheeps", "sheepes"]),
            ],
        ],
    },
    "possessives": {
        "titulo": {"es": "Posesivos", "en": "Possessives"},
        "emoji": "🎁",
        "explicacion": {
            "es": [
                "Sirven para decir **de quién es** algo.",
                "I → **my** (mi) · you → **your** (tu) · he → **his** (su, de él) · she → **her** (su, de ella).",
                "we → **our** (nuestro) · they → **their** (su, de ellos).",
                "Ejemplo: She has a cat. **Her** cat is white.",
            ],
            "en": [
                "They tell **who something belongs to**.",
                "I → **my** · you → **your** · he → **his** · she → **her**.",
                "we → **our** · they → **their**.",
                "Example: She has a cat. **Her** cat is white.",
            ],
        },
        "lecciones": [
            [
                ("I have a dog. ___ dog is big.", "My", ["Your", "Her"]),
                ("She has a doll. ___ doll is pretty.", "Her", ["His", "My"]),
                ("He has a bike. ___ bike is red.", "His", ["Her", "Our"]),
                ("You have a pen. Is this ___ pen?", "your", ["my", "their"]),
                ("We have a house. ___ house is blue.", "Our", ["Their", "My"]),
                ("They have a car. ___ car is new.", "Their", ["Our", "His"]),
                ("Tom has a cat. ___ cat is black.", "His", ["Her", "Their"]),
                ("Ana has a ball. ___ ball is small.", "Her", ["His", "Our"]),
            ],
            [
                ("I love ___ mom.", "my", ["your", "his"]),
                ("Mary loves ___ dad.", "her", ["his", "my"]),
                ("Peter and Luis play with ___ toys.", "their", ["our", "her"]),
                ("We eat ___ lunch at school.", "our", ["their", "my"]),
                ("Is that ___ backpack, Sofia?", "your", ["my", "his"]),
                ("The boy brushes ___ teeth.", "his", ["her", "their"]),
                ("The girls wear ___ hats.", "their", ["her", "our"]),
                ("I can't find ___ shoes!", "my", ["your", "their"]),
            ],
        ],
    },
    "prepositions": {
        "titulo": {"es": "Preposiciones de lugar", "en": "Prepositions of place"},
        "emoji": "📦",
        "explicacion": {
            "es": [
                "Dicen **dónde está** algo.",
                "**in** = dentro · The cat is **in** the box.",
                "**on** = encima · The book is **on** the table.",
                "**under** = debajo · The ball is **under** the bed.",
                "**next to** = al lado · The dog is **next to** the door.",
            ],
            "en": [
                "They tell **where** something is.",
                "**in** · The cat is **in** the box.",
                "**on** · The book is **on** the table.",
                "**under** · The ball is **under** the bed.",
                "**next to** · The dog is **next to** the door.",
            ],
        },
        "lecciones": [
            [
                ("The cat is ___ the box. (dentro)", "in", ["on", "under"]),
                ("The book is ___ the table. (encima)", "on", ["in", "under"]),
                ("The ball is ___ the bed. (debajo)", "under", ["on", "in"]),
                ("The fish is ___ the water. (dentro)", "in", ["on", "under"]),
                ("The bird is ___ the tree. (encima)", "on", ["under", "in"]),
                ("The shoes are ___ the chair. (debajo)", "under", ["in", "on"]),
                ("The milk is ___ the fridge. (dentro)", "in", ["on", "under"]),
                ("The hat is ___ my head. (encima)", "on", ["in", "under"]),
            ],
            [
                ("The dog is ___ the door. (al lado)", "next to", ["in", "on"]),
                ("My pencil is ___ my bag. (dentro)", "in", ["on", "next to"]),
                ("The lamp is ___ the sofa. (al lado)", "next to", ["under", "in"]),
                ("The cat sleeps ___ the table. (debajo)", "under", ["on", "next to"]),
                ("The picture is ___ the wall. (encima)", "on", ["in", "under"]),
                ("I sit ___ my friend. (al lado)", "next to", ["in", "under"]),
                ("The toys are ___ the box. (dentro)", "in", ["on", "next to"]),
                ("The monster is ___ the bed! (debajo)", "under", ["on", "in"]),
            ],
        ],
    },
    "there-is": {
        "titulo": {"es": "There is / There are", "en": "There is / There are"},
        "emoji": "👀",
        "explicacion": {
            "es": [
                "Significan **hay**.",
                "**There is** para **uno** · There is a cat.",
                "**There are** para **varios** · There are two cats.",
                "Para preguntar: **Is there** a dog? · **Are there** apples?",
            ],
            "en": [
                "They say something exists.",
                "**There is** for **one** · There is a cat.",
                "**There are** for **many** · There are two cats.",
                "Questions: **Is there** a dog? · **Are there** apples?",
            ],
        },
        "lecciones": [
            [
                ("___ a cat in the garden.", "There is", ["There are"]),
                ("___ three books on the table.", "There are", ["There is"]),
                ("___ a ball under the bed.", "There is", ["There are"]),
                ("___ many stars in the sky.", "There are", ["There is"]),
                ("___ an apple in my bag.", "There is", ["There are"]),
                ("___ two dogs in the park.", "There are", ["There is"]),
                ("___ a big tree in my school.", "There is", ["There are"]),
                ("___ five children in the class.", "There are", ["There is"]),
            ],
            [
                ("___ a dog in your house?", "Is there", ["Are there"]),
                ("___ any cookies?", "Are there", ["Is there"]),
                ("___ a TV in your room?", "Is there", ["Are there"]),
                ("___ fish in the sea?", "Are there", ["Is there"]),
                ("There ___ a bird on the roof.", "is", ["are"]),
                ("There ___ ten pencils in the box.", "are", ["is"]),
                ("There ___ a rainbow!", "is", ["are"]),
                ("There ___ three bananas.", "are", ["is"]),
            ],
        ],
    },
    "can": {
        "titulo": {"es": "Can / Can't", "en": "Can / Can't"},
        "emoji": "💪",
        "explicacion": {
            "es": [
                "**can** = poder / saber hacer algo · I **can** swim (Sé nadar).",
                "**can't** = no poder · A fish **can't** fly (Un pez no puede volar).",
                "Después de can va el verbo **sin cambios** · She can **run** (no \"runs\").",
                "Para preguntar: **Can** you dance?",
            ],
            "en": [
                "**can** = be able to · I **can** swim.",
                "**can't** = not able to · A fish **can't** fly.",
                "After can, the verb **doesn't change** · She can **run** (not \"runs\").",
                "Questions: **Can** you dance?",
            ],
        },
        "lecciones": [
            [
                ("A bird ___ fly.", "can", ["can't"]),
                ("A fish ___ walk.", "can't", ["can"]),
                ("A dog ___ run.", "can", ["can't"]),
                ("A cat ___ read.", "can't", ["can"]),
                ("A monkey ___ climb.", "can", ["can't"]),
                ("A cow ___ fly.", "can't", ["can"]),
                ("A fish ___ swim.", "can", ["can't"]),
                ("A baby ___ drive a car.", "can't", ["can"]),
            ],
            [
                ("She can ___ very fast.", "run", ["runs", "running"]),
                ("I can ___ a picture.", "draw", ["draws", "drawing"]),
                ("___ you swim?", "Can", ["Do can", "Cans"]),
                ("He can ___ the guitar.", "play", ["plays", "playing"]),
                ("We can ___ English.", "speak", ["speaks", "speaking"]),
                ("___ your dog jump?", "Can", ["Cans", "Does can"]),
                ("They can ___ high.", "jump", ["jumps", "jumping"]),
                ("My brother can ___ a bike.", "ride", ["rides", "riding"]),
            ],
        ],
    },
}

# Lecciones 3 y 4 de cada tema (y explicación ampliada) viven en gramatica_extra.py para
# que este archivo siga siendo legible.
from app.gramatica_extra import EXTRA as _EXTRA  # noqa: E402

for _unidad, _extra in _EXTRA.items():
    GRAMATICA[_unidad]["explicacion"]["es"].extend(_extra["explicacion"][0])
    GRAMATICA[_unidad]["explicacion"]["en"].extend(_extra["explicacion"][1])
    GRAMATICA[_unidad]["lecciones"].extend(_extra["lecciones"])

# Orden de cada camino. Vocabulario y gramática son independientes: el niño elige el
# apartado y, dentro de él, la plataforma elige la siguiente lección.
ORDEN_VOCABULARIO = [
    "animals", "colors", "food", "numbers", "clothes", "body",
    "home", "school", "transport", "nature", "sports",
]
ORDEN_GRAMATICA = [
    "to-be", "articles", "plurals", "possessives", "simple-present",
    "prepositions", "there-is", "can", "present-continuous", "simple-past",
]
ORDEN_UNIDADES = ORDEN_VOCABULARIO + ORDEN_GRAMATICA
ORDEN_POR_SECCION = {"vocabulario": ORDEN_VOCABULARIO, "gramatica": ORDEN_GRAMATICA}
LECCIONES_VOCABULARIO = 5

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
    return LECCIONES_VOCABULARIO if unidad in VOCABULARIO else len(GRAMATICA[unidad]["lecciones"])


def lecciones_en_orden(seccion: str | None = None) -> list[tuple[str, int]]:
    """Lecciones de un camino (o de los dos), en el orden en que se desbloquean."""
    unidades = ORDEN_POR_SECCION[seccion] if seccion else ORDEN_UNIDADES
    return [(u, n) for u in unidades for n in range(1, numero_de_lecciones(u) + 1)]


def clave_leccion(unidad: str, leccion: int) -> str:
    return f"{unidad}-{leccion}"


def _preguntas_vocabulario(unidad: str) -> list[list[dict]]:
    """5 lecciones de 8 preguntas, cada una con un enfoque distinto para que no se repitan:

    1. **Conoce**: imagen → palabra (palabras 1–8).
    2. **Encuentra**: las palabras nuevas (9–16): imagen → palabra y palabra → imagen.
    3. **Traduce**: «perro» → Dog y dog → «perro».
    4. **Escribe**: ¿cuál está bien escrita? y la letra que falta (D_g).
    5. **Desafío**: ¿sí o no?, ¿cuál NO es…?, y un poco de todo lo anterior.

    Los mundos con menos de 16 palabras completan la lección 2 con palabras de la 1."""
    datos = VOCABULARIO[unidad]
    palabras = datos["palabras"]
    azar = random.Random(unidad)  # determinista: sembrar dos veces da el mismo contenido
    n = PREGUNTAS_POR_LECCION
    tipos = _tipos_de_pregunta(unidad, azar)

    leccion_1 = [tipos["imagen_a_palabra"](*p) for p in palabras[:n]]

    nuevas = palabras[n:2 * n]
    relleno = azar.sample(palabras[:n], n - len(nuevas))
    mitad = len(nuevas) // 2
    leccion_2 = [tipos["imagen_a_palabra"](*p) for p in nuevas[:mitad]] + [
        tipos["palabra_a_imagen"](*p) for p in nuevas[mitad:] + relleno
    ]

    traducir = azar.sample(palabras, n)
    leccion_3 = [tipos["espanol_a_ingles"](*p) for p in traducir[:n // 2]] + [
        tipos["ingles_a_espanol"](*p) for p in traducir[n // 2:]
    ]

    escribibles = [p for p in palabras if len(_letras(p[0])) >= 2]  # 3 letras o más
    escribir = azar.sample(escribibles, min(n, len(escribibles)))
    leccion_4 = [tipos["ortografia"](*p) for p in escribir[:n // 2]] + [
        tipos["letra_que_falta"](*p) for p in escribir[n // 2:]
    ]
    leccion_4 += [tipos["imagen_a_palabra"](*p) for p in azar.sample(palabras, n - len(leccion_4))]

    desafio = azar.sample(escribibles, n)
    plan = ["si_o_no", "si_o_no", "intruso", "intruso", "espanol_a_ingles",
            "ingles_a_espanol", "letra_que_falta", "palabra_a_imagen"]
    leccion_5 = [tipos[tipo](*p) for tipo, p in zip(plan, desafio)]

    # Fuera de la primera (que presenta las palabras en orden), los tipos se intercalan.
    for leccion in (leccion_2, leccion_3, leccion_4, leccion_5):
        azar.shuffle(leccion)
    return [leccion_1, leccion_2, leccion_3, leccion_4, leccion_5]


VOCALES = "aeiou"


def _letras(palabra: str) -> list[int]:
    """Posiciones de las letras (sin la primera), las que se pueden cambiar u ocultar."""
    return [i for i, c in enumerate(palabra) if c.isalpha() and i > 0]


def _mal_escritas(palabra: str, azar: random.Random) -> list[str]:
    """Tres errores de ortografía creíbles: falta una letra, una letra doble, dos letras
    al revés o una vocal cambiada (Elephant → Elefant, Elephnat, Elepant...)."""
    posiciones = _letras(palabra)
    candidatas = set()
    for i in posiciones:
        candidatas.add(palabra[:i] + palabra[i + 1:])
        candidatas.add(palabra[:i] + palabra[i] + palabra[i:])
        if i + 1 < len(palabra) and palabra[i + 1].isalpha():
            candidatas.add(palabra[:i] + palabra[i + 1] + palabra[i] + palabra[i + 2:])
        if palabra[i].lower() in VOCALES:
            candidatas.update(palabra[:i] + v + palabra[i + 1:] for v in VOCALES if v != palabra[i].lower())
    candidatas = sorted(c for c in candidatas if c.lower() != palabra.lower())
    return azar.sample(candidatas, 3)


def _tipos_de_pregunta(unidad: str, azar: random.Random) -> dict:
    """Generadores de cada tipo de pregunta para un mundo: reciben (palabra, emoji)."""
    datos = VOCABULARIO[unidad]
    palabras = datos["palabras"]
    otras_palabras = lambda palabra: [p for p, _ in palabras if p != palabra]  # noqa: E731
    otros_emojis = lambda palabra: [e for p, e in palabras if p != palabra]  # noqa: E731
    intrusos = [e for u in INTRUSOS.get(unidad, INTRUSOS_POR_DEFECTO) for _, e in VOCABULARIO[u]["palabras"]]

    def pregunta(texto, icono, correcta, distractores, formato="texto"):
        return {"pregunta": texto, "icono": icono, "respuesta_correcta": correcta,
                "opciones": [correcta, *distractores], "formato_opciones": formato}

    def imagen_a_palabra(palabra, emoji):
        return pregunta(datos["pregunta"], emoji, palabra, azar.sample(otras_palabras(palabra), 3))

    def palabra_a_imagen(palabra, emoji):
        return pregunta(f"Which one is “{palabra.lower()}”?", None, emoji,
                        azar.sample(otros_emojis(palabra), 3), "emoji")

    def espanol_a_ingles(palabra, emoji):
        return pregunta(f"¿Cómo se dice «{TRADUCCIONES[palabra].lower()}» en inglés?", None, palabra,
                        azar.sample(otras_palabras(palabra), 3))

    def ingles_a_espanol(palabra, emoji):
        otras = [TRADUCCIONES[p] for p in otras_palabras(palabra)]
        return pregunta(f"What does “{palabra.lower()}” mean?", None, TRADUCCIONES[palabra], azar.sample(otras, 3))

    def ortografia(palabra, emoji):
        return pregunta("How do you spell it?", emoji, palabra, _mal_escritas(palabra, azar))

    def letra_que_falta(palabra, emoji):
        posiciones = _letras(palabra)
        vocales = [i for i in posiciones if palabra[i].lower() in VOCALES]
        i = azar.choice(vocales or posiciones)
        letra = palabra[i].lower()
        grupo = VOCALES if letra in VOCALES else "bcdfghlmnprst"
        distractores = azar.sample([c for c in grupo if c != letra], 3)
        return pregunta(f"What letter is missing? {palabra[:i]}_{palabra[i + 1:]}", emoji, letra, distractores)

    def si_o_no(palabra, emoji):
        # La mitad de las veces el dibujo no corresponde a la palabra.
        if azar.random() < 0.5:
            return pregunta(f"Is it “{palabra.lower()}”?", emoji, "Yes", ["No"])
        return pregunta(f"Is it “{palabra.lower()}”?", azar.choice(otros_emojis(palabra)), "No", ["Yes"])

    def intruso(palabra, emoji):
        propios = [emoji, *azar.sample(otros_emojis(palabra), 2)]
        return pregunta(datos["intruso"], None, azar.choice(intrusos), propios, "emoji")

    return {f.__name__: f for f in (imagen_a_palabra, palabra_a_imagen, espanol_a_ingles, ingles_a_espanol,
                                    ortografia, letra_que_falta, si_o_no, intruso)}


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
    for unidad in ORDEN_UNIDADES:
        indice = ORDEN_POR_SECCION[seccion_de(unidad)].index(unidad) + 1
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
