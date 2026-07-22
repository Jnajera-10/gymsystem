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


def _euclidean_distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class FaceService:
    @staticmethod
    def save_embedding(client_id, embedding):
        """Guarda (o reemplaza) el embedding facial de un cliente."""
        client = Client.query.get(client_id)
        if not client:
            return None
        client.face_embedding = json.dumps(embedding)
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
        Compara el embedding recibido contra todos los clientes activos
        que tengan rostro registrado. Devuelve (client, distance) del mejor
        match si está bajo el umbral, o (None, None) si no hay coincidencia.
        """
        candidates = Client.query.filter(
            Client.is_active == True,
            Client.face_embedding.isnot(None),
        ).all()

        best_client = None
        best_distance = None

        for c in candidates:
            try:
                stored = json.loads(c.face_embedding)
            except (TypeError, ValueError):
                continue
            if len(stored) != len(embedding):
                continue
            dist = _euclidean_distance(stored, embedding)
            if best_distance is None or dist < best_distance:
                best_distance = dist
                best_client = c

        if best_client is not None and best_distance is not None and best_distance <= MATCH_THRESHOLD:
            return best_client, best_distance
        return None, best_distance
