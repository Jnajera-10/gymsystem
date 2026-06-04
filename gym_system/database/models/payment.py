from database.db import db
from datetime import datetime
import pytz

BOGOTA = pytz.timezone('America/Bogota')

class Payment(db.Model):
    __tablename__ = 'payments'
    id               = db.Column(db.Integer, primary_key=True)
    client_id        = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    membership_id    = db.Column(db.Integer, db.ForeignKey('memberships.id'), nullable=False)
    amount           = db.Column(db.Float, nullable=False)
    payment_date     = db.Column(db.Date, default=lambda: datetime.now(BOGOTA).date())
    start_date       = db.Column(db.Date, nullable=False)
    end_date         = db.Column(db.Date, nullable=False)   # último día INCLUSIVE (vence 23:59)
    payment_method   = db.Column(db.String(30), default='efectivo')
    notes            = db.Column(db.Text)
    is_deleted       = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(BOGOTA))

    # Plan pareja: segundo cliente (opcional, solo para couple plan)
    partner_client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    membership = db.relationship('Membership', backref='payments')
    partner    = db.relationship(
        'Client',
        foreign_keys=[partner_client_id],
        backref='partner_payments'
    )
