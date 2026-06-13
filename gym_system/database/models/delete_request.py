from database.db import db
from datetime import datetime
import pytz

BOGOTA = pytz.timezone('America/Bogota')

class DeleteRequest(db.Model):
    """Solicitud de un recepcionista para eliminar un pago. Requiere aprobación del admin."""
    __tablename__ = 'delete_requests'

    id             = db.Column(db.Integer, primary_key=True)
    payment_id     = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
    requested_by   = db.Column(db.Integer, db.ForeignKey('users.id'),    nullable=False)
    justification  = db.Column(db.Text, nullable=False)
    status         = db.Column(db.String(20), default='pendiente')  # pendiente | aprobada | rechazada
    reviewed_by    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    review_note    = db.Column(db.Text, nullable=True)
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(BOGOTA))
    reviewed_at    = db.Column(db.DateTime, nullable=True)

    payment        = db.relationship('Payment',  foreign_keys=[payment_id], backref='delete_requests')
    requester      = db.relationship('User',     foreign_keys=[requested_by])
    reviewer       = db.relationship('User',     foreign_keys=[reviewed_by])
