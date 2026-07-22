from database.db import db
from datetime import datetime
import pytz

BOGOTA = pytz.timezone('America/Bogota')

class Client(db.Model):
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    document_type = db.Column(db.String(20), nullable=False)
    document_number = db.Column(db.String(30), unique=True, nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    birth_date = db.Column(db.Date)
    gender = db.Column(db.String(10))
    address = db.Column(db.String(255))
    emergency_contact = db.Column(db.String(150))
    emergency_phone = db.Column(db.String(20))
    enrollment_date = db.Column(db.Date, default=lambda: datetime.now(BOGOTA).date())
    is_active = db.Column(db.Boolean, default=True)
    is_migrated = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(BOGOTA))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(BOGOTA))

    # ── Reconocimiento facial ────────────────────────────────────────
    # face_embedding: JSON (lista de floats) generado por face-api.js en el navegador.
    # Se guarda como texto (JSON) para no depender de extensiones de PostgreSQL.
    face_embedding = db.Column(db.Text)
    face_registered_at = db.Column(db.DateTime)
    biometric_consent = db.Column(db.Boolean, default=False)
    biometric_consent_at = db.Column(db.DateTime)

    payments = db.relationship(
        'Payment',
        foreign_keys='Payment.client_id',
        backref='client',
        lazy=True
    )
    attendances = db.relationship('Attendance', backref='client', lazy=True)