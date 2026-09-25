# Modelo de datos (Firestore)

Este modelo traduce el diccionario de datos relacional del documento de grado
(usuarios, actividades, historial_actividades, resultados, historial_recompensas) a
colecciones de Firestore, y agrega lo necesario para feedback docente y la futura
integración con ESP32.

> Firestore es una base NoSQL orientada a documentos. En vez de JOINs se usan
> referencias (`id_usuario`) y, cuando conviene por rendimiento, subcolecciones.

## Colección `usuarios`

```
usuarios/{id_usuario}
├── nombre: string
├── edad: number
├── rol: "estudiante" | "docente" | "padre" | "admin"
├── acudientes_ids: array<string>    // uno o más padres/acudientes vinculados (RF11, si rol = estudiante)
├── codigo_acceso: string           // solo estudiantes: código corto de 6 caracteres para el login
├── autorizacion_datos: map         // solo estudiantes (Ley 1581 / Decreto 1377): quién autorizó
│     { otorgada_por, rol, fecha, version_terminos }
├── terminos_aceptados: map         // solo adultos: { version, fecha } de frontend/terminos.html
├── docente_id: string | null        // docente asignado (si rol = estudiante)
├── email: string | null             // solo docentes/padres/admin (login con Firebase Auth)
├── auth_uid: string | null          // uid de Firebase Auth, si aplica
├── pin_hash: string | null          // hash del PIN de acceso simplificado (RF01) — nunca se guarda en texto plano
├── device_id: string | null        // dispensador ESP32 asignado (si rol = estudiante, fase futura del hardware).
│                                    // Si es null, el frontend no promete una "recompensa física" al ganarla.
├── activo: boolean
├── creado_en: timestamp
└── actualizado_en: timestamp
```

## Colección `actividades`

```
actividades/{id_actividad}
├── nombre: string
├── descripcion: string
├── nivel: number            // 1 fácil, 2 medio, 3 difícil
├── tipo: "vocabulario"      // único tipo soportado por ahora (RF03 se acotó a vocabulario)
├── puntaje_maximo: number
├── activo: boolean
├── pregunta: string | null       // ej. "What animal is this?"
├── opciones: array<string>        // ej. ["Dog", "Cat", "Bird", "Fish"]
├── respuesta_correcta: string | null
└── icono: string | null           // emoji que ilustra la actividad, ej. "🐶"
```

El contenido (`pregunta`/`opciones`/`respuesta_correcta`/`icono`) lo interpreta
`frontend/activity.html` sin tocar código (RNF-ESC-01): agregar vocabulario nuevo es
crear un documento más con `POST /api/actividades`. Ver
`backend/scripts/seed_actividades.py` para un catálogo inicial de ejemplo.

## Colección `historial_actividades`

```
historial_actividades/{id_hist}
├── id_usuario: string        (ref -> usuarios)
├── id_actividad: string      (ref -> actividades)
├── fecha: timestamp
├── tiempo_empleado: number   // segundos
├── intentos: number
└── puntaje_obtenido: number
```

## Colección `resultados` (progreso acumulado por estudiante)

Se recomienda como **subcolección** de `usuarios` para leerla rápido junto al perfil:

```
usuarios/{id_usuario}/resultados/actual
├── puntaje_total: number
├── nivel_logrado: number
├── actividades_completadas: number
└── actualizado_en: timestamp
```

## Colección `historial_recompensas`

```
historial_recompensas/{id_historial}
├── id_usuario: string        (ref -> usuarios)
├── fecha_entrega: timestamp
├── puntos_consumidos: number
├── estado: "pendiente" | "entregada" | "error"
└── device_id: string | null   // qué dispensador ESP32 la debe entregar
```

## Colección `feedback` (nuevo — pedido explícito: feedback del progreso)

```
feedback/{id_feedback}
├── id_estudiante: string     (ref -> usuarios)
├── id_docente: string        (ref -> usuarios)
├── fecha: timestamp
├── comentario: string
├── tipo: "progreso" | "conducta" | "recomendacion"
└── visible_para_padres: boolean
```

## Colección `intentos_pin` (RF01/RF07, seguridad)

Cuenta los intentos fallidos de código + PIN para bloquear un código tras varios
fallos seguidos (el PIN es de solo 4 dígitos). La usan el login del niño y la
vinculación de padres/docentes.

```
intentos_pin/{codigo_acceso}
├── fallos: number                 // intentos fallidos seguidos
└── bloqueado_hasta: timestamp | null  // tras 5 fallos, 10 minutos de bloqueo
```

## Colección `auditoria` (RNF-AUD-*)

Solo-inserción: nunca se edita ni se borra (ver `firebase/firestore.rules` y
`app/services/auth_service.py: registrar_auditoria`).

```
auditoria/{id}
├── tipo: string        // "login_exitoso" | "login_fallido" | "actividad_creada" |
│                        // "feedback_creado" | "vinculacion_codigo_generado" |
│                        // "vinculacion_confirmada" | "recompensa_generada" | "error_sistema"
├── actor: string | null   (ref -> usuarios, o null si no aplica)
├── detalle: map            // contexto específico del evento
└── fecha: timestamp
```

## Realtime Database — cola para el ESP32 (fase futura)

Solo esto vive en Realtime Database, no en Firestore, por la mejor compatibilidad de las
librerías de ESP32:

```
cola_recompensas/
└── {device_id}/
    ├── id_usuario: string
    ├── id_historial_recompensa: string
    ├── comando: "dispensar"
    ├── estado: "pendiente" | "en_proceso" | "completado"
    └── timestamp: number
```

## Tabla de equivalencia con el modelo relacional original

| Tabla SQL original | Colección Firestore |
|---|---|
| `usuarios` | `usuarios` |
| `actividades` | `actividades` |
| `historial_actividades` | `historial_actividades` |
| `resultados` | `usuarios/{id}/resultados/actual` |
| `historial_recompensas` | `historial_recompensas` |
| — (nuevo) | `feedback` |
| — (nuevo, seguridad del PIN) | `intentos_pin` |
| — (nuevo, auditoría) | `auditoria` |
| — (nuevo, hardware) | Realtime Database: `cola_recompensas` |

## Índices que probablemente necesitarás

Ya están declarados en [`firebase/firestore.indexes.json`](../firebase/firestore.indexes.json):

- `historial_actividades`: compuesto por `id_usuario` + `fecha` (para el historial de un niño ordenado).
- `feedback`: compuesto por `id_estudiante` + `fecha`.
- `historial_recompensas`: compuesto por `id_usuario` + `estado`.
