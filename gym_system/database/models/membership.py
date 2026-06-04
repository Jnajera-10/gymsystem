from database.db import db
from datetime import datetime
import pytz

BOGOTA = pytz.timezone('America/Bogota')

# Tipos de membresía disponibles
MEMBERSHIP_TYPES = [
    ('diario',        'Diario',        1),
    ('mensual',       'Mensual',       30),
    ('pareja',        'Plan Pareja',   30),   # 2 personas obligatorio
    ('trimestral',    'Trimestral',    90),
    ('semestral',     'Semestral',     180),
    ('anual',         'Anual',         365),
    ('estudiantil',   'Estudiantil',   30),   # solo bachilleres
]

class Membership(db.Model):
    __tablename__ = 'memberships'
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    duration_days   = db.Column(db.Integer, nullable=False)
    price           = db.Column(db.Float, nullable=False)
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(BOGOTA))

    # Tipo de plan (diario, mensual, pareja, trimestral, semestral, anual, estudiantil)
    membership_type = db.Column(db.String(30), nullable=False, default='mensual')

    # Plan pareja: mínimo y máximo 2 miembros
    max_members     = db.Column(db.Integer, nullable=False, default=1)

    # Plan estudiantil: cliente debe ser bachiller
    requires_student = db.Column(db.Boolean, default=False)

    @property
    def is_couple_plan(self):
        return self.membership_type == 'pareja'

    @property
    def is_student_plan(self):
        return self.membership_type == 'estudiantil'
