import json
import math
from database.models.client import Client
from database.db import db
import pytz
from datetime import datetime

BOGOTA = pytz.timezone('America/Bogota')

# Distancia euclidiana máxima para considerar "misma persona".
# face-api.js recomienda ~0.6 como umbral típico; ajústalo según pruebas reales
# (más bajo = más estricto, menos falsos positivos; más alto = más tolerante).
MATCH_THRESHOLD = 0.55

# Cuántas poses like mínimo/máximo se piden al registrar un rostro.
MIN_POSES = 3
MAX_POSES = 5


def _euclidean_distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _normalize_stored(raw):
    """
    Devuelve siempre una lista de embeddings (lista de listas de floats),
    sin importar si lo guardado es el formato viejo (un solo embedding
    plano) o el nuevo (varias poses).
    """
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not data:
        return []
    # Formato nuevo: lista de listas -> [[...], [...], [...]]
    if isinstance(data[0], list):
        return data
    # Formato viejo: una sola lista plana de floats -> [...]
    return [data]


class FaceService:
    @staticmethod
    def save_embedding(client_id, embeddings):
        """
        Guarda (o reemplaza) los embeddings faciales de un cliente.
        `embeddings` puede ser una sola lista de floats (compatibilidad)
        o una lista de varias poses (recomendado, ej. 3 a 5 capturas).
        """
        client = Client.query.get(client_id)
        if not client:
            return None
        if embeddings and isinstance(embeddings[0], (int, float)):
            embeddings = [embeddings]
        client.face_embedding = json.dumps(embeddings)
        client.face_registered_at = datetime.now(BOGOTA)
        db.session.commit()
        return client

    @staticmethod
    def clear_embedding(client_id):
        client = Client.query.get(client_id)
        if not client:
            return None
        client.face_embedding = None
        client.face_registered_at = None
        db.session.commit()
        return client

    @staticmethod
    def set_consent(client_id, consent=True):
        client = Client.query.get(client_id)
        if not client:
            return None
        client.biometric_consent = consent
        client.biometric_consent_at = datetime.now(BOGOTA) if consent else None
        db.session.commit()
        return client

    @staticmethod
    def find_match(embedding):
        """
        Compara el embedding recibido contra todas las poses guardadas de
        todos los clientes activos con rostro registrado. Para cada cliente
        se toma la distancia MÍNIMA entre sus poses guardadas y el embedding
        recibido (así reconoce aunque la pose actual no sea idéntica a la
        que se guardó). Devuelve (client, distance) del mejor match si está
        bajo el umbral, o (None, distance) si no hay coincidencia.
        """
        candidates = Client.query.filter(
            Client.is_active == True,
            Client.face_embedding.isnot(None),
        ).all()

        best_client = None
        best_distance = None

        for c in candidates:
            poses = _normalize_stored(c.face_embedding)
            for stored in poses:
                if len(stored) != len(embedding):
                    continue
                dist = _euclidean_distance(stored, embedding)
                if best_distance is None or dist < best_distance:
                    best_distance = dist
                    best_client = c

        if best_client is not None and best_distance is not None and best_distance <= MATCH_THRESHOLD:
            return best_client, best_distance
        return None, best_distance

