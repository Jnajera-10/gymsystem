from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.models.sales import Sale
from database.models.inventory import Product
from database.models.client import Client
from services.sales_service import SalesService

sales_bp = Blueprint('sales', __name__, url_prefix='/sales')

@sales_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    sales = Sale.query.filter_by(is_deleted=False).order_by(Sale.sale_date.desc()).all()
    return render_template('sales/sales.html', sales=sales)

@sales_bp.route('/new', methods=['GET', 'POST'])
def new():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    products = Product.query.filter_by(is_active=True).all()
    clients = Client.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        client_id = request.form.get('client_id') or None
        payment_method = request.form.get('payment_method', 'efectivo')
        product_ids = request.form.getlist('product_id')
        quantities = request.form.getlist('quantity')
        items = [{'product_id': int(pid), 'quantity': int(qty)}
                 for pid, qty in zip(product_ids, quantities) if int(qty) > 0]
        if items:
            sale = SalesService.create_sale(client_id, items, payment_method)
            flash('Venta registrada.', 'success')
            return redirect(url_for('sales.index'))
        flash('Agrega al menos un producto.', 'danger')
    return render_template('sales/new_sale.html', products=products, clients=clients)
