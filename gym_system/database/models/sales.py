from database.db import db
from datetime import datetime
import pytz

BOGOTA = pytz.timezone('America/Bogota')

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    total = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(30), default='efectivo')
    notes = db.Column(db.Text)
    is_deleted = db.Column(db.Boolean, default=False)
    sale_date = db.Column(db.DateTime, default=lambda: datetime.now(BOGOTA))

    # Relación con el cliente (nullable porque puede ser venta sin cliente registrado)
    client = db.relationship('Client', backref='sales', lazy=True, foreign_keys=[client_id])
    items = db.relationship('SaleItem', backref='sale', lazy=True)

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    product = db.relationship('Product', backref='sale_items', lazy=True)
