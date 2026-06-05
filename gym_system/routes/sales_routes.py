from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.models.sales import Sale
from database.models.inventory import Product
from database.models.client import Client
from database.db import db
from services.sales_service import SalesService
from utils.security import login_required, admin_required
import logging

logger = logging.getLogger(__name__)

sales_bp = Blueprint('sales', __name__, url_prefix='/sales')
PER_PAGE = 30


@sales_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    pagination = (
        Sale.query
        .filter_by(is_deleted=False)
        .order_by(Sale.sale_date.desc())
        .paginate(page=page, per_page=PER_PAGE, error_out=False)
    )
    return render_template('sales/sales.html', sales=pagination.items, pagination=pagination)


@sales_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    clients = Client.query.filter_by(is_active=True).order_by(Client.full_name).all()

    if request.method == 'POST':
        client_id = request.form.get('client_id') or None
        payment_method = request.form.get('payment_method', 'efectivo')
        notes = request.form.get('notes', '').strip() or None

        product_ids = request.form.getlist('product_id')
        quantities = request.form.getlist('quantity')

        # Conversión segura; saltar filas con datos inválidos
        items = []
        parse_error = False
        for pid_str, qty_str in zip(product_ids, quantities):
            try:
                pid = int(pid_str)
                qty = int(qty_str)
                if qty > 0:
                    items.append({'product_id': pid, 'quantity': qty})
            except (ValueError, TypeError):
                parse_error = True

        if parse_error:
            flash('Algunos valores de cantidad son inválidos y fueron ignorados.', 'warning')

        if not items:
            flash('Agrega al menos un producto con cantidad mayor a 0.', 'danger')
            return render_template('sales/new_sale.html', products=products, clients=clients)

        try:
            sale = SalesService.create_sale(client_id, items, payment_method, notes)
            flash('Venta registrada exitosamente.', 'success')
            return redirect(url_for('sales.invoice', sid=sale.id))
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            logger.error(f'[sales.new] Error inesperado: {e}')
            flash('Error inesperado al registrar la venta. Intenta de nuevo.', 'danger')

    return render_template('sales/new_sale.html', products=products, clients=clients)


@sales_bp.route('/<int:sid>/delete', methods=['POST'])
@admin_required
def delete(sid):
    sale = Sale.query.get_or_404(sid)
    if sale.is_deleted:
        flash('Esta venta ya fue eliminada.', 'warning')
        return redirect(url_for('sales.index'))

    # Revertir stock al eliminar (soft-delete)
    try:
        for item in sale.items:
            if item.product:
                item.product.quantity += item.quantity
        sale.is_deleted = True
        db.session.commit()
        flash('Venta eliminada y stock revertido.', 'warning')
    except Exception as e:
        db.session.rollback()
        logger.error(f'[sales.delete] {e}')
        flash('Error al eliminar la venta.', 'danger')

    return redirect(url_for('sales.index'))


@sales_bp.route('/<int:sid>/invoice')
@login_required
def invoice(sid):
    sale = Sale.query.get_or_404(sid)
    return render_template('sales/invoice.html', sale=sale)
