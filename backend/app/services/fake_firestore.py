"""
Implementación mínima en memoria del subconjunto de la interfaz de
`firestore.Client` que usa este proyecto (collection/document/where/order_by/
limit/stream/get/set/update/reference).

Sirve ÚNICAMENTE para desarrollo local y para las pruebas automatizadas
(`backend/tests/`), de forma que se pueda correr y probar toda la API sin
depender de un proyecto de Firebase real. Se activa con `USE_FAKE_DB=true` en
`.env` (ver `app/config.py` y `app/services/firebase_service.py`).

NUNCA usar en producción: no persiste en disco, no tiene reglas de seguridad y
vive solo mientras el proceso está corriendo.
"""
import itertools


def _coincide(data: dict, campo: str, operador: str, valor) -> bool:
    actual = data.get(campo)
    if operador == "==":
        return actual == valor
    if operador == "!=":
        return actual != valor
    if operador == "array_contains":
        return isinstance(actual, list) and valor in actual
    if operador in (">", ">=", "<", "<="):
        if actual is None:
            return False
        return {
            ">": actual > valor,
            ">=": actual >= valor,
            "<": actual < valor,
            "<=": actual <= valor,
        }[operador]
    raise NotImplementedError(f"Operador no soportado en el fake: {operador}")


class _FakeSnapshot:
    def __init__(self, doc_id, data, reference=None):
        self.id = doc_id
        self._data = data
        self.exists = data is not None
        self.reference = reference

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _FakeDocumentRef:
    def __init__(self, store: dict, path: str, doc_id: str):
        self._store = store
        self._path = path
        self.id = doc_id

    def get(self):
        data = self._store.get(self._path, {}).get(self.id)
        return _FakeSnapshot(self.id, data, reference=self)

    def set(self, data: dict, merge: bool = False):
        coleccion = self._store.setdefault(self._path, {})
        if merge and self.id in coleccion:
            actual = dict(coleccion[self.id])
            actual.update(data)
            coleccion[self.id] = actual
        else:
            coleccion[self.id] = dict(data)

    def update(self, data: dict):
        coleccion = self._store.setdefault(self._path, {})
        if self.id not in coleccion:
            raise KeyError(f"El documento {self._path}/{self.id} no existe")
        actual = dict(coleccion[self.id])
        actual.update(data)
        coleccion[self.id] = actual

    def collection(self, nombre: str) -> "_FakeCollectionRef":
        return _FakeCollectionRef(self._store, f"{self._path}/{self.id}/{nombre}")


class _FakeCollectionRef:
    _contador = itertools.count(1)

    def __init__(self, store: dict, path: str, filtros=None, orden=None, limite=None):
        self._store = store
        self._path = path
        self._filtros = filtros or []
        self._orden = orden
        self._limite = limite

    def document(self, doc_id: str | None = None) -> _FakeDocumentRef:
        if doc_id is None:
            doc_id = f"auto{next(_FakeCollectionRef._contador)}"
        return _FakeDocumentRef(self._store, self._path, doc_id)

    def where(self, campo: str, operador: str, valor) -> "_FakeCollectionRef":
        return _FakeCollectionRef(
            self._store, self._path, [*self._filtros, (campo, operador, valor)], self._orden, self._limite
        )

    def order_by(self, campo: str, direction: str = "ASCENDING") -> "_FakeCollectionRef":
        return _FakeCollectionRef(self._store, self._path, self._filtros, (campo, direction), self._limite)

    def limit(self, n: int) -> "_FakeCollectionRef":
        return _FakeCollectionRef(self._store, self._path, self._filtros, self._orden, n)

    def stream(self):
        coleccion = self._store.get(self._path, {})
        resultados = []
        for doc_id, data in coleccion.items():
            if all(_coincide(data, campo, op, valor) for campo, op, valor in self._filtros):
                ref = _FakeDocumentRef(self._store, self._path, doc_id)
                resultados.append(_FakeSnapshot(doc_id, data, reference=ref))
        if self._orden:
            campo, direction = self._orden
            resultados.sort(
                key=lambda snap: (snap.to_dict().get(campo) is None, snap.to_dict().get(campo)),
                reverse=direction.upper() == "DESCENDING",
            )
        if self._limite is not None:
            resultados = resultados[: self._limite]
        return resultados


class FakeFirestoreClient:
    def __init__(self):
        self._store: dict[str, dict] = {}

    def collection(self, nombre: str) -> _FakeCollectionRef:
        return _FakeCollectionRef(self._store, nombre)

    def reset(self):
        """Solo para pruebas: vacía todos los datos entre tests."""
        self._store.clear()


class FakeRealtimeRef:
    """Reemplazo mínimo de una referencia de Realtime Database para dev/pruebas."""

    def __init__(self, store: dict, path: str):
        self._store = store
        self._path = path

    def set(self, data):
        self._store[self._path] = data

    def get(self, shallow: bool = False):
        return self._store.get(self._path)

    def delete(self):
        self._store.pop(self._path, None)


_cliente_fake: FakeFirestoreClient | None = None
_realtime_store: dict[str, dict] = {}


def get_fake_firestore_client() -> FakeFirestoreClient:
    global _cliente_fake
    if _cliente_fake is None:
        _cliente_fake = FakeFirestoreClient()
    return _cliente_fake


def get_fake_realtime_ref(path: str) -> FakeRealtimeRef:
    return FakeRealtimeRef(_realtime_store, path)
