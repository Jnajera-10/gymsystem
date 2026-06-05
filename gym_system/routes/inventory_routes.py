from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.models.inventory import Product, StockMovement
from database.db import db
from services.inventory_service import InventoryService
from utils.security import login_required, role_required
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')


def _parse_date(value):
    """Convierte string 'YYYY-MM-DD' a date, o None si está vacío/inválido."""
    if not value or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@inventory_bp.route('/')
@login_required
def index():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    low_stock = InventoryService.low_stock()
    movements = StockMovement.query.order_by(StockMovement.created_at.desc()).limit(50).all()
    return render_template(
        'inventory/products.html',
        products=products,
        low_stock=low_stock,
        movements=movements,
    )


@inventory_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('El nombre del producto es obligatorio.', 'danger')
            return redirect(url_for('inventory.index'))

        purchase_price = _safe_float(request.form.get('purchase_price'))
        sale_price = _safe_float(request.form.get('sale_price'))

        if sale_price <= 0:
            flash('El precio de venta debe ser mayor a 0.', 'danger')
            return redirect(url_for('inventory.index'))

        p = Product(
            name=name,
            category=request.form.get('category', '').strip() or None,
            brand=request.form.get('brand', '').strip() or None,
            presentation=request.form.get('presentation', '').strip() or None,
            quantity=_safe_int(request.form.get('quantity', 0)),
            purchase_price=purchase_price,
            sale_price=sale_price,
            min_stock=_safe_int(request.form.get('min_stock', 5)),
            expiration_date=_parse_date(request.form.get('expiration_date')),
        )
        try:
            db.session.add(p)
            db.session.commit()
            flash(f'Producto "{p.name}" creado exitosamente.', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'[inventory.create] {e}')
            flash('Error al crear el producto. Intenta de nuevo.', 'danger')
        return redirect(url_for('inventory.index'))

    # GET: mostrar el formulario (integrado en products.html)
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    low_stock = InventoryService.low_stock()
    return render_template('inventory/products.html', products=products, low_stock=low_stock, show_create=True)


@inventory_bp.route('/<int:pid>/add-stock', methods=['POST'])
@login_required
def add_stock(pid):
    qty = _safe_int(request.form.get('quantity', 0))
    reason = request.form.get('reason', 'Entrada manual').strip() or 'Entrada manual'
    if qty <= 0:
        flash('La cantidad debe ser mayor a 0.', 'danger')
        return redirect(url_for('inventory.index'))
    try:
        InventoryService.add_stock(pid, qty, reason)
        flash(f'Stock actualizado (+{qty} unidades).', 'success')
    except Exception as e:
        logger.error(f'[inventory.add_stock] {e}')
        flash('Error al agregar stock.', 'danger')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/<int:pid>/edit', methods=['POST'])
@login_required
@role_required('admin')
def edit(pid):
    p = Product.query.get_or_404(pid)

    name = request.form.get('name', '').strip()
    if not name:
        flash('El nombre no puede estar vacío.', 'danger')
        return redirect(url_for('inventory.index'))

    sale_price = _safe_float(request.form.get('sale_price'))
    if sale_price <= 0:
        flash('El precio de venta debe ser mayor a 0.', 'danger')
        return redirect(url_for('inventory.index'))

    p.name = name
    p.category = request.form.get('category', '').strip() or None
    p.brand = request.form.get('brand', '').strip() or None
    p.presentation = request.form.get('presentation', '').strip() or None
    p.purchase_price = _safe_float(request.form.get('purchase_price'))
    p.sale_price = sale_price
    p.min_stock = _safe_int(request.form.get('min_stock', 5))
    p.expiration_date = _parse_date(request.form.get('expiration_date'))

    # Solo permitir editar cantidad si se envía explícitamente (campo opcional)
    qty_str = request.form.get('quantity', '').strip()
    if qty_str:
        p.quantity = _safe_int(qty_str, p.quantity)

    try:
        db.session.commit()
        flash(f'Producto "{p.name}" actualizado.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f'[inventory.edit] {e}')
        flash('Error al actualizar el producto.', 'danger')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/<int:pid>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete(pid):
    p = Product.query.get_or_404(pid)
    p.is_active = False
    db.session.commit()
    flash(f'Producto "{p.name}" eliminado del inventario.', 'warning')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/movements')
@login_required
def movements():
    page = request.args.get('page', 1, type=int)
    pagination = (
        StockMovement.query
        .order_by(StockMovement.created_at.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )
    return render_template(
        'inventory/stock_movements.html',
        movements=pagination.items,
        pagination=pagination,
    )


@inventory_bp.route('/alerts')
@login_required
def alerts():
    low_stock = InventoryService.low_stock()
    return render_template('inventory/alerts.html', products=low_stock)
