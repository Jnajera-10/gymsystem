from database.db import db
from datetime import datetime
import pytz

BOGOTA = pytz.timezone('America/Bogota')


class CashRegister(db.Model):
    """Caja diaria: registra el monto base con el que empieza el día."""
    __tablename__ = 'cash_registers'

    id           = db.Column(db.Integer, primary_key=True)
    date         = db.Column(db.Date, nullable=False, unique=True)   # un registro por día
    opening_cash = db.Column(db.Float, nullable=False, default=0)    # monto base del día
    notes        = db.Column(db.Text, nullable=True)
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(BOGOTA))
    updated_at   = db.Column(db.DateTime, onupdate=lambda: datetime.now(BOGOTA))

    def __repr__(self):
        return f'<CashRegister {self.date} base=${self.opening_cash}>'
